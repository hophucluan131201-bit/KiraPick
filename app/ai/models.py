"""Model registry: which weights exist locally, and may they be opened?

The manifest (configs/model-manifest.json) says where each weight comes from and its file name. Whether a weight may
be opened is decided only by the allow-list (configs/model-policy.json, app/ai/policy.py): status ``verified`` and a
SHA-256 pinned there. A file that is missing, differs, or is not allowed is reported as unavailable — never used,
never re-downloaded by the app. ``<file>.sha256`` side files written at build time are not trusted.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.ai.policy import LOAD_LOG, ModelPolicy, load_model_policy

_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = _ROOT / "configs" / "model-manifest.json"


class ModelState(str, Enum):
    READY = "ready"
    MISSING = "missing"
    CORRUPT = "corrupt"  # present but its SHA-256 is not one pinned in the allow-list
    BLOCKED = "blocked"  # the allow-list does not allow this weight (pending / never / not listed)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    name: str
    file: str
    sha256: str
    size: int
    license: str
    url: str
    provenance: str
    runtime: str
    purpose: str = "identity"  # "identity": needed to group people; "quality": optional scoring;
    # "gpu": larger model used only when CUDA really runs (not shipped in the CPU installer);
    # "identity_plus": optional stronger identity cues (grouping falls back without them)
    archive_member: str = ""  # the file is this member of the zip archive at ``url``


@dataclass(frozen=True, slots=True)
class ModelStatus:
    spec: ModelSpec
    state: ModelState
    path: Path


def default_models_dir() -> Path:
    """KIRAPICK_MODELS_DIR (or the old SNORLU_MODELS_DIR), else models/ next to a packaged exe, else the repo's models/weights."""
    env = os.environ.get("KIRAPICK_MODELS_DIR") or os.environ.get("SNORLU_MODELS_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "models"
    return _ROOT / "models" / "weights"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, ModelSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: ModelSpec(**m) for m in data["models"]}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    def __init__(self, models_dir: Path | None = None, manifest: dict[str, ModelSpec] | None = None,
                 policy: ModelPolicy | None = None) -> None:
        self.models_dir = models_dir or default_models_dir()
        self.specs = manifest if manifest is not None else load_manifest()
        self.policy = policy if policy is not None else load_model_policy()
        self._verified: dict[str, tuple[int, int, str]] = {}  # id -> (size, mtime_ns, sha256 of the file)

    def status(self, model_id: str) -> ModelStatus:
        spec = self.specs[model_id]
        path = self.models_dir / spec.file
        try:
            st = path.stat()
        except OSError:
            return ModelStatus(spec, ModelState.MISSING, path)
        refusal = self.policy.refusal(model_id)
        if refusal is not None:  # refused before the file is even read
            LOAD_LOG.refuse(model_id, path, refusal)
            return ModelStatus(spec, ModelState.BLOCKED, path)
        sha = self.file_sha256(model_id, path, st)
        entry = self.policy.entry(model_id)
        if entry is None or not entry.accepts(sha, st.st_size):
            LOAD_LOG.refuse(model_id, path, "mã băm không có trong danh sách cho phép")
            return ModelStatus(spec, ModelState.CORRUPT, path)
        return ModelStatus(spec, ModelState.READY, path)

    def file_sha256(self, model_id: str, path: Path, st: os.stat_result | None = None) -> str:
        """SHA-256 of the file itself (cached while its size and mtime do not change)."""
        st = st or path.stat()
        cached = self._verified.get(model_id)
        if cached is None or cached[:2] != (st.st_size, st.st_mtime_ns):
            cached = (st.st_size, st.st_mtime_ns, sha256_of(path))
            self._verified[model_id] = cached
        return cached[2]

    def require(self, model_id: str) -> Path:
        status = self.status(model_id)
        if status.state is not ModelState.READY:
            raise ModelUnavailableError(status)
        LOAD_LOG.handed_out(model_id, status.path, self._verified[model_id][2])
        return status.path

    def all_status(self) -> list[ModelStatus]:
        return [self.status(model_id) for model_id in self.specs]

    def can_detect(self) -> bool:
        """People and faces can be found (YOLOX-S + YuNet): the analysis runs, grouping may still be manual only."""
        return all(self.status(i).state is ModelState.READY for i in ("person_detector_s", "face_detector"))

    def can_recognise(self) -> bool:
        """A face recogniser is verified: only then are people grouped automatically (LIC-1 S3)."""
        return self.status("face_embedder").state is ModelState.READY

    def ready(self, purpose: str) -> bool:
        """All models needed for one purpose are present and verified."""
        ids = [i for i, s in self.specs.items() if s.purpose == purpose]
        return bool(ids) and all(self.status(i).state is ModelState.READY for i in ids)


class ModelUnavailableError(RuntimeError):
    def __init__(self, status: ModelStatus) -> None:
        self.status = status
        what = {ModelState.MISSING: "chưa có", ModelState.BLOCKED: "không được phép dùng trong bản này"}.get(
            status.state, "bị hỏng/không đúng phiên bản")
        super().__init__(f"Mô hình {status.spec.name} {what}: {status.path}")
