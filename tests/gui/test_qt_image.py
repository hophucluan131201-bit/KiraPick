"""pil_to_qimage_rgb32: the worker-side conversion of the viewer (part 2 task 8: no long GUI-thread block)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402

from app.ui import qt_image  # noqa: E402
from app.ui.qt_image import pil_to_qimage_rgb32  # noqa: E402


def _photo() -> Image.Image:
    im = Image.new("RGB", (3, 2), (10, 20, 30))
    im.putpixel((0, 0), (255, 0, 0))  # top-left red
    im.putpixel((2, 1), (0, 0, 255))  # bottom-right blue
    return im


def _rgb(q: QImage, x: int, y: int) -> tuple[int, int, int]:
    c = QColor(q.pixel(x, y))
    return c.red(), c.green(), c.blue()


def test_pixels_and_format() -> None:
    q = pil_to_qimage_rgb32(_photo())
    assert q.format() == QImage.Format.Format_RGB32 and (q.width(), q.height()) == (3, 2)
    assert _rgb(q, 0, 0) == (255, 0, 0) and _rgb(q, 1, 0) == (10, 20, 30) and _rgb(q, 2, 1) == (0, 0, 255)


def test_turns_are_clockwise_like_xoay_xem() -> None:
    q = pil_to_qimage_rgb32(_photo(), 1)  # 90° clockwise: top-left goes to top-right
    assert (q.width(), q.height()) == (2, 3)
    assert _rgb(q, 1, 0) == (255, 0, 0) and _rgb(q, 0, 2) == (0, 0, 255)
    q = pil_to_qimage_rgb32(_photo(), 2)
    assert _rgb(q, 2, 1) == (255, 0, 0) and _rgb(q, 0, 0) == (0, 0, 255)
    q = pil_to_qimage_rgb32(_photo(), 3)
    assert (q.width(), q.height()) == (2, 3) and _rgb(q, 0, 2) == (255, 0, 0) and _rgb(q, 1, 0) == (0, 0, 255)
    assert _rgb(pil_to_qimage_rgb32(_photo(), 4), 0, 0) == (255, 0, 0)


def test_grey_and_alpha_photos() -> None:
    q = pil_to_qimage_rgb32(Image.new("L", (2, 2), 128))
    assert _rgb(q, 1, 1) == (128, 128, 128)
    q = pil_to_qimage_rgb32(Image.new("RGBA", (2, 2), (200, 100, 50, 0)))
    assert q.hasAlphaChannel() and QColor.fromRgba(q.pixel(0, 0)).alpha() == 0


def test_copied_in_steps(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(qt_image, "_CHUNK", 7)  # not a multiple of a pixel or a line: still exact
    im = Image.new("RGB", (5, 4))
    im.putdata([(i * 10 % 256, i * 3, 255 - i) for i in range(20)])
    q = pil_to_qimage_rgb32(im)
    assert all(_rgb(q, x, y) == im.getpixel((x, y)) for x in range(5) for y in range(4))
