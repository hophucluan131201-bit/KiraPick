"""Stopping background work before the resources it uses go away (closing the app, switching photo folder).

Contract (review CR11-V2-01):
1. Every worker belongs to a tracked owner on the GUI thread: a QThreadPool owned by a widget (viewer, thumbnails,
   histogram, learning), a QThread kept in a window attribute (import, analysis, export, app update), or — once a
   stop was asked and it did not finish in time — the window's ``_retiring`` list. A QThread is never dropped while
   it runs (Qt aborts the process when a running QThread is destroyed).
2. Signal objects the workers report through are children of their owner, so they are always destroyed on the GUI
   thread, by their owner, after the owner's workers are done.
3. Order: ask every worker to stop (cancel flag; queued tasks dropped) → wait, bounded → deliver results already
   queued to the GUI thread → only then close the session database and let objects go.
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
