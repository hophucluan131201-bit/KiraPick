"""Which layout the main window uses for the size of its content area (pure decision; no Qt here).

Sizes are logical pixels (after Windows scaling), measured on the content area — the window minus title,
top and bottom bars — so the same numbers work from a 1080p laptop at 150 % to a 4K monitor.
"""

from __future__ import annotations

from enum import Enum

TINY_W, TINY_H = 720, 420  # below either: grid only, sidebar and details as overlays
SHORT_H = 640  # horizontal split: details below the grid, Grid Focus / Detail Focus
NARROW_W = 1100  # vertical split: icon rail, details docked or overlay, grid first
MEDIUM_W = 1440
HYSTERESIS = 40  # leaving the current mode needs the size to pass its threshold by this much
DEBOUNCE_MS = 120  # apply a mode change only after resizing settled
NARROW_DOCK_W = 900  # in NARROW the details are docked from this width, an overlay sheet below it
MIN_WINDOW = (560, 380)


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


def detail_docked(mode: Mode, width: int, previously_docked: bool | None = None) -> bool:
    """Details in the splitter (True) or as an overlay sheet (False). In NARROW they dock from 900 px;
    once undocked they dock again only from 940 px, so a width near 900 does not flip them."""
    if mode is Mode.TINY:
        return False
    if mode is not Mode.NARROW:
        return True
    return width >= NARROW_DOCK_W + (HYSTERESIS if previously_docked is False else 0)
