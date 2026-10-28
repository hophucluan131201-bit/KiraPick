"""Which layout a window of a given client size gets (pure, no Qt).

Coordinates: the main window's CLIENT area in logical pixels, i.e. Qt's QMainWindow.size() — it excludes the
Windows frame and title bar and includes KiraPick's own top and bottom bars.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.layout_modes import (
    DEBOUNCE_MS, HYSTERESIS, MEDIUM_W, MIN_WINDOW, NARROW_DOCK_W, NARROW_W, SHORT_H, STRIP_MAX_H, STRIP_RATIO,
    TINY_H, TINY_W, Mode,
    client_size, detail_docked, detail_visible_default, mode_for,
)


def test_constants() -> None:
    assert (TINY_W, TINY_H, SHORT_H, NARROW_W, MEDIUM_W) == (600, 300, 560, 1100, 1440)
    assert (HYSTERESIS, DEBOUNCE_MS, NARROW_DOCK_W, MIN_WINDOW) == (40, 120, 900, (560, 300))
    assert (STRIP_RATIO, STRIP_MAX_H) == (3.0, 760)


# Client sizes of real Windows Snap layouts (taskbar 48 px; the title bar is outside the client area and is never
# subtracted in code). Computed per scale: logical screen = physical / scale.
SNAP = [
    ("1080p 100% full screen", 1920, 1000, Mode.WIDE),
    ("1080p 100% left half", 960, 1000, Mode.NARROW),
    ("1080p 100% top half", 1920, 484, Mode.SHORT),
    ("1080p 100% quarter", 960, 484, Mode.SHORT),
    ("1080p 125% full screen", 1536, 800, Mode.WIDE),
    ("1080p 125% left half", 768, 800, Mode.NARROW),
    ("1080p 125% top half", 1536, 387, Mode.SHORT),
    ("1080p 150% full screen", 1280, 667, Mode.MEDIUM),
    ("1080p 150% left half", 640, 667, Mode.NARROW),
    ("1080p 150% top half", 1280, 323, Mode.SHORT),
    ("4K 150% full screen", 2560, 1387, Mode.WIDE),
    ("4K 150% top half", 2560, 683, Mode.SHORT),  # a wide strip: SHORT like every other top/bottom half
    ("4K 100% top half", 3840, 1024, Mode.WIDE),  # 1024 px high: room for the column layout
    ("1440p 100% top half", 2560, 664, Mode.SHORT),
    ("ultrawide 3440x1440 top half", 3440, 664, Mode.SHORT),
    ("ultrawide 3440x1440 full screen", 3440, 1360, Mode.WIDE),
    ("super-ultrawide 5120x1440 full screen", 5120, 1360, Mode.WIDE),  # 3.8:1 but tall enough
    ("4K 200% left half", 960, 1040, Mode.NARROW),
    ("4K 200% top half", 1920, 512, Mode.SHORT),
]


@pytest.mark.parametrize(("name", "w", "h", "mode"), SNAP, ids=[s[0] for s in SNAP])
def test_windows_snap_layouts(name: str, w: int, h: int, mode: Mode) -> None:
    assert mode_for(w, h) is mode, name
    assert w >= MIN_WINDOW[0] and h >= MIN_WINDOW[1]  # the minimum size never blocks a snap layout


@pytest.mark.parametrize(("w", "h", "mode"), [
    (600, 800, Mode.NARROW), (599, 800, Mode.TINY),
    (1200, 300, Mode.SHORT), (1200, 299, Mode.TINY),
    (1200, 560, Mode.MEDIUM), (1200, 559, Mode.SHORT),
    (1100, 900, Mode.MEDIUM), (1099, 900, Mode.NARROW),
    (1440, 900, Mode.WIDE), (1439, 900, Mode.MEDIUM),
    (0, 0, Mode.WIDE), (-5, 300, Mode.WIDE),
])
def test_boundaries_and_precedence(w: int, h: int, mode: Mode) -> None:
    assert mode_for(w, h) is mode


def test_hysteresis_keeps_the_current_mode_near_a_threshold() -> None:
    assert mode_for(1120, 900, Mode.NARROW) is Mode.NARROW and mode_for(1141, 900, Mode.NARROW) is Mode.MEDIUM
    assert mode_for(1090, 900, Mode.MEDIUM) is Mode.NARROW  # entering the smaller mode needs no margin
    assert mode_for(1470, 900, Mode.MEDIUM) is Mode.MEDIUM and mode_for(1480, 900, Mode.MEDIUM) is Mode.WIDE
    assert mode_for(1200, 590, Mode.SHORT) is Mode.SHORT and mode_for(1200, 600, Mode.SHORT) is Mode.MEDIUM
    assert mode_for(630, 800, Mode.TINY) is Mode.TINY and mode_for(640, 800, Mode.TINY) is Mode.NARROW


def test_dragging_back_and_forth_over_a_threshold_does_not_flicker() -> None:
    mode = Mode.MEDIUM
    seen = []
    for w in (1105, 1095, 1105, 1110, 1120, 1135, 1130):
        mode = mode_for(w, 900, mode)
        seen.append(mode)
    assert seen == [Mode.MEDIUM] + [Mode.NARROW] * 6


SEQUENCE = [((1920, 1000), Mode.WIDE), ((960, 1000), Mode.NARROW), ((960, 484), Mode.SHORT),
            ((1920, 484), Mode.SHORT), ((1920, 1000), Mode.WIDE)]


def test_snap_sequence_both_directions() -> None:
    """Review CR6-03: full → left half → quarter → top half → full, and back the other way."""
    for steps in (SEQUENCE, list(reversed(SEQUENCE))):
        mode = None
        for (w, h), expected in steps:
            mode = mode_for(w, h, mode)
            assert mode is expected, (w, h)


def test_detail_placement_is_not_visibility() -> None:
    """Review CR6-02: docked/overlay says WHERE the panel goes; whether it is shown is separate."""
    assert detail_docked(Mode.NARROW, 960) and not detail_docked(Mode.NARROW, 768)
    assert not detail_docked(Mode.TINY, 2000)
    assert detail_docked(Mode.WIDE, 1920) and detail_docked(Mode.MEDIUM, 1200) and detail_docked(Mode.SHORT, 1920)
    assert detail_docked(Mode.NARROW, 920, previously_docked=True)
    assert not detail_docked(Mode.NARROW, 930, previously_docked=False) and detail_docked(Mode.NARROW, 940, False)
    # Default visibility (before the user presses Tab): SHORT starts in Grid Focus although its panel is docked.
    assert detail_visible_default(Mode.WIDE, 1920) and detail_visible_default(Mode.MEDIUM, 1200)
    assert not detail_visible_default(Mode.SHORT, 1920)
    assert detail_visible_default(Mode.NARROW, 960) and not detail_visible_default(Mode.NARROW, 768)
    assert not detail_visible_default(Mode.TINY, 2000)


def test_client_size_reads_the_qt_widget_size_not_the_frame(qtbot) -> None:  # noqa: ANN001
    """The value passed to mode_for is QMainWindow.size(): Qt defines it without the window frame / title bar."""
    from PySide6.QtWidgets import QMainWindow

    w = QMainWindow()
    qtbot.addWidget(w)
    w.resize(1920, 484)
    w.show()
    assert client_size(w) == (w.width(), w.height()) == (1920, 484)
    assert w.frameGeometry().height() >= w.height()  # the frame (title bar on Windows) is never inside
    assert mode_for(*client_size(w)) is Mode.SHORT


@pytest.mark.parametrize(("w", "h", "mode"), [
    (2049, 683, Mode.SHORT), (2048, 683, Mode.WIDE),  # strip rule: width >= 3 x height ...
    (2277, 759, Mode.SHORT), (2280, 760, Mode.WIDE),  # ... and height < 760
    (2560, 759, Mode.SHORT), (2560, 760, Mode.WIDE),
    (1280, 667, Mode.MEDIUM),  # 1080p full screen at 150 %: 1.9:1, never SHORT
    (1920, 640, Mode.SHORT), (1919, 640, Mode.WIDE),
])
def test_wide_strip_rule(w: int, h: int, mode: Mode) -> None:
    assert mode_for(w, h) is mode


def test_strip_rule_has_hysteresis_on_both_axes() -> None:
    """While in SHORT the window counts as 40 px lower, for the height rule and for the strip rule."""
    assert mode_for(2000, 683, Mode.SHORT) is Mode.SHORT and mode_for(2000, 683, Mode.WIDE) is Mode.WIDE
    assert mode_for(1930, 683, Mode.SHORT) is Mode.SHORT and mode_for(1928, 683, Mode.SHORT) is Mode.WIDE
    assert mode_for(2560, 790, Mode.SHORT) is Mode.SHORT and mode_for(2560, 800, Mode.SHORT) is Mode.WIDE
    mode = Mode.WIDE
    seen = []
    for w in (2045, 2052, 2040, 2060, 2000, 1990, 2050):  # dragging the width around 3 x 683 = 2049
        mode = mode_for(w, 683, mode)
        seen.append(mode)
    assert seen == [Mode.WIDE, Mode.SHORT, Mode.SHORT, Mode.SHORT, Mode.SHORT, Mode.SHORT, Mode.SHORT]
