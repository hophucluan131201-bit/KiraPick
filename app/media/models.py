"""Which model weights Media may load (design §12), on top of the one allow-list shared by every mode.

Media is commercial work. A weight may be loaded here only when configs/model-policy.json marks it ``verified`` for
the ``media`` mode and the file's SHA-256 is pinned there (ModelRegistry checks the hash). Everything else raises
MediaModelNotAllowed before any file is opened. A Media feature with a fallback asks ``available()`` first and uses
its fallback (``fallback_for()``) when the weight is not available. Each load is recorded for report A.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ai.models import ModelRegistry, ModelState, ModelStatus
from app.ai.policy import ModelPolicy, load_model_policy

MODE = "media"


class MediaModelNotAllowed(RuntimeError):
    """A Media code path asked for a weight it may not load (bug, or a weight not cleared yet)."""


@dataclass(frozen=True, slots=True)
class MediaModel:
    id: str
    status: str
    needed_for: str
    fallback: str | None
    block_from: int | None  # milestone from which a weight without fallback, not cleared, blocks the build
    terms: str

    @property
    def loadable(self) -> bool:
        return self.status == "verified"


@dataclass(frozen=True, slots=True)
class MediaModelPolicy:
    models: dict[str, MediaModel]  # weights Media uses (entries with a "media" section)
    never: frozenset[str]  # weights Media may never load: status never, or not usable in the media mode
    shared: ModelPolicy

    def loadable_ids(self) -> list[str]:
        return [m.id for m in self.models.values() if m.loadable]

    def blocking(self, milestone: int) -> list[str]:
        """Weights that block a build at this milestone: needed from then on, no fallback, not cleared."""
        return [m.id for m in self.models.values()
                if not m.loadable and m.block_from is not None and milestone >= m.block_from]


def media_policy(shared: ModelPolicy | None = None) -> MediaModelPolicy:
    shared = shared if shared is not None else load_model_policy()
    models: dict[str, MediaModel] = {}
    never: set[str] = set()
    for e in shared.entries.values():
        if e.media is not None:
            status = e.status if MODE in e.modes else "pending"
            models[e.id] = MediaModel(e.id, status, e.media.get("needed_for", ""), e.media.get("fallback"),
                                      e.media.get("block_from"), e.terms)
        elif e.status == "never" or MODE not in e.modes:
            never.add(e.id)
    return MediaModelPolicy(models, frozenset(never), shared)


class MediaRegistry:
    """Wraps ModelRegistry for Media: refuses weights outside the policy and records what was loaded."""

    def __init__(self, registry: ModelRegistry | None = None, policy: MediaModelPolicy | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.policy = policy or media_policy(self.registry.policy)
        self.loaded: dict[str, str] = {}  # id -> SHA-256 of the file handed out (report A)

    def allowed(self, model_id: str) -> bool:
        model = self.policy.models.get(model_id)
        return model is not None and model.loadable and model_id not in self.policy.never

    def require(self, model_id: str) -> Path:
        if not self.allowed(model_id):
            model = self.policy.models.get(model_id)
            why = ("never allowed in Media" if model_id in self.policy.never
                   else "not used by Media" if model is None else f"status {model.status!r}")
            raise MediaModelNotAllowed(f"Media may not load {model_id}: {why}")
        path = self.registry.require(model_id)
        self.loaded[model_id] = self.registry.file_sha256(model_id, path)
        return path

    def status(self, model_id: str) -> ModelStatus:
        """As ModelRegistry.status, but BLOCKED for any weight Media may not load (so detector loaders that probe an
        optional model, like YOLOX-M, never see one that is not cleared for Media)."""
        status = self.registry.status(model_id)
        if not self.allowed(model_id) and status.state is ModelState.READY:
            return ModelStatus(status.spec, ModelState.BLOCKED, status.path)
        return status

    def available(self, model_id: str) -> bool:
        """Allowed and present with a pinned SHA-256: a feature with a fallback asks this before using a weight."""
        return self.allowed(model_id) and self.registry.status(model_id).state is ModelState.READY

    def fallback_for(self, model_id: str) -> str | None:
        """What a Media feature does instead when this weight is not available (design v5)."""
        model = self.policy.models.get(model_id)
        return model.fallback if model is not None else None

    def report_loaded(self) -> dict[str, dict[str, str]]:
        """Report A: every weight Media really loaded, with its SHA-256 and status."""
        return {i: {"sha256": sha, "status": self.policy.models[i].status} for i, sha in sorted(self.loaded.items())}

    def report_unavailable(self) -> dict[str, dict[str, str | None]]:
        """Weights Media would use that are not available now, with the fallback in use."""
        return {m.id: {"status": m.status, "state": self.registry.status(m.id).state.value, "fallback": m.fallback}
                for m in self.policy.models.values() if not self.available(m.id)}
