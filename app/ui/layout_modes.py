"""Which layout the main window uses for its size (pure decision; no Qt import here).

Coordinates: the main window's CLIENT area in logical pixels (after Windows scaling) — exactly Qt's
``QMainWindow.size()``: without the Windows frame and title bar (so no title-bar height is ever assumed),
with KiraPick's own top and bottom bars. The thresholds are set from real Windows Snap layouts:
1080p laptop at 100 / 125 / 150 % — full screen 1920×1000 / 1536×800 / 1280×667, left half 960 / 768 / 640 wide,
top half 484 / 387 / 323 high — and 4K at 150 / 200 % (see tests/unit/test_layout_modes.py).
"""

from __future__ import annotations

from enum import Enum

TINY_W, TINY_H = 600, 300  # below either: grid only, sidebar and details as overlays (no Snap layout gets here)
SHORT_H = 560  # horizontal split (top/bottom half): details below the grid, Grid Focus / Detail Focus
NARROW_W = 1100  # vertical split: icon rail, details docked or overlay, grid first
MEDIUM_W = 1440
HYSTERESIS = 40  # leaving the current mode needs the size to pass its threshold by this much
DEBOUNCE_MS = 120  # apply a mode change only after resizing settled
NARROW_DOCK_W = 900  # in NARROW the details are docked from this width, an overlay sheet below it
MIN_WINDOW = (560, 300)  # below the smallest Snap half (640 wide, 323 high at 150 %)


class Mode(str, Enum):
    WIDE = "wide"
    MEDIUM = "medium"
    NARROW = "narrow"
    SHORT = "short"
    TINY = "tiny"


def _below(value: int, threshold: int, staying: bool) -> bool:
    """Below the threshold; when already in that mode, it is left only past threshold + HYSTERESIS."""
    return value < threshold + (HYSTERESIS if staying else 0)


def mode_for(width: int, height: int, previous: Mode | None = None) -> Mode:
    """First rule that matches: TINY, SHORT, NARROW, MEDIUM, else WIDE. Unknown sizes (≤ 0) → WIDE."""
    if width <= 0 or height <= 0:
        return Mode.WIDE
    if _below(width, TINY_W, previous is Mode.TINY) or _below(height, TINY_H, previous is Mode.TINY):
        return Mode.TINY
    if _below(height, SHORT_H, previous is Mode.SHORT):
        return Mode.SHORT
    if _below(width, NARROW_W, previous is Mode.NARROW):
        return Mode.NARROW
    if _below(width, MEDIUM_W, previous is Mode.MEDIUM):
        return Mode.MEDIUM
    return Mode.WIDE


def client_size(window: object) -> tuple[int, int]:
    """The size ``mode_for`` expects: the window's own Qt size (``width()``, ``height()``), never its frame."""
    return int(window.width()), int(window.height())  # type: ignore[attr-defined]


def detail_visible_default(mode: Mode, width: int) -> bool:
    """Whether the detail panel is shown before the user presses Tab. Placement (``detail_docked``) is separate:
    SHORT has a docked panel but starts in Grid Focus (hidden); TINY and narrow NARROW start with the sheet closed.
    After a Tab press, visibility is the user's choice, kept per mode by the controller (Task 12)."""
    if mode in (Mode.WIDE, Mode.MEDIUM):
        return True
    if mode is Mode.NARROW:
        return detail_docked(mode, width)
    return False


def detail_docked(mode: Mode, width: int, previously_docked: bool | None = None) -> bool:
    """Details in the splitter (True) or as an overlay sheet (False). In NARROW they dock from 900 px;
    once undocked they dock again only from 940 px, so a width near 900 does not flip them."""
    if mode is Mode.TINY:
        return False
    if mode is not Mode.NARROW:
        return True
    return width >= NARROW_DOCK_W + (HYSTERESIS if previously_docked is False else 0)
