"""Compare mode, part 2 task 8: long texts never cut off or covering the photo, DPI changes, slow sources, late
callbacks, shutdown with an export and a full decode running, Snap sizes with Compare open."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.quality.rank import Ranked  # noqa: E402
from app.quality.score import Score  # noqa: E402
from app.storage import decisions  # noqa: E402
from app.ui import main_window as mw  # noqa: E402
from app.ui import viewer as viewer_module  # noqa: E402
from app.ui.compare_view import CompareView  # noqa: E402
from tests.gui.test_compare_lifecycle import FakeFull  # noqa: E402
from tests.gui.test_compare_tile import _record  # noqa: E402
from tests.gui.test_compare_window import _mark, _opened  # noqa: E402
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: E402, F401 - fixture
from tests.gui.test_shutdown_timeout import _db_open, _watch_db  # noqa: E402
from tests.integration.test_import_job import _photo  # noqa: E402

LONG = ("mắt hơi mềm vì tiêu cự dài và tốc độ chụp thấp so với chuyển động của người mẫu, tóc che một phần mắt trái, "
        "ánh sáng nền cháy ở góc trên")


def _view(qtbot, tmp_path: Path, size=(560, 380), n=4):  # noqa: ANN001, ANN202
    photos = [_photo(tmp_path / f"A_VERY_LONG_FILE_NAME_FROM_THE_CAMERA_{i:04d}.jpg", 60 + i, size=(900, 600))
              for i in range(n)]
    view = CompareView()
    qtbot.addWidget(view)
    view.resize(*size)
    view.show()
    score = Score(total=71.0, parts={"eyes": 80.0, "focus": 70.0}, confidence=1.0, weaknesses=[LONG])
    recs = [_record(p, asset_id=i + 1, score=score, ranked=Ranked(71.0, 64.0, 68.0), flag="keep", rating=5,
                    favorite=True) for i, p in enumerate(photos)]
    view.show_records(recs, {}, 1)
    view.set_ai_visible(True)
    QApplication.processEvents()
    return view, recs


def test_long_ai_line_is_elided_inside_the_photo_and_never_covers_its_centre(qtbot, tmp_path) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, tmp_path)
    for r in recs:
        tile = view.tile(r.id)
        label, v = tile.ai_label, tile.viewer
        assert label.isVisible() and label.text().endswith("…") and LONG[1:] in label.toolTip()
        rect = label.geometry()
        assert rect.left() >= 0 and rect.right() <= v.width() and rect.bottom() <= v.height()  # inside the photo area
        assert rect.height() <= label.fontMetrics().height() + 12  # one line
        assert not rect.contains(v.rect().center())  # the middle of the photo stays visible


def test_long_header_is_elided_with_the_full_text_in_the_tooltip(qtbot, tmp_path) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, tmp_path)
    for r in recs:
        header = view.tile(r.id).header
        assert header.fontMetrics().horizontalAdvance(header.text()) <= header.width()
        assert r.name in header.toolTip() and "★★★★★" in header.toolTip()
    view.resize(1600, 900)  # room again: the full text comes back
    qtbot.wait(300)
    assert view.tile(1).header.text().startswith("1") and recs[0].name in view.tile(1).header.text()


def test_dpi_change_keeps_true_100_percent(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """Moving the window to a 200 % screen: zoomed tiles re-apply 100 % = one photo pixel per physical pixel."""
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    v = w.compare.tile(ids[0]).viewer
    w.compare._set_active(ids[0])
    v.set_zoom(1.0)
    qtbot.waitUntil(v.is_full_resolution_shown, timeout=10000)
    assert v.transform().m11() == pytest.approx(1.0)
    for tile in w.compare.tiles:
        monkeypatch.setattr(tile.viewer, "devicePixelRatioF", lambda: 2.0)
    w.layout_controller.on_screen_changed(w.screen())
    assert v.zoom == 1.0 and v.transform().m11() == pytest.approx(0.5)
