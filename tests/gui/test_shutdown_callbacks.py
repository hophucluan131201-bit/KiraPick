"""Review CR11-V3-01 / RV11-V3-01: results queued by workers (and the work they start) are all handled while the
session is still open; a running export keeps its owner until it ends."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from app.export import copy_export
from app.storage.project import DB_NAME
from app.ui import main_window as mw
from tests.gui.test_main_window import _import, _photo, _window, env  # noqa: F401 - fixture
from tests.gui.test_shutdown_timeout import _db_open, _watch_db


class _Relay(QObject):
    a = Signal()
    b = Signal()


class _Task(QRunnable):
    def __init__(self, fn) -> None:  # noqa: ANN001
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        self.fn()


def _chain(w: mw.MainWindow, events: list[str], *, through_gate: bool, pool=None) -> threading.Event:  # noqa: ANN001
    """Worker A (viewer pool, held) → callback A starts worker B → callback B reads the session database.

    through_gate=False starts B straight on a tracked pool (default: the learning pool, which closing waits for), as
    a path the gate does not cover would; True starts it through the window's normal API (the histogram request),
    which the gate must refuse."""
    project = w.project
    relay = _Relay(w)
    gate = threading.Event()

    def worker_b() -> None:
        events.append("B done")  # fast: finished before anyone can see it running
        relay.b.emit()

    def callback_a() -> None:
        events.append("callback A")
        if through_gate:
            hist = w.detail.score_card.histogram
            before = hist._pool.activeThreadCount()
            hist.request(1, Path(__file__))  # would start a histogram task if the gate were open
            events.append("B refused" if hist._pool.activeThreadCount() == before and not w._gate.open else "B started")
        else:
            (pool or w._taste_pool).start(_Task(worker_b))

    def callback_b() -> None:
        try:
            project.conn.execute("SELECT COUNT(*) FROM assets").fetchone()
            events.append("callback B ok")
        except sqlite3.ProgrammingError:
            events.append("callback B on closed db")

    relay.a.connect(callback_a)
    relay.b.connect(callback_b)

    def worker_a() -> None:
        gate.wait(30)
        events.append("A done")
        relay.a.emit()

    w.viewer._pool.start(_Task(worker_a))
    return gate


def test_close_handles_callback_chain_before_closing_the_database(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    gate = _chain(w, events, through_gate=False)
    threading.Timer(0.2, gate.set).start()  # A ends during the close's own wait

    assert w.close() is True
    assert events == ["A done", "callback A", "B done", "callback B ok", "db closed"]
    assert not _db_open(project)


def test_folder_switch_handles_callback_chain_first(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    other = tmp_path / "Buổi khác"
    for i in range(2):
        _photo(other / f"IMG_{i:04d}.jpg", 80 + i)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    # B on a pool the folder switch waits for (session work). The learning pool is not session work: its jobs use
    # copied examples and their results read the window's CURRENT session when they arrive.
    gate = _chain(w, events, through_gate=False, pool=w.model._pool)
    threading.Timer(0.2, gate.set).start()

    thread = w.start_import(other)
    assert thread is not None and w.project is not project
    assert events == ["A done", "callback A", "B done", "callback B ok", "db closed"]
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)


def test_gate_refuses_new_work_started_by_a_callback(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    _watch_db(w, events, monkeypatch)
    gate = _chain(w, events, through_gate=True)
    threading.Timer(0.2, gate.set).start()

    assert w.close() is True
    assert events == ["A done", "callback A", "B refused", "db closed"]


def test_settle_needs_a_quiet_pass() -> None:
    """Unit view of the loop: it stops only after a pass that delivered nothing while nothing ran."""
    from app.ui.shutdown import Work, settle

    deliveries = iter([2, 1, 0])  # A's result, then B's result, then nothing
    calls: list[str] = []
    work = Work("x", lambda ms: True, lambda: calls.append("stop"))
    assert settle(lambda: [work], 10, deliver=lambda: next(deliveries)) == []
    assert calls == ["stop", "stop", "stop"]  # three rounds
    busy = iter([1] * 10)
    assert settle(lambda: [work], 10, rounds=3, deliver=lambda: next(busy)) == ["kết quả công việc nền"]


# ------------------------------------------------------------------ export (RV11-V3-01)
def _held_export(qtbot, w: mw.MainWindow, dest: Path, monkeypatch) -> tuple[threading.Event, object]:  # noqa: ANN001
    gate, copying = threading.Event(), threading.Event()
    real = copy_export._copy_exclusive

    def held(src: Path, dest_root: Path, rel: str) -> str:
        copying.set()
        gate.wait(30)
        return real(src, dest_root, rel)

    monkeypatch.setattr(copy_export, "_copy_exclusive", held)
    w.select_row(0)
    w.set_flag("keep")
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(dest))
    dialog.refresh()
    dialog.hide()  # no final message box in tests
    thread = dialog.start_copy()
    assert copying.wait(10)  # the copy is inside a file (a cancel can no longer skip it)
    assert dialog.start_copy() is thread  # a second start never replaces (and drops) the running copy
    return gate, dialog


def _stop_export_when_asked(monkeypatch) -> None:  # noqa: ANN001
    """"Dừng xuất và thoát / đổi thư mục?" → Yes (the question itself: test_review_notes_t15)."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)


