"""Windows Snap sizes (logical px after the taskbar) at 100 / 125 / 150 %: each gives the expected layout mode and no
button text is cut off. On Windows CI this runs with the real `windows` platform and Windows fonts, also with
QT_SCALE_FACTOR 1.25 / 1.5 / 2 (pre-beta review); here it runs offscreen with the Linux fonts."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QAbstractButton, QApplication

from app.ui.layout_modes import Mode
from tests.gui.platform_checks import skip_unless_fits, skip_without_real_fonts
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture

SNAP = {  # name: (width, height, mode)
    "100% full": (1920, 1040, Mode.WIDE), "100% half": (960, 1040, Mode.NARROW),
    "100% quarter": (960, 520, Mode.SHORT), "125% full": (1536, 824, Mode.WIDE),
    "125% half": (768, 824, Mode.NARROW), "125% quarter": (768, 412, Mode.SHORT),
    "150% full": (1280, 680, Mode.MEDIUM), "150% half": (640, 680, Mode.NARROW),
    "150% quarter": (640, 340, Mode.SHORT), "150% third": (426, 680, Mode.TINY),
    "4K 150% top half": (2560, 683, Mode.SHORT), "low strip": (1920, 400, Mode.SHORT),
    "smallest window": (560, 300, Mode.TINY),
}


def clipped_buttons(window) -> list[str]:  # noqa: ANN001
    """Visible buttons whose text (and icon) is wider than the room inside them."""
    out = []
    for b in window.findChildren(QAbstractButton):
        if not (b.isVisibleTo(window) and b.text()):
            continue
        need = b.fontMetrics().horizontalAdvance(b.text().replace("&", ""))
        if not b.icon().isNull():
            need += b.iconSize().width() + 4
        room = b.contentsRect().width() - 6
        if need > room:
            out.append(f"{b.text()!r}: needs {need} px, has {room}")
    return out


@pytest.mark.parametrize("name", list(SNAP))
def test_snap_size_mode_and_no_clipped_buttons(qtbot, env: dict, name: str) -> None:  # noqa: F811
    width, height, mode = SNAP[name]
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.resize(width, height)
    QApplication.processEvents()
    w.layout_controller.evaluate()
    QApplication.processEvents()
    # A third at 150 % (426 px) is below the 560 px minimum window: Windows then shows the window 560 px wide.
    wanted = (max(width, 560), max(height, 300))
    skip_unless_fits(w, wanted)
    assert (w.width(), w.height()) == wanted
    assert w.layout_controller.mode is mode
    skip_without_real_fonts()
    font = w.font()
    assert clipped_buttons(w) == [], (f"{name} ({QApplication.platformName()}, dpr {w.devicePixelRatioF()}, "
                                      f"font {font.family()} {font.pointSizeF()} pt, dpi {w.logicalDpiX()})")
