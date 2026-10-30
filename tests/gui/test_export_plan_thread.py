"""Part 3 Task 9 — planning from another folder in the background: generations, cancel, the shutdown contract
(spec §5). The scan / EXIF / hashing never run on the GUI thread."""

from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, QThread
from PySide6.QtWidgets import QApplication

from app.export import copy_export, hashing
from app.export.formats import ExportFormat
from app.export.layout import Layout
from app.export.sources import ScanCancelled, SourceSpec
from app.ui import jobs
from app.ui import main_window as mw
from app.ui.export_dialog import ExportDialog
from app.ui.jobs import ExportPlanThread, PlanRequest
from tests.fixtures_export import make_export_session
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture
from tests.gui.test_shutdown_timeout import _db_open, _watch_db
from tests.integration.test_import_job import _photo


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    card = tmp_path / "card"
    card.mkdir()
    for name in ("DSC_0001.NEF", "DSC_0001.JPG", "DSC_0003.NEF", "DSC_0004.JPG"):
        shutil.copy2(f.root / name, card / name)
    f.card = card
    f.settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    yield f
    f.project.close()


def external_dialog(qtbot, fx) -> ExportDialog:  # noqa: ANN001
    dialog = ExportDialog(fx.project, [], settings=fx.settings)
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(fx.dest))
    dialog.external_path.setText(str(fx.card))
    dialog.source_external.setChecked(True)  # plans in the background
    return dialog


def wait_plan(qtbot, dialog: ExportDialog) -> None:
    qtbot.waitUntil(lambda: dialog.plan is not None and not dialog.scanning, timeout=20000)


def settle_threads(qtbot, dialog: ExportDialog) -> None:
    dialog._cancel_plans()
    qtbot.waitUntil(lambda: not dialog.plan_threads, timeout=20000)


