"""Review notes carried into Task 13: marking tint (RV7-01), tick boxes with a filter / a sort order (RV7-02),
filmstrip tooltip (RV7-03), Xoay xem and E-zoom while loading (RV8-01..04), EXIF across sessions (RV9-01), card size
slider (RV10-01)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, QRect, QSettings, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from app.storage import decisions, view
from app.storage.view import rotate_point
from app.ui import viewer as viewer_module
from app.ui.asset_model import Filter
from app.ui.grid import FOOTER
from tests.gui.test_main_window import _import, _photo, _window, env  # noqa: F401 - fixture


def _flag(w, row: int) -> str | None:  # noqa: ANN001
    return decisions.get(w.project.conn, w.model.record(w.model.index(row)).id).flag


def _paint_card(w, row: int, marked: bool) -> QPixmap:  # noqa: ANN001
    delegate = w.grid.itemDelegate()
    cell = delegate.cell
    target = QPixmap(cell, cell + FOOTER)
    target.fill(Qt.GlobalColor.black)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, cell, cell + FOOTER)
    if marked:
        option.state |= QStyle.StateFlag.State_Selected
    p = QPainter(target)
    delegate.paint(p, option, w.model.index(row))
    p.end()
    return target


# ------------------------------------------------------------------ RV7
def test_marking_tint_never_covers_the_photo(qtbot, env: dict) -> None:  # noqa: F811
    """RV7-01: marking tints the card background only; the photo's pixels are never tinted."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(3)  # current = another card, so row 0 has no frame
    w.model.wait_for_thumbnails()
    qtbot.waitUntil(lambda: w.model.pixmap(w.model.record(w.model.index(0))) is not None, timeout=3000)
    plain, marked = _paint_card(w, 0, False).toImage(), _paint_card(w, 0, True).toImage()
    centre = w.grid.itemDelegate()._picture(QRect(3, 3, w.grid.itemDelegate().cell - 6,
                                                  w.grid.itemDelegate().cell + FOOTER - 6)).center()
    assert plain.pixelColor(centre) == marked.pixelColor(centre)  # the photo itself
    assert plain.pixelColor(8, w.grid.itemDelegate().cell + 20) != marked.pixelColor(8, w.grid.itemDelegate().cell + 20)


def _tick(w, row: int, shift: bool = False) -> None:  # noqa: ANN001
    w.on_tick(w.model.record(w.model.index(row)).id, shift)


