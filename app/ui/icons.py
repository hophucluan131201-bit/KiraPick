"""The app's icons: Lucide line icons (ISC; the ones derived from Feather: MIT), kept as SVG files in
``app/assets/icons`` with their licence (``LICENSE.txt``). One drawing style for every control replaces the mixed
emoji, which Windows draws in colour and other systems draw differently (UX-2, owner approval 2026-11-13).

``icon(name)`` gives a QIcon in the theme's text colour (or ``color``), drawn sharp at 1x-3x display scaling, with a
dimmed copy for disabled controls. A missing file gives an empty icon and a warning, never an exception."""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.ui import theme

log = logging.getLogger(__name__)

STROKE = "1.75"
SIZE = 18  # logical px on buttons and menus
DISABLED = "#6b7078"
# the only icons with a colour of their own: what a mark means at a glance (Giữ / Loại / sao / yêu thích)
COLOR_OF = {"check": theme.KEEP, "x": theme.REJECT_ON_BUTTON, "star": theme.STAR, "heart": theme.FAVORITE}


def icons_dir() -> Path:
    """``app/assets/icons`` in the source tree, ``<bundle>/app/assets/icons`` in a packaged build."""
    here = Path(__file__).resolve().parents[1] / "assets" / "icons"
    bundle = Path(getattr(sys, "_MEIPASS", "")) / "app" / "assets" / "icons"
    return bundle if getattr(sys, "_MEIPASS", None) and bundle.is_dir() else here


@lru_cache(maxsize=None)
def _svg(name: str) -> str | None:
    path = icons_dir() / f"{name}.svg"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        log.warning("icon %s missing", name)
        return None


def _pixmap(svg: str, color: str, px: int, filled: bool) -> QPixmap:
    data = svg.replace("currentColor", color).replace('stroke-width="2"', f'stroke-width="{STROKE}"')
    if filled:
        data = data.replace('fill="none"', f'fill="{color}"', 1)
    image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    QSvgRenderer(QByteArray(data.encode("utf-8"))).render(painter, QRectF(0, 0, px, px))
    painter.end()
    return QPixmap.fromImage(image)


@lru_cache(maxsize=None)
def icon(name: str, color: str | None = None, filled: bool = False) -> QIcon:
    """The Lucide icon ``name`` (file stem), stroked in ``color`` (default: its own colour, else the text colour);
    ``filled`` also fills the shape (a set star or heart)."""
    svg = _svg(name)
    result = QIcon()
    if svg is None:
        return result
    color = color or COLOR_OF.get(name, theme.TEXT)
    for scale in (1, 2, 3):
        px = SIZE * scale
        result.addPixmap(_pixmap(svg, color, px, filled), QIcon.Mode.Normal)
        result.addPixmap(_pixmap(svg, DISABLED, px, filled), QIcon.Mode.Disabled)
    return result


def icon_size() -> QSize:
    return QSize(SIZE, SIZE)
