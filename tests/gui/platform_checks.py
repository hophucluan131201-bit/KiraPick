"""When a GUI test's answer depends on the machine: the screen size of a real platform, or font metrics.

- A real platform (e.g. `windows` on a CI runner) never makes a window larger than its screen; offscreen does.
- Qt's offscreen platform on Windows has no Windows fonts (it reports a "Sans Serif" fallback about 1.7x wider than
  Segoe UI, seen in CI): text-width results there say nothing about the app; they are checked with the real
  `windows` platform instead (CI step "GUI smoke on the real Windows platform")."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication, QWidget


def fits_screen(widget: QWidget, size: tuple[int, int]) -> bool:
    if QApplication.platformName() == "offscreen":
        return True
    screen = widget.screen().availableGeometry()
    return size[0] <= screen.width() and size[1] <= screen.height()


def skip_unless_fits(widget: QWidget, size: tuple[int, int]) -> None:
    if not fits_screen(widget, size):
        screen = widget.screen().availableGeometry()
        pytest.skip(f"{size[0]}x{size[1]} is larger than this screen ({screen.width()}x{screen.height()} available)")


def skip_without_real_fonts() -> None:
    if sys.platform == "win32" and QApplication.platformName() == "offscreen":
        pytest.skip("font-dependent: offscreen on Windows has no Windows fonts; checked on the real windows platform")
