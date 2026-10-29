"""PIL <-> Qt image conversion (safe to call from worker threads: QImage only)."""

from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage


def pil_to_qimage(image: Image.Image) -> QImage:
    rgb = image if image.mode == "RGB" else image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimage = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
    return qimage.copy()  # detach from the Python bytes buffer


_CHUNK = 4 << 20  # bytes copied per step: other threads (the GUI thread) get the GIL between steps


def pil_to_qimage_rgb32(image: Image.Image, turns: int = 0) -> QImage:
    """A 32-bit QImage of ``image`` turned ``turns`` quarter turns clockwise, for a worker thread: Pillow does the
    turn and the packing (it releases the GIL), the copy into the QImage goes in small steps. Qt's own
    convertToFormat / transformed / copy keep the GIL for their whole run (~0.1–0.4 s at 24 MP) and freeze the
    window meanwhile. QPixmap.fromImage then needs no conversion on the GUI thread."""
    turns %= 4
    if turns:
        image = image.transpose((None, Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180,
                                 Image.Transpose.ROTATE_90)[turns])
    alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)
    rgb = image.convert("RGBA" if alpha else "RGB") if image.mode != ("RGBA" if alpha else "RGB") else image
    data = rgb.tobytes("raw", "BGRA" if alpha else "BGRX")  # = Qt's (A)RGB32 in memory (little-endian)
    qimage = QImage(rgb.width, rgb.height, QImage.Format.Format_ARGB32 if alpha else QImage.Format.Format_RGB32)
    if qimage.isNull():
        return qimage
    line = rgb.width * 4
    bits = qimage.bits()
    if qimage.bytesPerLine() == line:
        for start in range(0, len(data), _CHUNK):
            bits[start:start + _CHUNK] = data[start:start + _CHUNK]
    else:  # never for 32-bit images (lines are 4-byte aligned); kept correct anyway
        stride = qimage.bytesPerLine()
        for y in range(rgb.height):
            bits[y * stride:y * stride + line] = data[y * line:(y + 1) * line]
    return qimage
