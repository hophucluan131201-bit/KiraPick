"""Collect Python garbage on the GUI thread only.

Python's automatic collector runs on whichever thread happens to allocate. With Qt thread pools (thumbnails,
histograms, loading the loupe image, learning) that can be a worker thread, and collecting a cycle that holds a
Qt object there destroys it outside the GUI thread — a rare segfault (seen once in a full test run). So the
automatic collector is switched off and a GUI-thread timer runs it with the same generation thresholds.
"""

from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer

THRESHOLD = gc.get_threshold()  # Python's own thresholds (generation 0, 1, 2), kept
INTERVAL_MS = 500

_installed: GuiThreadCollector | None = None


class GuiThreadCollector(QObject):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        gc.disable()
        self.timer = QTimer(self)
        self.timer.setInterval(INTERVAL_MS)
        self.timer.timeout.connect(self.check)
        self.timer.start()

    @staticmethod
    def check() -> None:
        """Same rule as Python's own collector, but here, on the GUI thread."""
        l0, l1, l2 = gc.get_count()
        if l0 > THRESHOLD[0]:
            gc.collect(0)
            if l1 > THRESHOLD[1]:
                gc.collect(1)
                if l2 > THRESHOLD[2]:
                    gc.collect(2)


def install(app: QObject) -> GuiThreadCollector:
    """Once per application (idempotent)."""
    global _installed
    if _installed is None:
        _installed = GuiThreadCollector(app)
    return _installed


def installed() -> GuiThreadCollector | None:
    return _installed
