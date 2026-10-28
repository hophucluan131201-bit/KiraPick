"""Run Python's cyclic garbage collector on the GUI thread only (workaround for a crash in worker threads).

Evidence (2026-10-28, Python 3.13.17, PySide6 / Qt 6.12.0, Linux offscreen test run): one full test run ended with
"Fatal Python error: Segmentation fault". The faulthandler dump shows the crashing thread in "Garbage-collecting",
entered from ``threading._DummyThread.__init__`` — i.e. a thread created by Qt (a QThreadPool worker) calling into
Python for the first time, and the allocation there triggered an automatic collection. Confirmed: the collector ran
inside a Qt worker thread when the process crashed. Not visible in the dump (hypothesis): which object was being
destroyed; the likely case is a reference cycle holding a Qt object, which Qt does not allow to be destroyed outside
the thread it belongs to.

What this module does: switch off automatic collection and call ``gc.collect`` from a GUI-thread timer. Plain
reference counting is unchanged (most objects are still freed at once); only reference CYCLES wait for the timer.

How the timer decides, compared with CPython 3.12/3.13 (``gc_collect_generations``): it collects the OLDEST generation
whose counter is above its threshold (collecting it also collects the younger ones), using Python's own thresholds
(``gc.get_threshold()``: (700, 10, 10) on 3.12, (2000, 10, 10) on 3.13). Difference: CPython additionally skips a
full (generation 2) collection while the objects that survived recent collections are fewer than 25 % of the
long-lived ones; that counter is not visible from Python, so this timer may run full collections somewhat more
often (a cost in CPU, not in correctness). Timing differs too: at most every ``INTERVAL_MS`` instead of at the
allocation that crossed the threshold, so cycles may live up to that long.

Remaining risk: a long blocking call on the GUI thread delays collection (there are none by design); memory of
cycles created by worker threads is reclaimed later than with automatic GC.
"""

from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer

THRESHOLD = gc.get_threshold()  # Python's own thresholds for this interpreter, kept
INTERVAL_MS = 500

_installed: GuiThreadCollector | None = None


class GuiThreadCollector(QObject):
    def __init__(self, app: QObject) -> None:
        super().__init__(app)
        self._was_enabled = gc.isenabled()
        gc.disable()
        self.timer = QTimer(self)
        self.timer.setInterval(INTERVAL_MS)
        self.timer.timeout.connect(self.check)
        self.timer.start()
        quit_signal = getattr(app, "aboutToQuit", None)
        if quit_signal is not None:  # never leave the process without a collector after the app ends
            quit_signal.connect(uninstall)

    @staticmethod
    def check() -> None:
        counts = gc.get_count()
        for generation in (2, 1, 0):  # the oldest generation over its threshold, like CPython
            if counts[generation] > THRESHOLD[generation]:
                gc.collect(generation)
                return


def install(app: QObject | None) -> GuiThreadCollector | None:
    """Once per application (idempotent). Without an application nothing changes (automatic GC stays on)."""
    global _installed
    if _installed is None and app is not None:
        _installed = GuiThreadCollector(app)
    return _installed if app is not None else None


def uninstall() -> None:
    """Give collection back to Python (application quitting, or tests)."""
    global _installed
    guard, _installed = _installed, None
    if guard is None:
        return
    guard.timer.stop()
    if guard._was_enabled:
        gc.enable()
    gc.collect()
    guard.deleteLater()


def installed() -> GuiThreadCollector | None:
    return _installed
