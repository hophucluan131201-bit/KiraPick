"""Which model weights Media may load, and a registry that refuses everything else (design §12).

Media is commercial work: ArcFace, TOPIQ and the other non-commercial weights shipped for Chụp cá nhân must never be
loaded here. Every load goes through MediaRegistry.require(); a weight outside configs/media-models.json, or not yet
cleared (status "pending"), raises MediaModelNotAllowed before any file is opened. Each load is recorded with its
SHA-256 for the self-test's report A (what Media really loaded).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.ai.models import ModelRegistry, sha256_of

_ROOT = Path(__file__).resolve().parents[2]
MEDIA_MODELS_PATH = _ROOT / "configs" / "media-models.json"
ALLOWED_STATUSES = frozenset({"verified", "approved_with_risk"})
STATUSES = frozenset({"verified", "approved_with_risk", "pending", "not_used"})


class MediaModelNotAllowed(RuntimeError):
    """A Media code path asked for a weight it may not load (bug, or a weight not cleared yet)."""


@dataclass(frozen=True, slots=True)
class MediaModel:
    id: str
    status: str
    needed_for: str
    fallback: str | None
    block_from: int | None  # milestone from which a pending weight without fallback blocks the build
    terms: str

    @property
    def loadable(self) -> bool:
        return self.status in ALLOWED_STATUSES


@dataclass(frozen=True, slots=True)
class MediaModelPolicy:
    models: dict[str, MediaModel]
    never: frozenset[str]

    def loadable_ids(self) -> list[str]:
        return [m.id for m in self.models.values() if m.loadable]

    def blocking(self, milestone: int) -> list[str]:
        """Weights that block a build at this milestone: needed from then on, no fallback, not cleared."""
        return [m.id for m in self.models.values()
                if not m.loadable and m.block_from is not None and milestone >= m.block_from]


def load_policy(path: Path = MEDIA_MODELS_PATH) -> MediaModelPolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    models: dict[str, MediaModel] = {}
    for m in data["models"]:
        model = MediaModel(m["id"], m["status"], m["needed_for"], m.get("fallback"), m.get("block_from"), m["terms"])
        if model.status not in STATUSES:
            raise ValueError(f"{model.id}: unknown status {model.status!r}")
        if model.id in models:
            raise ValueError(f"{model.id}: listed twice")
        models[model.id] = model
    never = frozenset(data.get("never", []))
    clash = never & {m.id for m in models.values() if m.loadable}
    if clash:
        raise ValueError(f"never-allowed weights marked loadable: {sorted(clash)}")
    return MediaModelPolicy(models, never)


class MediaRegistry:
    """Wraps ModelRegistry for Media: refuses weights outside the policy and records what was loaded."""

    def __init__(self, registry: ModelRegistry | None = None, policy: MediaModelPolicy | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.policy = policy or load_policy()
        self.loaded: dict[str, str] = {}  # id -> SHA-256 of the file handed out (report A)

    def allowed(self, model_id: str) -> bool:
        model = self.policy.models.get(model_id)
        return model is not None and model.loadable and model_id not in self.policy.never

    def require(self, model_id: str) -> Path:
        if not self.allowed(model_id):
            model = self.policy.models.get(model_id)
            why = ("never allowed in Media (non-commercial or not needed)" if model_id in self.policy.never
                   else "not in configs/media-models.json" if model is None else f"status {model.status!r}")
            raise MediaModelNotAllowed(f"Media may not load {model_id}: {why}")
        path = self.registry.require(model_id)
        self.loaded[model_id] = sha256_of(path)
        return path

    def available(self, model_id: str) -> bool:
        """Allowed and present (verified by SHA-256): a feature with a fallback asks this before using a weight."""
        if not self.allowed(model_id):
            return False
        from app.ai.models import ModelState

        return self.registry.status(model_id).state is ModelState.READY

    def report_loaded(self) -> dict[str, dict[str, str]]:
        """Report A: every weight Media really loaded, with its SHA-256 and licence status."""
        return {i: {"sha256": sha, "status": self.policy.models[i].status} for i, sha in sorted(self.loaded.items())}
