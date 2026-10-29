"""Pointer moves for GUI tests that behave like a real mouse on every Qt platform (review CR-P2-FINAL-01).

Offscreen, QTest.mouseMove delivers Enter / MouseMove synchronously. On the real `windows` platform it moves the
operating-system cursor and Windows posts the mouse messages: they reach the widget 20–50 ms later through the event
loop (CI diagnostic run 40964432140, scripts/diag_compare_hover.py). A test asserting right after QTest.mouseMove
then sees the state before the move. move_pointer waits until the target widget has really received the MouseMove,
so the assertions that follow check what the user gets once the pointer is there; it never calls app internals.
"""

from __future__ import annotations

from PySide6.QtCore import QDeadlineTimer, QEvent, QObject, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget


class _Seen(QObject):
    def __init__(self, widget: QWidget) -> None:
        super().__init__()
        self.widget, self.moved = widget, False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if obj is self.widget and event.type() == QEvent.Type.MouseMove:
            self.moved = True
        return False


def move_pointer(widget: QWidget, pos: QPoint | None = None, timeout_ms: int = 2000) -> bool:
    """Move the pointer onto ``widget`` at ``pos`` (default: its centre) with QTest and return once ``widget``
    received the MouseMove (True), or after ``timeout_ms`` (False: the platform sent nothing, e.g. the pointer was
    already there)."""
    pos = widget.rect().center() if pos is None else pos
    return _move(widget, lambda: QTest.mouseMove(widget, pos), timeout_ms)


def move_os_cursor(widget: QWidget, pos: QPoint | None = None, timeout_ms: int = 2000) -> bool:
    """The same with the operating-system cursor (QCursor.setPos), as a real mouse moves it."""
    pos = widget.rect().center() if pos is None else pos
    return _move(widget, lambda: QCursor.setPos(widget.mapToGlobal(pos)), timeout_ms)


def _move(widget: QWidget, move, timeout_ms: int) -> bool:  # noqa: ANN001
    seen = _Seen(widget)
    widget.installEventFilter(seen)
    try:
        move()
        deadline = QDeadlineTimer(timeout_ms)
        while not seen.moved and not deadline.hasExpired():
            QApplication.processEvents()
            if not seen.moved:
                QTest.qWait(2)
        return seen.moved
    finally:
        widget.removeEventFilter(seen)