def _runs(db: Path) -> int:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0]


def test_close_waits_for_a_running_export_and_records_it(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    db = project.folder / DB_NAME
    gate, dialog = _held_export(qtbot, w, tmp_path / "out", monkeypatch)
    _stop_export_when_asked(monkeypatch)
    real_finished = dialog._finished
    monkeypatch.setattr(dialog, "_finished", lambda result, progress: (events.append("export finished"),
                                                                       real_finished(result, progress)))

    assert w.close() is False and _db_open(project)  # the copy is still running: nothing released
    assert "sao chép ảnh xuất" in w.status.text()
    assert dialog.copy_thread is not None and dialog.copy_thread.isRunning()  # owner kept, thread referenced
    gate.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=10000)
    assert events == ["export finished", "db closed"]
    copied = list((tmp_path / "out").rglob("*.jpg"))
    assert len(copied) == 1 and copied[0].stat().st_size > 0
    assert _runs(db) == 1  # recorded on the open database before it closed


def test_folder_switch_waits_for_a_running_export(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    other = tmp_path / "Buổi khác"
    for i in range(2):
        _photo(other / f"IMG_{i:04d}.jpg", 90 + i)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    db = project.folder / DB_NAME
    gate, dialog = _held_export(qtbot, w, tmp_path / "out", monkeypatch)
    _stop_export_when_asked(monkeypatch)

    monkeypatch.setattr(mw, "SWITCH_WAIT_MS", 50)
    assert w.start_import(other) is None and w.project is project  # refused while copying
    assert dialog.copy_thread.isRunning()
    monkeypatch.setattr(mw, "SWITCH_WAIT_MS", 10000)
    threading.Timer(0.2, gate.set).start()  # ends during the switch's own wait
    assert w.start_import(other) is not None and w.project is not project
    assert events == ["db closed"] and _runs(db) == 1
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)


def test_no_dialog_or_new_download_from_results_while_closing(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """A result delivered during the release pass must not open a dialog (it would run its own event loop and
    let the user act mid-shutdown) or start a download."""
    from PySide6.QtWidgets import QMessageBox

    from app.ui.update_dialog import AppUpdater

    shown: list[str] = []
    for kind in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(QMessageBox, kind, lambda *a, k=kind, **kw: shown.append(k))
    w = _window(qtbot, env)
    w._gate.open = False  # as during settle
    w._on_import_failed("boom")
    updater = AppUpdater(w, gate=w._gate, get_releases=lambda: [])
    updater._failed("offline")
    updater._offer(None)
    started: list[object] = []
    monkeypatch.setattr(updater, "_run", lambda *a: started.append(a))
    updater._install(Path("setup.exe"))
    assert shown == [] and started == []
    w._gate.open = True
    w._on_import_failed("boom")
    assert shown == ["critical"]  # normal behaviour otherwise
