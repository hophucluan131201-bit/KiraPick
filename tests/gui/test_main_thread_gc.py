"""Garbage is collected on the GUI thread only: Qt objects must never be destroyed from a worker thread
(a full test run crashed with a segfault while Python collected garbage inside a Qt thread-pool worker)."""

from __future__ import annotations

import gc
import threading

from tests.gui.test_main_window import _window, env  # noqa: F401 - fixture


def test_automatic_gc_is_off_and_the_gui_timer_collects(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    from app.ui import gc_guard

    w = _window(qtbot, env)
    assert not gc.isenabled()
    guard = gc_guard.installed()
    assert guard is not None and guard.timer.isActive()
    calls: list[tuple[int, bool]] = []
    real = gc.collect
    monkeypatch.setattr(gc_guard.gc, "collect",
                        lambda gen=2: calls.append((gen, threading.current_thread() is threading.main_thread()))
                        or real(gen))
    # Counters over the generation-0 threshold, as after many allocations. (Allocating objects here is not reliable:
    # CPython's counter also goes DOWN for every container object freed, old ones included, so garbage released by
    # earlier tests can keep it under the threshold — the same rule automatic collection follows.)
    monkeypatch.setattr(gc_guard.gc, "get_count", lambda: (gc_guard.THRESHOLD[0] + 1, 0, 0))
    qtbot.waitUntil(lambda: bool(calls), timeout=3000)
    assert calls[0] == (0, True)  # run by the timer, on the GUI thread
    assert w is not None


def test_check_collects_the_oldest_generation_over_its_threshold(monkeypatch) -> None:
    """Like CPython's gc_collect_generations: the oldest generation whose counter passed its threshold."""
    from app.ui import gc_guard

    calls: list[int] = []
    monkeypatch.setattr(gc_guard.gc, "collect", lambda gen=2: calls.append(gen))
    t0, t1, t2 = gc_guard.THRESHOLD
    for counts, expected in (((t0, t1, t2), []), ((t0 + 1, 0, 0), [0]), ((t0 + 1, t1 + 1, 0), [1]),
                             ((t0 + 1, t1 + 1, t2 + 1), [2]), ((0, 0, t2 + 1), [2])):
        calls.clear()
        monkeypatch.setattr(gc_guard.gc, "get_count", lambda c=counts: c)
        gc_guard.GuiThreadCollector.check()
        assert calls == expected, counts
