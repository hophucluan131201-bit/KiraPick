"""Stopping background work before the resources it uses go away (closing the app, switching photo folder).

Contract (review CR11-V2-01):
1. Every worker belongs to a tracked owner on the GUI thread: a QThreadPool owned by a widget (viewer, thumbnails,
   histogram, learning), a QThread kept in a window attribute (import, analysis, export, app update), or — once a
   stop was asked and it did not finish in time — the window's ``_retiring`` list. A QThread is never dropped while
   it runs (Qt aborts the process when a running QThread is destroyed).
2. Signal objects the workers report through are children of their owner, so they are always destroyed on the GUI
   thread, by their owner, after the owner's workers are done.
3. Order (``settle``): close the gate (no new worker may start) → ask every worker to stop (cancel flag; queued tasks
   dropped) → wait, bounded → deliver the results workers queued to the GUI thread → repeat until one delivery pass
   finds no queued call and no worker running (bounded number of rounds) → only then close the session database and
   let objects go. Repeating matters: a result delivered in one pass may queue another call (or, without the gate,
   start another worker), and Qt delivers calls queued during a pass only in the next pass.
4. If a worker is still running when the wait ends, nothing is closed or destroyed: switching folder is refused (the
   current session stays open), and closing the window turns into a non-blocking wait (GUI timer); if the worker
   still has not stopped after a while, the user may leave at once — the process ends without running destructors
   (``os._exit``), so no Qt object or connection is torn down under a running worker. Decisions are committed as they
   are made; SQLite recovers an interrupted job at the next open, and import/analysis resume.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QEvent, QObject

SETTLE_ROUNDS = 20  # measured: a folder switch with a two-level worker chain settles in ≤ 5 passes (GUI updates incl.)


@dataclass(frozen=True)
class Work:
    name: str  # what the user is told is still running
    wait: Callable[[int], bool]  # block at most msecs; True once nothing of it runs any more
    stop: Callable[[], None]  # ask it to stop; never blocks


def drain(works: Iterable[Work], msecs: int) -> list[str]:
    """Ask all to stop, then wait for all within ONE budget of ``msecs``. Returns the names still running."""
    works = list(works)
    for w in works:
        w.stop()
    deadline = time.monotonic() + msecs / 1000
    left: list[str] = []
    for w in works:
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        if not w.wait(remaining):
            left.append(w.name)
    return left


def still_running(works: Iterable[Work]) -> list[str]:
    return [w.name for w in works if not w.wait(0)]


class Gate:
    """Shared by the window and the worker owners: while closed, no new worker is started."""

    def __init__(self) -> None:
        self.open = True


class _CountQueuedCalls(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def eventFilter(self, _obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.MetaCall:  # a queued signal → slot call (e.g. a worker's result)
            self.count += 1
        return False


def deliver_queued() -> int:
    """Deliver what is already posted to the GUI thread (no input events, no event loop); return how many queued
    slot calls ran. Calls queued while delivering wait for the next pass (Qt's rule)."""
    app = QCoreApplication.instance()
    if app is None:
        return 0
    counter = _CountQueuedCalls()
    app.installEventFilter(counter)
    try:
        QCoreApplication.sendPostedEvents()
    finally:
        app.removeEventFilter(counter)
    return counter.count


def settle(works: Callable[[], list[Work]], msecs: int, *, rounds: int = SETTLE_ROUNDS,
           deliver: Callable[[], int] = deliver_queued) -> list[str]:
    """Stop, wait, deliver — until a pass delivers nothing while nothing runs. Returns what is still pending
    (nothing may be released then). The caller closes the gate first."""
    for _ in range(rounds):
        left = drain(works(), msecs)
        if left:
            return left
        if deliver() == 0:
            left = still_running(works())
            if not left:
                return []
    return still_running(works()) or ["kết quả công việc nền"]
