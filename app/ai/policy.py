"""Which model weights KiraPick may open: one allow-list for every mode (configs/model-policy.json).

A weight may be opened only when its status is ``verified`` **and** the file's SHA-256 is one of the hashes pinned in
the list. ``pending`` (no basis for the purpose yet) and ``never`` weights are refused whatever the file is, and
``<file>.sha256`` side files are not trusted: editing one cannot make a file acceptable. ModelRegistry asks this
policy before it hands out any path, so every load path (normal run, GPU -> CPU, YOLOX-M -> S, --self-test)
goes through the same check.

LOAD_LOG records, for the self-test's report A and the analysis log, every weight that was really opened (id,
SHA-256 computed from the file itself, provider) and every weight that was present but refused (with the reason).
It holds model ids, file names and hashes only: never photo names, paths of photos or metadata.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = _ROOT / "configs" / "model-policy.json"
STATUSES = frozenset({"verified", "pending", "never"})
BENCHMARK = frozenset({"yes", "pending", "no"})
MODES = frozenset({"personal"})

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Pinned:
    sha256: str
    size: int
    note: str = ""


@dataclass(frozen=True, slots=True)
class PolicyEntry:
    id: str
    status: str
    modes: frozenset[str]
    pinned: tuple[Pinned, ...]
    terms: str
    # Internal benchmark (development machine, never shipped): {"allowed": "yes" | "pending" | "no", "basis": "…"},
    # decided per weight from its own terms. It never lets the app open a weight: only "status" does that.
    benchmark: dict | None = None

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def accepts(self, sha256: str, size: int) -> bool:
        return self.verified and any(p.sha256 == sha256 and p.size == size for p in self.pinned)


@dataclass(frozen=True, slots=True)
class ModelPolicy:
    entries: dict[str, PolicyEntry]

    def entry(self, model_id: str) -> PolicyEntry | None:
        return self.entries.get(model_id)

    def verified(self, model_id: str, mode: str | None = None) -> bool:
        e = self.entries.get(model_id)
        return e is not None and e.verified and (mode is None or mode in e.modes)

    def refusal(self, model_id: str) -> str | None:
        """Why this weight may not be opened at all (None: it may, if its hash is pinned)."""
        e = self.entries.get(model_id)
        if e is None:
            return "không có trong danh sách cho phép"
        if e.status == "never":
            return "không bao giờ được dùng (điều khoản không cho phép)"
        if e.status == "pending":
            return "chưa đủ căn cứ sử dụng (chờ xác minh)"
        return None

    def ids(self, status: str) -> list[str]:
        return [e.id for e in self.entries.values() if e.status == status]


def parse_policy(data: dict) -> ModelPolicy:
    entries: dict[str, PolicyEntry] = {}
    for m in data["models"]:
        status = m["status"]
        if status not in STATUSES:
            raise ValueError(f"{m['id']}: unknown status {status!r}")
        if m["id"] in entries:
            raise ValueError(f"{m['id']}: listed twice")
        modes = frozenset(m.get("modes", []))
        if modes - MODES:
            raise ValueError(f"{m['id']}: unknown modes {sorted(modes - MODES)}")
        pinned = tuple(Pinned(p["sha256"].lower(), int(p["size"]), p.get("note", "")) for p in m.get("pinned", []))
        if status == "verified" and not pinned:
            raise ValueError(f"{m['id']}: verified without a pinned SHA-256")
        bench = m.get("benchmark")
        if bench is not None and (bench.get("allowed") not in BENCHMARK or not bench.get("basis")):
            raise ValueError(f"{m['id']}: benchmark needs allowed in {sorted(BENCHMARK)} and a basis")
        if status != "verified" and pinned:
            raise ValueError(f"{m['id']}: {status} weights must not pin a hash")
        entries[m["id"]] = PolicyEntry(m["id"], status, modes, pinned, m.get("terms", ""),
                                     m.get("benchmark"))
    return ModelPolicy(entries)


def load_model_policy(path: Path = POLICY_PATH) -> ModelPolicy:
    return parse_policy(json.loads(path.read_text(encoding="utf-8")))


def policy_for_tests(entries: dict[str, tuple[str, int]], status: str = "verified",
                     modes: tuple[str, ...] = ("personal",)) -> ModelPolicy:
    """A policy verifying exactly these files (id -> (sha256, size)); for tests with synthetic weights only."""
    return ModelPolicy({i: PolicyEntry(i, status, frozenset(modes), (Pinned(sha, size),) if status == "verified" else (),
                                       "test") for i, (sha, size) in entries.items()})


@dataclass
class LoadLog:
    """What was really opened (report A) and what was present but refused."""

    opened: dict[str, dict] = field(default_factory=dict)  # model id -> {file, sha256, providers}
    refused: dict[str, dict] = field(default_factory=dict)  # model id -> {file, reason}
    _by_path: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def handed_out(self, model_id: str, path: Path, sha256: str) -> None:
        with self._lock:
            self._by_path[str(Path(path).resolve())] = model_id
            self.opened.setdefault(model_id, {"file": Path(path).name, "sha256": sha256, "providers": []})
            self.opened[model_id]["sha256"] = sha256

    def provider(self, path: Path, provider: str) -> None:
        """A session / network was created on this file with this provider (cuda, directml, cpu, opencv)."""
        with self._lock:
            model_id = self._by_path.get(str(Path(path).resolve()))
            if model_id is None:  # not handed out by the registry: a load path that bypassed the check
                log.error("model file opened without the allow-list check: %s", Path(path).name)
                self.refused.setdefault("?" + Path(path).name, {"file": Path(path).name,
                                                                 "reason": "mở không qua danh sách cho phép"})
                return
            providers = self.opened[model_id]["providers"]
            if provider not in providers:
                providers.append(provider)
                log.info("model opened: id=%s file=%s sha256=%s provider=%s", model_id, Path(path).name,
                         self.opened[model_id]["sha256"], provider)

    def refuse(self, model_id: str, path: Path, reason: str) -> None:
        with self._lock:
            if model_id not in self.refused:
                self.refused[model_id] = {"file": Path(path).name, "reason": reason}
                log.info("model skipped: id=%s file=%s reason=%s", model_id, Path(path).name, reason)

    def report(self) -> dict:
        with self._lock:
            return {"opened": {k: dict(v, providers=list(v["providers"])) for k, v in sorted(self.opened.items())},
                    "skipped": dict(sorted(self.refused.items()))}

    def clear(self) -> None:
        with self._lock:
            self.opened.clear()
            self.refused.clear()
            self._by_path.clear()


LOAD_LOG = LoadLog()
