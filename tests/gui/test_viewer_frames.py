"""The viewer after the worker-side conversion (part 2 Task 8, review CR-P2-FINAL additional regression): RGB, grey
and transparent photos, every Xoay xem turn on the preview and on the full-resolution frame, turning again after the
frame arrived, true 100 %, the full frame given back (Compare) — and the Part 1 loupe."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402

from app.ui.viewer import PREVIEW_LONG_SIDE, ImageViewer  # noqa: E402

SIZE = (3000, 2000)  # larger than the preview, so preview and full frame differ


def _marked(path: Path, mode: str) -> Path:
    """A photo with a red block at the top-left corner of the file (20 % of each side)."""
    base = {"RGB": (30, 60, 200), "L": 90, "RGBA": (30, 60, 200, 255)}[mode]
    red = {"RGB": (230, 20, 20), "L": 250, "RGBA": (230, 20, 20, 255)}[mode]
    img = Image.new(mode, SIZE, base)
    ImageDraw.Draw(img).rectangle((0, 0, SIZE[0] // 5, SIZE[1] // 5), fill=red)
    if mode == "RGBA":
        ImageDraw.Draw(img).rectangle((SIZE[0] - 300, SIZE[1] - 300, SIZE[0], SIZE[1]), fill=(0, 0, 0, 0))
    img.save(path, "JPEG" if mode == "RGB" else "PNG", **({"quality": 90} if mode == "RGB" else {}))
    return path


def _corner(turns: int) -> tuple[float, float]:
    """Where the file's top-left block is on screen after ``turns`` clockwise quarter turns (0..1)."""
    return [(0.08, 0.08), (0.92, 0.08), (0.92, 0.92), (0.08, 0.92)][turns % 4]


def _shown(viewer: ImageViewer) -> tuple[tuple[int, int], QColor]:
    pm = viewer._item.pixmap()
    x, y = _corner(viewer._rotation)
    return (pm.width(), pm.height()), pm.toImage().pixelColor(int(x * (pm.width() - 1)), int(y * (pm.height() - 1)))


def _is_marker(color: QColor, mode: str) -> bool:
    return color.red() > 200 and (mode == "L" or color.blue() < 80)


def _viewer(qtbot) -> ImageViewer:  # noqa: ANN001
    v = ImageViewer()
    qtbot.addWidget(v)
    v.resize(900, 700)
    v.show()
    return v


@pytest.mark.parametrize("mode", ["RGB", "L", "RGBA"])
@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_preview_and_full_frame_turned_with_the_right_pixels(qtbot, tmp_path: Path, mode: str, turns: int) -> None:  # noqa: ANN001
    path = _marked(tmp_path / f"p.{'jpg' if mode == 'RGB' else 'png'}", mode)
    v = _viewer(qtbot)
    v.show_photo(path, None, max(SIZE), turns)
    assert v.wait_idle(20000)
    qtbot.waitUntil(lambda: not v._item.pixmap().isNull(), timeout=5000)
    size, color = _shown(v)
    long_side = PREVIEW_LONG_SIDE
    short = round(long_side * 2 / 3)
    assert size == ((long_side, short) if turns % 2 == 0 else (short, long_side))
    assert _is_marker(color, mode), (mode, turns, color.name())
    v.set_zoom(1.0)
    qtbot.waitUntil(v.is_full_resolution_shown, timeout=20000)
    size, color = _shown(v)
    assert size == (SIZE if turns % 2 == 0 else SIZE[::-1])
    assert _is_marker(color, mode), (mode, turns, color.name())
    assert v.zoom_percent() == 100 and v.transform().m11() == pytest.approx(1.0)  # true 100 % at DPR 1
    if mode == "RGBA":  # as before Task 8: the loader flattens to RGB (app.ingest.preview._to_rgb), opaque frame
        img = v._item.pixmap().toImage()
        bx, by = _corner(turns + 2)
        corner = img.pixelColor(int(bx * (img.width() - 1)), int(by * (img.height() - 1)))
        assert not img.hasAlphaChannel() and corner.alpha() == 255


def test_turning_after_the_full_frame_arrived(qtbot, tmp_path: Path) -> None:  # noqa: ANN001
    """The frame came turned once by the worker; Xoay xem twice more turns only the difference, pixels follow."""
    path = _marked(tmp_path / "p.jpg", "RGB")
    v = _viewer(qtbot)
    v.show_photo(path, None, max(SIZE), 1)
    v.set_zoom(1.0)
    qtbot.waitUntil(v.is_full_resolution_shown, timeout=20000)
    assert v._base_turns == 1
    for turns in (2, 3, 0, 1):
        assert v.set_rotation(turns)
        size, color = _shown(v)
        assert size == (SIZE if turns % 2 == 0 else SIZE[::-1]) and _is_marker(color, "RGB"), turns
    v.drop_full(keep_zoom=True)  # Compare gives the frame back: the preview-sized copy keeps the turn
    v.set_rotation(2)
    size, color = _shown(v)
    assert max(size) == PREVIEW_LONG_SIDE and size[0] > size[1] and _is_marker(color, "RGB")


def test_loupe_shows_turned_full_frame(qtbot, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Part 1 loupe (the window's own viewer): E/Z at 100 % on a turned photo, then turned again."""
    from PySide6.QtCore import Qt

    from app.ui import main_window as mw
    from tests.gui.test_main_window import _import, _key, _window

    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    folder = tmp_path / "photos"
    folder.mkdir()
    _marked(folder / "IMG_0001.jpg", "RGB")
    env = {"photos": folder, "ini": str(tmp_path / "s.ini")}
    w = _window(qtbot, env)
    _import(qtbot, w, folder)
    w.select_row(0)
    w.rotate_view()
    w.show_loupe(True)
    _key(qtbot, w, Qt.Key.Key_Z)
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=20000)
    size, color = _shown(w.viewer)
    assert size == SIZE[::-1] and _is_marker(color, "RGB")
    w.rotate_view()
    size, color = _shown(w.viewer)
    assert size == SIZE and _is_marker(color, "RGB") and w.viewer.zoom_percent() == 100
