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
