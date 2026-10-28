"""Which layout a window of a given content size gets (pure, no Qt)."""

from __future__ import annotations

import pytest

from app.ui.layout_modes import (
    DEBOUNCE_MS, HYSTERESIS, MEDIUM_W, MIN_WINDOW, NARROW_DOCK_W, NARROW_W, SHORT_H, TINY_H, TINY_W, Mode,
    detail_docked, mode_for,
)


def test_constants_match_the_spec() -> None:
    assert (TINY_W, TINY_H, SHORT_H, NARROW_W, MEDIUM_W) == (720, 420, 640, 1100, 1440)
    assert (HYSTERESIS, DEBOUNCE_MS, NARROW_DOCK_W, MIN_WINDOW) == (40, 120, 900, (560, 380))


@pytest.mark.parametrize(("w", "h", "mode"), [
    (1920, 1080, Mode.WIDE), (1536, 864, Mode.WIDE), (1280, 720, Mode.MEDIUM), (960, 1080, Mode.NARROW),
    (1920, 540, Mode.SHORT), (700, 400, Mode.TINY), (0, 0, Mode.WIDE), (-5, 300, Mode.WIDE),
    (3840, 2160, Mode.WIDE),
])
def test_reference_sizes(w: int, h: int, mode: Mode) -> None:
    assert mode_for(w, h) is mode


@pytest.mark.parametrize(("w", "h", "mode"), [
    (720, 800, Mode.NARROW), (719, 800, Mode.TINY),  # TINY below 720 wide
    (1200, 420, Mode.SHORT), (1200, 419, Mode.TINY),  # TINY below 420 high
    (1200, 640, Mode.MEDIUM), (1200, 639, Mode.SHORT),
    (1100, 900, Mode.MEDIUM), (1099, 900, Mode.NARROW),
    (1440, 900, Mode.WIDE), (1439, 900, Mode.MEDIUM),
    (960, 540, Mode.SHORT),  # short wins over narrow: height is the scarcer resource there
])
def test_boundaries_and_precedence(w: int, h: int, mode: Mode) -> None:
    assert mode_for(w, h) is mode


def test_hysteresis_keeps_the_current_mode_near_a_threshold() -> None:
    assert mode_for(1120, 900, Mode.NARROW) is Mode.NARROW
    assert mode_for(1141, 900, Mode.NARROW) is Mode.MEDIUM
    assert mode_for(1090, 900, Mode.MEDIUM) is Mode.NARROW  # entering the smaller mode needs no margin
    assert mode_for(1470, 900, Mode.MEDIUM) is Mode.MEDIUM and mode_for(1480, 900, Mode.MEDIUM) is Mode.WIDE
    assert mode_for(1200, 670, Mode.SHORT) is Mode.SHORT and mode_for(1200, 680, Mode.SHORT) is Mode.MEDIUM
    assert mode_for(750, 800, Mode.TINY) is Mode.TINY and mode_for(760, 800, Mode.TINY) is Mode.NARROW


def test_dragging_back_and_forth_over_a_threshold_does_not_flicker() -> None:
    mode = Mode.MEDIUM
    seen = []
    for w in (1105, 1095, 1105, 1110, 1120, 1135, 1130):  # jitter around 1100
        mode = mode_for(w, 900, mode)
        seen.append(mode)
    assert seen == [Mode.MEDIUM] + [Mode.NARROW] * 6  # one change, no back-and-forth


def test_detail_docked() -> None:
    assert detail_docked(Mode.NARROW, 950) and not detail_docked(Mode.NARROW, 880)
    assert not detail_docked(Mode.TINY, 2000)
    assert detail_docked(Mode.WIDE, 1920) and detail_docked(Mode.MEDIUM, 1200) and detail_docked(Mode.SHORT, 1920)
    assert detail_docked(Mode.NARROW, 920, previously_docked=True)  # stays docked down to 900
    assert not detail_docked(Mode.NARROW, 930, previously_docked=False)  # docks again from 940
    assert detail_docked(Mode.NARROW, 940, previously_docked=False)
