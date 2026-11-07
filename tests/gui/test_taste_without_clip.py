"""Without the CLIP model the taste score says the Hợp gu function is off (instead of "not enough data"), naming the
function, not the model (REG-1: model names only in ⚙ → ℹ Giới thiệu)."""

from __future__ import annotations

from pathlib import Path

from app.ai.models import ModelRegistry, load_manifest
from tests.gui.test_main_window import _window, env  # noqa: F401 - fixture


def test_missing_clip_names_the_function(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    w._registry = ModelRegistry(tmp_path / "no-models", load_manifest())
    w.retrain_taste(wait=True)
    assert not w.taste.ready and "Hợp gu" in w.taste.status.reason and "CLIP" not in w.taste.status.reason