def test_tick_and_shift_tick_with_keep_filter(qtbot, env: dict) -> None:  # noqa: F811
    """RV7-02: in the "Giữ" filter, unticking a photo changes it at once but the card stays where it is until the
    filter is refreshed (cards never jump away under the mouse while culling); the current photo, the marking and
    the Shift anchor stay right, also after the refresh."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    for row in range(5):
        _tick(w, row)  # Chọn rows 0–4
    keep_row = next(i for i in range(w.filters.count())
                    if (w.filters.item(i).data(Qt.ItemDataRole.UserRole) or (None,))[0] is Filter.KEEP)
    w.filters.setCurrentRow(keep_row)
    names = [r.name for r in w.model.records()]
    assert len(names) == 5
    w.select_row(3)
    current = w.current_record().id
    w.grid.selectionModel().select(w.model.index(4), w.grid.selectionModel().SelectionFlag.Select)
    marked = sorted(r.id for r in w.selected_records())
    _tick(w, 0)  # untick: no longer Chọn
    qtbot.wait(50)
    assert _flag(w, 0) is None and [r.name for r in w.model.records()] == names  # still shown, chip gone
    assert w.current_record().id == current and sorted(r.id for r in w.selected_records()) == marked
    w.reload_preserving_view()  # the app's in-place refresh: now it has left the view (choosing a filter in the
    # sidebar instead starts the new view at its first photo, by design)
    assert [r.name for r in w.model.records()] == names[1:]
    assert w.current_record().id == current and sorted(r.id for r in w.selected_records()) == marked
    _tick(w, 0)  # anchor = first shown (this click unticks it)
    _tick(w, 2, shift=True)  # Shift: rows 0–2 of the view become Chọn, the anchor's card included
    assert [_flag(w, r) for r in range(3)] == ["keep", "keep", "keep"]
    assert w.current_record().id == current


def test_shift_tick_follows_sorted_order(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    """RV7-02: Shift+tick covers the cards between the two ticks AS SHOWN (capture time here), not by file name or
    database id."""
    folder = tmp_path / "Thứ tự"
    for i, second in enumerate((50, 10, 40, 20, 30)):  # names and times in different orders
        _photo(folder / f"IMG_{i:04d}.jpg", 300 + i, taken=f"2026:10:25 19:00:{second:02d}")
    w = _window(qtbot, env)
    _import(qtbot, w, folder)
    shown = [r.name for r in w.model.records()]
    assert shown == ["IMG_0001.jpg", "IMG_0003.jpg", "IMG_0004.jpg", "IMG_0002.jpg", "IMG_0000.jpg"]
    _tick(w, 1)  # IMG_0003
    _tick(w, 3, shift=True)  # … IMG_0002
    kept = sorted(w.model.record(w.model.index(r)).name for r in range(5) if _flag(w, r) == "keep")
    assert kept == ["IMG_0002.jpg", "IMG_0003.jpg", "IMG_0004.jpg"]


def test_filmstrip_tooltip_has_status(qtbot, env: dict) -> None:  # noqa: F811
    """RV7-03: filmstrip cards have no chip; their tooltip carries it."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(1)
    w.set_flag("keep")
    tip = w.filmstrip.model().index(1, 0).data(Qt.ItemDataRole.ToolTipRole)
    assert "Chọn" in tip and w.model.record(w.model.index(1)).relative_path in tip


# ------------------------------------------------------------------ RV8
def _loupe(qtbot, w, row: int = 0):  # noqa: ANN001, ANN202
    w.select_row(row)
    w.model.wait_for_thumbnails()
    w.show_loupe(True)
    return w.current_record()


def test_fast_rotations_while_loading_keep_the_latest(qtbot, env: dict) -> None:  # noqa: F811
    """RV8-01: several Xoay xem presses while the preview loads — the last rotation wins, no stale result."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    rec = _loupe(qtbot, w)
    for _ in range(3):
        w.rotate_view()
    assert w.viewer.wait_idle(10000)
    qtbot.wait(100)
    assert view.rotation(w.project.conn, rec.id) == 3 and w.viewer._rotation == 3
    width, height = w.viewer.pixmap_size()
    assert height > width  # a landscape photo turned 270° is shown upright-portrait


def test_four_turns_back_to_zero(qtbot, env: dict) -> None:  # noqa: F811
    """RV8-03."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    rec = _loupe(qtbot, w)
    for _ in range(4):
        w.rotate_view()
    assert view.rotation(w.project.conn, rec.id) == 0 and w.current_record().rotation == 0
    assert w.project.conn.execute("SELECT COUNT(*) FROM view_rotation").fetchone()[0] == 0
    assert w.viewer.wait_idle(10000)
    qtbot.wait(50)
    width, height = w.viewer.pixmap_size()
    assert width > height


def _centre(w) -> tuple[float, float]:  # noqa: ANN001
    v = w.viewer
    pm = v._item.pixmap()
    c = v.mapToScene(v.viewport().rect().center())
    return c.x() / pm.width(), c.y() / pm.height()


