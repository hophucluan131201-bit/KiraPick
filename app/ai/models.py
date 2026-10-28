"""Model registry: which weights exist locally, and are they the exact files we expect?

The manifest (configs/model-manifest.json) pins every file by SHA-256. A file
that is missing or differs is reported as unavailable — never used, never
re-downloaded by the app.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = _ROOT / "configs" / "model-manifest.json"


class ModelState(str, Enum):
    READY = "ready"
    MISSING = "missing"
    CORRUPT = "corrupt"  # present but SHA-256 differs


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


def _read_sidecar(path: Path) -> tuple[str, int, str] | None:
    """``<file>.sha256``: "<sha256> <size> [origin]" written by a build-time converter."""
    try:
        parts = path.with_name(path.name + ".sha256").read_text().split()
        return parts[0], int(parts[1]), parts[2] if len(parts) > 2 else ""
    except (OSError, ValueError, IndexError):
        return None


class ModelRegistry:
    def __init__(self, models_dir: Path | None = None, manifest: dict[str, ModelSpec] | None = None) -> None:
        self.models_dir = models_dir or default_models_dir()
        self.specs = manifest if manifest is not None else load_manifest()
        self._verified: dict[str, tuple[int, int, bool]] = {}  # id -> (size, mtime_ns, ok)

    def status(self, model_id: str) -> ModelStatus:
        spec = self.specs[model_id]
        path = self.models_dir / spec.file
        try:
            st = path.stat()
        except OSError:
            return ModelStatus(spec, ModelState.MISSING, path)
        expected_sha, expected_size = spec.sha256, spec.size
        sidecar = _read_sidecar(path)
        if not expected_sha:  # converted at build time: the converter wrote "<sha256> <size>" next to it
            if sidecar is None:
                return ModelStatus(spec, ModelState.CORRUPT, path)
            expected_sha, expected_size = sidecar[0], sidecar[1]
        elif sidecar is not None and sidecar[2] == f"fp16w-of:{spec.sha256}":
            # weights stored as float16 by scripts/shrink_models.py from exactly the pinned file
            expected_sha, expected_size = sidecar[0], sidecar[1]
        cached = self._verified.get(model_id)
        if cached is None or cached[:2] != (st.st_size, st.st_mtime_ns):
            ok = st.st_size == expected_size and sha256_of(path) == expected_sha
            cached = (st.st_size, st.st_mtime_ns, ok)
            self._verified[model_id] = cached
        return ModelStatus(spec, ModelState.READY if cached[2] else ModelState.CORRUPT, path)

    def require(self, model_id: str) -> Path:
        status = self.status(model_id)
        if status.state is not ModelState.READY:
            raise ModelUnavailableError(status)
        return status.path

    def all_status(self) -> list[ModelStatus]:
        return [self.status(model_id) for model_id in self.specs]

    def ready(self, purpose: str) -> bool:
        """All models needed for one purpose are present and verified."""
        ids = [i for i, s in self.specs.items() if s.purpose == purpose]
        return bool(ids) and all(self.status(i).state is ModelState.READY for i in ids)


class ModelUnavailableError(RuntimeError):
    def __init__(self, status: ModelStatus) -> None:
        self.status = status
        what = "chưa có" if status.state is ModelState.MISSING else "bị hỏng/không đúng phiên bản"
        super().__init__(f"Mô hình {status.spec.name} {what}: {status.path}")
