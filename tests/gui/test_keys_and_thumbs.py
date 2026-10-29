"""Task 13: HD thumbnails with decode generations (review CR12-03), keys P / K / Tab / Escape, help."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from app.storage import decisions
from app.ui import asset_model
from app.ui.layout_modes import Mode
from tests.gui.test_adaptive_layout import _at
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _long_side(pm) -> int:  # noqa: ANN001
    return 0 if pm is None else max(pm.width(), pm.height())


# ------------------------------------------------------------------ HD thumbnails
def test_hd_thumbnail_for_large_cells(qtbot, env: dict) -> None:  # noqa: F811
    """Cell 300 at DPR 2 → a 600 px thumbnail made from the photo (an 800 px HD file in the session cache); the
    photo itself is only read."""
    before = {p.name: _sha(p) for p in env["photos"].glob("*.jpg")}
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.set_device_pixel_ratio(2.0)
    w.set_grid_cell(300)
    rec = w.model.record(w.model.index(0))
    w.model.pixmap(rec)  # asks for the sharper one
    assert w.model.wait_for_thumbnails(10000)
    qtbot.waitUntil(lambda: _long_side(w.model.pixmap(rec)) >= 600, timeout=5000)
    assert w.model.wait_for_thumbnails(10000)  # the other cards' HD files too
    hd = list((w.project.cache_dir / asset_model.HD_DIR).glob(f"{rec.id}_*.jpg"))
    assert len(hd) == 1 and max(QImage(str(hd[0])).size().toTuple()) == asset_model.HD_LONG_SIDE
    assert not list((w.project.cache_dir / asset_model.HD_DIR).glob("*.part"))
    assert {p.name: _sha(p) for p in env["photos"].glob("*.jpg")} == before  # originals untouched


def test_small_cells_use_the_import_thumbnail(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.set_grid_cell(200)  # DPR 1: no HD needed
    w.model.wait_for_thumbnails()
    assert not (w.project.cache_dir / asset_model.HD_DIR).exists()
    assert w.model.decode_size == asset_model.THUMB_DISPLAY


def test_old_decode_never_overwrites_a_newer_one(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR12-03: results delivered out of order — the older generation (old DPR / smaller cells) arrives
    after the newer one and is dropped; a newer result does replace an older pixmap."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.wait_for_thumbnails()
    m = w.model
    rec = m.record(m.index(0))
    old_gen = m._gen
    m.set_display_size(ratio=2.0)  # a new generation
    new_gen = m._gen
    assert new_gen > old_gen
    big, small = QImage(600, 400, QImage.Format.Format_RGB32), QImage(240, 160, QImage.Format.Format_RGB32)
    m._on_thumb_loaded(rec.id, big, new_gen)
    m._on_thumb_loaded(rec.id, small, old_gen)  # late, from before the change
    assert _long_side(m.pixmap(rec)) == 600
    m._on_thumb_loaded(rec.id, QImage(800, 533, QImage.Format.Format_RGB32), new_gen)  # same generation: fine
    assert _long_side(m.pixmap(rec)) == 800


def test_previous_session_decode_is_dropped(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    """Asset ids restart at 1 in every session: a decode finished for the previous session must not show up."""
    from tests.gui.test_main_window import _photo

    other = tmp_path / "Buổi khác"
    _photo(other / "IMG_0001.jpg", 99)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    stale_gen = w.model._gen
    _import(qtbot, w, other)
    w.model.wait_for_thumbnails()
    rec = w.model.record(w.model.index(0))
    shown = w.model.pixmap(rec)
    w.model._on_thumb_loaded(rec.id, QImage(321, 123, QImage.Format.Format_RGB32), stale_gen)
    assert w.model.pixmap(rec) is shown


def test_unreadable_thumbnail_is_not_decoded_on_every_repaint(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.wait_for_thumbnails()
    m = w.model
    rec = m.record(m.index(0))
    m.set_display_size(ratio=2.0)
    m._on_thumb_loaded(rec.id, QImage(), m._gen)  # this generation could not decode it
    started: list[int] = []
    monkeypatch.setattr(m._pool, "start", lambda task: started.append(task.asset_id))
    for _ in range(3):
        m.pixmap(rec)
    assert started == []


def test_large_card_is_drawn_sharp_at_dpr_2(qtbot, env: dict) -> None:  # noqa: F811
    """The delegate draws in device pixels: a 2× screen gets the 2× thumbnail's detail, not an upscaled 1× one."""
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.set_device_pixel_ratio(2.0)
    w.set_grid_cell(300)
    rec = w.model.record(w.model.index(0))
    w.model.pixmap(rec)
    w.model.wait_for_thumbnails(10000)
    qtbot.waitUntil(lambda: _long_side(w.model.pixmap(rec)) >= 600, timeout=5000)
    delegate = w.grid.itemDelegate()
    target = QPixmap(600, 680)
    target.setDevicePixelRatio(2.0)
    target.fill(Qt.GlobalColor.black)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 300, 340)
    painter = QPainter(target)
    delegate.paint(painter, option, w.model.index(0))
    painter.end()
    image = target.toImage()
    # Neighbouring device pixels inside the picture differ (random-noise photo): real 2× detail. An upscaled 1×
    # thumbnail would repeat each pixel twice.
    y = 2 * 170
    row = [image.pixelColor(x, y).rgb() for x in range(200, 400)]
    pairs_equal = sum(row[i] == row[i + 1] for i in range(0, len(row) - 1, 2))
    assert pairs_equal < len(row) // 4