def test_rotation_while_zoomed_keeps_the_same_spot(qtbot, env: dict) -> None:  # noqa: F811
    """RV8-04 (documented behaviour): Xoay xem on a zoomed photo turns it in place — no reload — and the photo
    point that was in the middle of the window stays in the middle, now at its turned position."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _loupe(qtbot, w)
    w.viewer.set_zoom(4.0, QPointF(0.25, 0.3))  # deep enough that the turned photo is larger than the window
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=10000)
    x0, y0 = _centre(w)
    assert (x0, y0) == pytest.approx((0.25, 0.3), abs=0.03)
    w.rotate_view()
    assert w.viewer.zoom == 4.0 and w.viewer.is_full_resolution_shown()  # turned in place
    assert _centre(w) == pytest.approx(rotate_point(x0, y0, 1), abs=0.03)


def test_user_pan_after_eye_zoom_is_not_overridden(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """RV8-02: E zooms to a point while the full image loads; if the user pans meanwhile, the full image arriving
    later keeps the user's view instead of jumping back to the eyes."""
    gate = threading.Event()
    real = viewer_module.load_full_resolution
    monkeypatch.setattr(viewer_module, "load_full_resolution", lambda p, **k: (gate.wait(10), real(p, **k))[1])
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _loupe(qtbot, w)
    qtbot.wait(100)
    w.viewer.set_zoom(4.0, QPointF(0.85, 0.85))  # E: the eyes, bottom right
    assert not w.viewer.is_full_resolution_shown()
    qtbot.mousePress(w.viewer.viewport(), Qt.MouseButton.LeftButton)  # the user grabs the photo …
    w.viewer.horizontalScrollBar().setValue(w.viewer.horizontalScrollBar().minimum())  # … and pans to the left
    w.viewer.verticalScrollBar().setValue(w.viewer.verticalScrollBar().minimum())
    qtbot.mouseRelease(w.viewer.viewport(), Qt.MouseButton.LeftButton)
    panned = _centre(w)
    gate.set()
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=10000)
    assert _centre(w) == pytest.approx(panned, abs=0.05) and _centre(w)[0] < 0.6


# ------------------------------------------------------------------ RV9
def test_exif_folds_when_switching_to_another_session_with_the_same_asset_id(qtbot, env: dict,  # noqa: F811
                                                                             tmp_path: Path) -> None:
    other = tmp_path / "Buổi khác"
    _photo(other / "IMG_0001.jpg", 77)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    first_id = w.current_record().id
    w.detail.open_exif()
    assert not w.detail.exif_section.collapsed
    _import(qtbot, w, other)
    w.select_row(0)
    assert w.current_record().id == first_id  # ids restart in every session
    assert w.detail.exif_section.collapsed


# ------------------------------------------------------------------ RV10
@pytest.mark.parametrize("size", [140, 220, 340])
def test_size_slider_140_to_340(qtbot, env: dict, size: int) -> None:  # noqa: F811
    """RV10-01: the card really has that size on screen (visualRect), columns follow, the tick box still hits,
    the size is saved and restored, thumbnails are drawn after the change."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.top_bar.size_slider.setValue(size)
    qtbot.wait(50)
    rect = w.grid.visualRect(w.model.index(0))
    assert (rect.width(), rect.height()) == (size, size + FOOTER)
    second = w.grid.visualRect(w.model.index(1))
    columns = w.grid.viewport().width() // (second.left() - rect.left())
    assert columns == w.grid.viewport().width() // (size + 2 * w.grid.spacing())
    tick = w.grid.itemDelegate().tick_rect(rect)
    assert rect.contains(tick)
    before = _flag(w, 0)
    qtbot.mouseClick(w.grid.viewport(), Qt.MouseButton.LeftButton, pos=tick.center())
    assert _flag(w, 0) != before  # the click on the box toggled Chọn
    w.model.wait_for_thumbnails()
    qtbot.waitUntil(lambda: w.model.pixmap(w.model.record(w.model.index(0))) is not None, timeout=3000)
    from app.ui.top_bar import CELL_DEFAULT

    assert int(QSettings(env["ini"], QSettings.Format.IniFormat).value("grid_cell", CELL_DEFAULT)) == size
    w.close()
    w2 = _window(qtbot, env)
    assert w2.top_bar.size_slider.value() == size and w2.grid.itemDelegate().cell == size