class SlowScan:
    """scan_external that waits for ``release`` (checking the cancel flag like the real scan)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, slow_calls: int = 1, cancel_delay: float = 0.0) -> None:
        self.real = jobs.scan_external
        self.cancel_delay = cancel_delay  # a slow medium: the stop takes effect only after this
        self.release, self.started = threading.Event(), threading.Event()
        self.calls, self.slow_calls, self.cancelled = 0, slow_calls, 0
        monkeypatch.setattr(jobs, "scan_external", self)

    def __call__(self, root: Path, **kw):  # noqa: ANN003, ANN204
        self.calls += 1
        if self.calls <= self.slow_calls:
            self.started.set()
            while not self.release.is_set():
                if kw["should_cancel"]():
                    time.sleep(self.cancel_delay)
                    self.cancelled += 1
                    raise ScanCancelled("stopped")
                time.sleep(0.005)
        return self.real(root, **kw)


def test_plan_thread_emits_plan(qtbot, fx) -> None:  # noqa: ANN001
    request = PlanRequest((fx.ids["raw_only"],), fx.dest, SourceSpec("external", fx.card), ExportFormat.RAW_JPEG,
                          Layout.SINGLE)
    thread = ExportPlanThread(fx.project.folder, request, 7)
    with qtbot.waitSignal(thread.planned, timeout=20000) as got:
        thread.start()
    thread.wait()
    generation, plan, index = got.args
    assert generation == 7 and index is not None and index.files == 4
    assert [(op.source_relative, op.match) for op in plan.operations] == [("DSC_0003.NEF", "content")]


def test_plan_thread_reports_cancel_and_errors(qtbot, fx) -> None:  # noqa: ANN001
    request = PlanRequest((fx.ids["raw_only"],), fx.dest, SourceSpec("external", fx.root / "nowhere"),
                          ExportFormat.RAW, Layout.SINGLE)
    thread = ExportPlanThread(fx.project.folder, request, 1)
    with qtbot.waitSignal(thread.failed, timeout=20000) as got:
        thread.start()
    thread.wait()
    assert got.args[0] == 1 and "không tìm thấy thư mục nguồn" in got.args[1]
    good = PlanRequest(request.photo_ids, fx.dest, SourceSpec("external", fx.card), request.fmt, request.layout)
    thread = ExportPlanThread(fx.project.folder, good, 2)
    thread.cancel()  # cancelled before it starts: the scan stops at once, failure "" (not an error)
    with qtbot.waitSignal(thread.failed, timeout=20000) as got:
        thread.start()
    thread.wait()
    assert got.args == [2, ""]


def test_late_plan_result_is_dropped(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    slow = SlowScan(monkeypatch)
    dialog = external_dialog(qtbot, fx)
    assert slow.started.wait(10) and dialog.scanning and not dialog.copy_button.isEnabled()
    first = dialog.plan_threads[0]
    dialog.format_buttons[ExportFormat.RAW].setChecked(True)  # a new choice while the first scan runs
    wait_plan(qtbot, dialog)
    assert dialog.plan.options["format"] == "raw"
    shown = dialog.plan
    slow.release.set()  # the first (older) request may finish now: its result must not replace the newer one
    first.wait(10000)
    QApplication.processEvents()
    assert dialog.plan is shown and dialog.plan.options["format"] == "raw"
    assert slow.cancelled == 1  # the older scan was asked to stop and did
    settle_threads(qtbot, dialog)


def test_index_reused_until_the_folder_is_chosen_again(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    slow = SlowScan(monkeypatch, slow_calls=0)
    dialog = external_dialog(qtbot, fx)
    wait_plan(qtbot, dialog)
    for fmt in (ExportFormat.RAW, ExportFormat.JPEG, ExportFormat.RAW_JPEG):
        dialog.format_buttons[fmt].setChecked(True)
        wait_plan(qtbot, dialog)
    assert slow.calls == 1  # format changes re-plan from the same scan
    dialog.set_external_root(fx.card)  # "Chọn…" again: the card may have changed
    wait_plan(qtbot, dialog)
    assert slow.calls == 2
    settle_threads(qtbot, dialog)


def test_stop_scan(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    slow = SlowScan(monkeypatch)
    dialog = external_dialog(qtbot, fx)
    assert slow.started.wait(10)
    assert dialog.stop_scan_button.isVisibleTo(dialog)
    dialog.stop_scan()
    qtbot.waitUntil(lambda: not dialog.plan_threads, timeout=10000)
    assert slow.cancelled == 1 and dialog.plan is None and "dừng quét" in dialog.scan_status.text().lower()
    assert not dialog.copy_button.isEnabled()


def test_no_hashing_on_gui_thread(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    gui = QApplication.instance().thread()
    seen: list[bool] = []

    def guard(real):  # noqa: ANN001, ANN202
        def wrapped(path, **kw):  # noqa: ANN001, ANN003, ANN202
            seen.append(QThread.currentThread() is not gui)
            return real(path, **kw)
        return wrapped

    monkeypatch.setattr(hashing, "sha256_file", guard(hashing.sha256_file))
    monkeypatch.setattr(copy_export, "sha256_file", guard(copy_export.sha256_file))
    dialog = external_dialog(qtbot, fx)
    wait_plan(qtbot, dialog)
    dialog.hide()
    dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    dialog.copy_thread.wait()
    assert seen and all(seen)  # hashed at planning (content proof) and copying (verification), never on the GUI
    settle_threads(qtbot, dialog)


# --- the window's shutdown contract ---------------------------------------------------------------------------------

def _scanning_window(qtbot, env: dict, tmp_path: Path, monkeypatch) -> tuple[object, SlowScan, ExportDialog]:  # noqa: ANN001
    slow = SlowScan(monkeypatch, slow_calls=100, cancel_delay=0.3)
    card = tmp_path / "card"
    _photo(card / "DSC_0000.jpg", 0)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.set_flag("keep")
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(tmp_path / "out"))
    dialog.external_path.setText(str(card))
    dialog.source_external.setChecked(True)
    assert slow.started.wait(10) and dialog.plan_threads
    return w, slow, dialog


def test_close_during_scan_waits_then_closes(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 5000)
    w, slow, dialog = _scanning_window(qtbot, env, tmp_path, monkeypatch)
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    thread = dialog.plan_threads[0]
    names = [work.name for work in w._session_work()]
    assert "quét nguồn xuất ảnh" in names
    w.close()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=10000)
    assert slow.cancelled >= 1 and not thread.isRunning()  # stopped by the shutdown, finished before the database
    assert events == ["db closed"] and not _db_open(project)


def test_switch_folder_during_scan(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    w, slow, dialog = _scanning_window(qtbot, env, tmp_path, monkeypatch)
    other = tmp_path / "Buổi khác"
    _photo(other / "IMG_0001.jpg", 91)
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    thread = dialog.plan_threads[0]
    assert w.start_import(other) is not None and w.project is not project
    assert not thread.isRunning() and slow.cancelled >= 1 and events == ["db closed"]
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)


def test_closing_the_dialog_stops_its_scan(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    slow = SlowScan(monkeypatch)
    dialog = external_dialog(qtbot, fx)
    assert slow.started.wait(10)
    dialog.close()
    qtbot.waitUntil(lambda: not dialog.plan_threads, timeout=10000)
    assert slow.cancelled == 1 and dialog.plan is None