# ------------------------------------------------------------------ keys
def _focus_grid(w) -> None:  # noqa: ANN001
    w.activateWindow()
    w.grid.setFocus()


def test_p_keeps_like_k(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _focus_grid(w)
    for row, key in ((0, Qt.Key.Key_P), (1, Qt.Key.Key_K)):
        w.select_row(row)
        qtbot.keyClick(w.grid, key)
        assert decisions.get(w.project.conn, w.model.record(w.model.index(row)).id).flag == "keep", key


def test_keys_in_search_box_do_not_cull(qtbot, env: dict) -> None:  # noqa: F811
    """Typing "pX1" + Tab in the search box: the text is typed, no photo is marked, the layout does not change, and
    Tab moves on to the next field (it does not toggle the details)."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    before = [decisions.get(w.project.conn, r.id) for r in w.model.records()]
    detail = w.detail.isVisible()
    w.activateWindow()
    w.search.setFocus()
    qtbot.keyClicks(w.search, "pX1")
    assert w.search.text() == "pX1"
    qtbot.keyClick(w.search, Qt.Key.Key_Tab)
    qtbot.wait(300)  # search timer
    assert [decisions.get(w.project.conn, r.id) for r in w.model.records()] == before[:len(w.model.records())]
    assert w.detail.isVisible() is detail
    from PySide6.QtWidgets import QApplication

    assert QApplication.focusWidget() is not w.search  # Tab moved focus on
    w.search.clear()
    qtbot.wait(300)
    assert [decisions.get(w.project.conn, r.id) for r in w.model.records()] == before


def test_tab_toggles_details_per_mode(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _focus_grid(w)
    assert w.detail.isVisible()
    qtbot.keyClick(w.grid, Qt.Key.Key_Tab)  # WIDE: hide
    assert not w.detail.isVisible()
    qtbot.keyClick(w.grid, Qt.Key.Key_Tab)
    assert w.detail.isVisible()
    _at(qtbot, w, (1920, 484))  # SHORT: Grid Focus ↔ Detail Focus
    _focus_grid(w)
    assert w.layout_controller.mode is Mode.SHORT and not w.detail.isVisible()
    qtbot.keyClick(w.grid, Qt.Key.Key_Tab)
    assert w.detail.isVisible() and not w.grid.isWrapping()
    qtbot.keyClick(w.grid, Qt.Key.Key_Tab)
    assert not w.detail.isVisible() and w.grid.isWrapping()
    _at(qtbot, w, (768, 800))  # NARROW below 900: Tab opens the sheet, Esc closes it
    _focus_grid(w)
    qtbot.keyClick(w.grid, Qt.Key.Key_Tab)
    assert w.layout_controller.sheet.is_open
    from PySide6.QtWidgets import QApplication

    qtbot.keyClick(QApplication.focusWidget() or w.grid, Qt.Key.Key_Escape)
    assert not w.layout_controller.sheet.is_open and not w.detail.isVisible()


def test_escape_closes_the_drawer_while_typing_in_it(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _at(qtbot, w, (960, 1000))
    _focus_grid(w)
    w.layout_controller.open_drawer("people")
    w.people_filter.setFocus()
    qtbot.keyClicks(w.people_filter, "an")
    assert w.people_filter.text() == "an" and w.layout_controller.side.is_open  # letters typed, nothing culled
    qtbot.keyClick(w.people_filter, Qt.Key.Key_Escape)
    assert not w.layout_controller.side.is_open


def test_key_hints_and_help_list_the_new_keys(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    from PySide6.QtWidgets import QMessageBox

    from app.ui.main_window import key_hints_html

    assert "P&nbsp;/&nbsp;K" in key_hints_html(False) and "Tab" in key_hints_html(False)
    assert "P&nbsp;/&nbsp;K" in key_hints_html(True)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    w = _window(qtbot, env)
    w.show_shortcuts()
    assert "P / K   Chọn" in shown[0] and "Tab" in shown[0] and "ô tìm kiếm" in shown[0]


def test_slider_in_short_detail_focus_reaches_the_decoder(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR13-01: the card size chosen with the slider during SHORT Detail Focus reaches every place that
    keeps it — QSettings, the delegate, the layout controller AND the thumbnail decoder — once the grid wraps
    again; switching focus back and forth keeps it; the photos are only read."""
    from PySide6.QtCore import QSettings

    before = {p.name: _sha(p) for p in env["photos"].glob("*.jpg")}
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.set_device_pixel_ratio(2.0)
    w.top_bar.size_slider.setValue(240)
    _at(qtbot, w, (1920, 484))  # SHORT
    lc = w.layout_controller
    lc.toggle_detail()  # Detail Focus: one row of small cards
    assert not w.grid.isWrapping()
    w.top_bar.size_slider.setValue(340)  # the user drags the slider meanwhile
    assert int(QSettings(env["ini"], QSettings.Format.IniFormat).value("grid_cell")) == 340
    lc.toggle_detail()  # back to Grid Focus
    assert w.grid.isWrapping()
    rect = w.grid.visualRect(w.model.index(0))
    assert (rect.width(), rect.height()) == (340, 340 + 40)
    assert w.grid.itemDelegate().cell == 340 and w.model.decode_size >= 680
    rec = w.model.record(w.model.index(0))
    w.model.pixmap(rec)
    w.model.wait_for_thumbnails(10000)
    qtbot.waitUntil(lambda: _long_side(w.model.pixmap(rec)) >= 680, timeout=5000)  # upgraded
    for _ in range(2):  # back and forth: the user's size is kept
        lc.toggle_detail()
        lc.toggle_detail()
        assert w.grid.itemDelegate().cell == 340 and w.model.decode_size >= 680
        assert w.grid.visualRect(w.model.index(0)).width() == 340
    assert {p.name: _sha(p) for p in env["photos"].glob("*.jpg")} == before


def test_decode_size_follows_smaller_cards_and_new_sessions(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    """Review RV13-01: after large cards on a 2× screen, smaller cards lower the decode size again, so a new session
    does not make HD thumbnails it does not need."""
    from tests.gui.test_main_window import _photo

    other = tmp_path / "Buổi khác"
    for i in range(3):
        _photo(other / f"IMG_{i:04d}.jpg", 60 + i)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.set_device_pixel_ratio(2.0)
    w.set_grid_cell(340)
    assert w.model.decode_size == 680
    w.set_grid_cell(140)
    assert w.model.decode_size == 280  # no new decode for cached ones (they are larger), new ones at 280
    _import(qtbot, w, other)
    for r in range(w.model.rowCount()):
        w.model.pixmap(w.model.record(w.model.index(r)))
    w.model.wait_for_thumbnails(10000)
    assert not (w.project.cache_dir / asset_model.HD_DIR).exists()  # 280 px: the import thumbnail is enough
    w.set_grid_cell(340)  # larger again: a new generation, sharper decodes
    assert w.model.decode_size == 680
