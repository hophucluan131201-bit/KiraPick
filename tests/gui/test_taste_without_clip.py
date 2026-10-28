"""Without the CLIP model the taste score says so (instead of "not enough data")."""

from __future__ import annotations

from pathlib import Path

from app.ai.models import ModelRegistry, load_manifest
from tests.gui.test_main_window import _window, env  # noqa: F401 - fixture


def test_missing_clip_is_named(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    w._registry = ModelRegistry(tmp_path / "no-models", load_manifest(), override_dir=None)
    w.retrain_taste(wait=True)
    assert not w.taste.ready and "CLIP" in w.taste.status.reason
