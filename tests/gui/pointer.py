"""Pointer moves for GUI tests that behave like a real mouse on every Qt platform (review CR-P2-FINAL-01).

Offscreen, QTest.mouseMove delivers Enter / MouseMove synchronously. On the real `windows` platform it moves the
operating-system cursor and Windows posts the mouse messages: they reach the widget 20–50 ms later through the event
loop (CI diagnostic run 40964432140, scripts/diag_compare_hover.py), and Windows drops a move back to the position it
last reported. A test asserting right after one QTest.mouseMove then sees the state before the move.

Beta readiness BR-01 (CI runs 41154503576, 41157679507, diagnostic S8): the FIRST move of the pointer inside a window
that has just opened produces only Enter, no MouseMove — whatever moves it (QTest, QCursor.setPos, SendInput, after
parking outside, after activating the window: 0 of 10 each); a second move inside the window does (10 of 10). A real
hand sends many moves, so the app is not affected; a test that moves once was. move_pointer therefore moves like a
hand: when the target's window has not delivered a MouseMove yet, or the pointer already rests on the goal, it first
moves to a point a few pixels away INSIDE the target widget, then onto the goal. It returns once the target widget has
really received a MouseMove; it never calls app internals. When nothing arrives, ``last_diag`` says why (popup, mouse
grabber, active window, widget under the cursor) for the assertion.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable

from PySide6.QtCore import QDeadlineTimer, QEvent, QObject, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

last_diag = ""
_moved_windows: weakref.WeakSet[QWidget] = weakref.WeakSet()  # windows that have delivered a MouseMove
_watcher: QObject | None = None


class _Watch(QObject):
    """Remembers every window that has delivered a MouseMove (installed once, for the whole test session)."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.MouseMove and isinstance(obj, QWidget):
            _moved_windows.add(obj.window())
        return False


def _watch() -> None:
    global _watcher
    if _watcher is None:
        _watcher = _Watch()
        QApplication.instance().installEventFilter(_watcher)


class _Seen(QObject):
    """Counts MouseMoves reaching ``widget`` and, separately, any widget of its window."""

    def __init__(self, widget: QWidget) -> None:
        super().__init__()
        self.widget, self.window = widget, widget.window()
        self.moved = False
        self.window_moves = 0

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.MouseMove:
            if obj is self.widget:
                self.moved = True
            if isinstance(obj, QWidget) and obj.window() is self.window:
                self.window_moves += 1
        return False


def move_pointer(widget: QWidget, pos: QPoint | None = None, timeout_ms: int = 2000) -> bool:
    """Move the pointer onto ``widget`` at ``pos`` (default: its centre) with QTest; True once ``widget`` received the
    MouseMove, False after ``timeout_ms`` (see ``last_diag``)."""
    pos = widget.rect().center() if pos is None else pos
    return _move(widget, pos, lambda g: QTest.mouseMove(widget, widget.mapFromGlobal(g)), timeout_ms)


def move_os_cursor(widget: QWidget, pos: QPoint | None = None, timeout_ms: int = 2000) -> bool:
    """The same with the operating-system cursor (QCursor.setPos), as a real mouse moves it."""
    pos = widget.rect().center() if pos is None else pos
    return _move(widget, pos, QCursor.setPos, timeout_ms)


def _wait(done: Callable[[], bool], msecs: int) -> None:
    deadline = QDeadlineTimer(msecs)
    while not done() and not deadline.hasExpired():
        QApplication.processEvents()
        if not done():
            QTest.qWait(2)


def _move(widget: QWidget, pos: QPoint, step: Callable[[QPoint], None], timeout_ms: int) -> bool:
    global last_diag
    goal = widget.mapToGlobal(pos)
    app = QApplication.instance()
    _watch()
    seen = _Seen(widget)
    app.installEventFilter(seen)
    try:
        if widget.window() not in _moved_windows or QCursor.pos() == goal:
            # The first move inside a newly opened window brings only Enter, and a move back to where the pointer
            # rests is dropped: come in like a hand, through a point a few pixels away inside the target itself.
            near = next((pos + d for d in (QPoint(-4, -4), QPoint(4, 4), QPoint(-4, 4), QPoint(4, -4))
                         if widget.rect().contains(pos + d) and widget.mapToGlobal(pos + d) != QCursor.pos()), None)
            if near is not None:
                step(widget.mapToGlobal(near))
                _wait(lambda: widget.window() in _moved_windows, 300)
                seen.moved = False
        step(goal)
        _wait(lambda: seen.moved, timeout_ms)
        if not seen.moved:
            under = QApplication.widgetAt(QCursor.pos())
            popup = QApplication.activePopupWidget()
            grabber = QWidget.mouseGrabber()
            active = QApplication.activeWindow()
            last_diag = (f"no MouseMove on {type(widget).__name__}: cursor {QCursor.pos().toTuple()} goal "
                         f"{goal.toTuple()} under {type(under).__name__ if under else None} (target: {under is widget}) "
                         f"window moves {seen.window_moves} popup {type(popup).__name__ if popup else None} "
                         f"grabber {type(grabber).__name__ if grabber else None} active window "
                         f"{type(active).__name__ if active else None} window active "
                         f"{widget.window().isActiveWindow()}")
        return seen.moved
    finally:
        app.removeEventFilter(seen)

