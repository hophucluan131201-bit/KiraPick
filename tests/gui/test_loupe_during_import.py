"""Owner's report (2026-11-13): while photos are still coming in, the large view went back to "fit" and lost the
zoomed spot every time the grid picked up new photos (the list is reloaded every 1.5 s during an import)."""

from __future__ import annotations

from PySide6.QtCore import Qt

from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture


def test_reload_during_import_keeps_zoom_and_position_in_large_view(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(1)
    _key(qtbot, w, Qt.Key.Key_Plus)  # large view at 100 %
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=10000)
    _key(qtbot, w, Qt.Key.Key_Plus)  # 200 %
    bar = w.viewer.horizontalScrollBar()
    bar.setValue(bar.maximum() // 3)
    zoom, x, y = w.viewer.zoom, bar.value(), w.viewer.verticalScrollBar().value()
    shown = w.current_record().id
    w.reload_preserving_view()  # what the import's timer does when new photos arrive
    qtbot.wait(300)
    assert w.current_record().id == shown and w.center.currentIndex() == 2
    assert w.viewer.zoom == zoom and w.viewer.is_full_resolution_shown()
    assert (bar.value(), w.viewer.verticalScrollBar().value()) == (x, y)
