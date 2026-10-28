"""Review CR11-V2-01: a worker that outlives the wait must never see its resources closed under it.

Each test holds a real worker (QRunnable in the window's own pool, or a QThread) on a gate past the wait limit, then
releases it, and checks the order: worker done → database closed → window closed."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QRunnable, QThread
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QMessageBox

from app.ui import main_window as mw
from tests.gui.test_main_window import _import, _photo, _window, env  # noqa: F401 - fixture


class _Hold(QRunnable):
    def __init__(self, gate: threading.Event, events: list[str], name: str) -> None:
        super().__init__()
        self.gate, self.events, self.name = gate, events, name

    def run(self) -> None:
        self.gate.wait(30)
        self.events.append(f"{self.name} done")


class _Stubborn(QThread):
    """An analysis that ignores cancel until the gate opens (e.g. a long model call)."""

    def __init__(self, gate: threading.Event, events: list[str]) -> None:
        super().__init__()
        self.gate, self.events = gate, events

    def cancel(self) -> None:
        pass

    def run(self) -> None:
        self.gate.wait(30)
        self.events.append("analysis done")


def _watch_db(w: mw.MainWindow, events: list[str], monkeypatch) -> object:  # noqa: ANN001
    project = w.project
    real = project.close
    monkeypatch.setattr(project, "close", lambda: (events.append("db closed"), real())[1])
    return project


def _db_open(project) -> bool:  # noqa: ANN001
    try:
        project.conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - sqlite3.ProgrammingError once closed
        return False


def test_close_waits_without_blocking_then_closes_in_order(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    gate = threading.Event()
    w.viewer._pool.start(_Hold(gate, events, "viewer"))

    t0 = time.monotonic()
    assert w.close() is False  # refused for now…
    assert time.monotonic() - t0 < 1.0  # …after a bounded wait, not until the worker ends
    assert w.isVisible() and _db_open(project) and "đọc ảnh để xem" in w.status.text()
    qtbot.wait(300)  # the window keeps processing events while it waits
    assert events == [] and w.isVisible()
    assert w.isEnabled() and not w.top_bar.isEnabled() and not w.centralWidget().isEnabled()  # nothing new starts
    assert not w.act_auto_update.isEnabled() and not any(s.isEnabled() for s in w.findChildren(QShortcut))
    w.set_flag("keep")  # a decision already on its way still reaches the open database

    gate.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=5000)
    assert events == ["viewer done", "db closed"] and not _db_open(project)


def test_hung_worker_asks_then_quits_without_closing_anything(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    monkeypatch.setattr(mw, "HUNG_AFTER_S", 0.3)
    monkeypatch.setattr(mw.logging, "shutdown", lambda: None)  # keep pytest's log handlers
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    asked: list[list[str]] = []
    exits: list[int] = []
    monkeypatch.setattr(w, "_ask_quit_anyway", lambda left: (asked.append(left), True)[1])
    monkeypatch.setattr(w, "_hard_exit", exits.append)
    gate = threading.Event()
    w.model._pool.start(_Hold(gate, events, "thumbnail"))

    w.close()
    qtbot.waitUntil(lambda: exits == [0], timeout=5000)
    assert asked == [["tạo ảnh nhỏ"]]
    assert events == [] and _db_open(project)  # nothing closed under the running worker before the process ends

    gate.set()  # test cleanup: the worker ends, then the normal close
    assert w.model.wait_for_thumbnails(5000)
    w._shutdown_ready = True
    w.close()
    assert events == ["thumbnail done", "db closed"]


def test_hung_worker_wait_more_then_it_ends(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    monkeypatch.setattr(mw, "HUNG_AFTER_S", 0.2)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    _watch_db(w, events, monkeypatch)
    asked: list[list[str]] = []
    monkeypatch.setattr(w, "_ask_quit_anyway", lambda left: (asked.append(left), False)[1])  # "chờ thêm"
    monkeypatch.setattr(w, "_hard_exit", lambda code: events.append("hard exit"))
    gate = threading.Event()
    w.detail.score_card.histogram._pool.start(_Hold(gate, events, "histogram"))

    w.close()
    qtbot.waitUntil(lambda: len(asked) >= 2, timeout=5000)  # asked again after another HUNG_AFTER_S
    assert w.isVisible()
    gate.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=5000)
    assert events == ["histogram done", "db closed"]


def test_folder_switch_and_reset_refused_while_a_worker_runs(qtbot, env: dict, tmp_path: Path,  # noqa: F811
                                                             monkeypatch) -> None:
    monkeypatch.setattr(mw, "SWITCH_WAIT_MS", 50)
    other = tmp_path / "Buổi khác"
    for i in range(2):
        _photo(other / f"IMG_{i:04d}.jpg", 70 + i)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    deleted: list[Path] = []
    monkeypatch.setattr(mw, "delete_session", lambda base, root: deleted.append(root))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    gate = threading.Event()
    w.model._pool.start(_Hold(gate, events, "thumbnail"))

    assert w.start_import(other) is None
    assert w.project is project and _db_open(project) and "Chưa đổi được thư mục" in w.status.text()
    w.reset_current_folder()
    assert deleted == [] and w.project is project and _db_open(project)

    gate.set()
    assert w.model.wait_for_thumbnails(5000)
    _import(qtbot, w, other)  # now it switches
    assert w.project is not project and events == ["thumbnail done", "db closed"]


def test_analysis_that_ignores_stop_is_kept_until_it_ends(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(mw, "ANALYSIS_STOP_MS", 50)
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    gate = threading.Event()
    thread = _Stubborn(gate, events)
    w.analyze_thread = thread
    thread.start()

    w._stop_analysis()
    assert w.analyze_thread is None and w._retiring == [thread] and thread.isRunning()  # never dropped running
    del thread  # only the window holds it now
    assert w.close() is False and _db_open(project)

    gate.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=5000)
    assert events == ["analysis done", "db closed"]
    qtbot.waitUntil(lambda: w._retiring == [], timeout=2000)  # forgotten once finished (on the GUI thread)
