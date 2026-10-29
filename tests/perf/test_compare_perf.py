"""Compare mode performance (part 2 task 8, marker `perf`): entering Compare and P / X in it on a 10,000-photo
session, the Qt thread while the pointer sweeps the tiles, and cold preview / full loading of real-size files with
the window's responsiveness measured meanwhile. Numbers only."""

from __future__ import annotations

import shutil
import statistics
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QElapsedTimer, QItemSelectionModel, QSettings, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui import main_window as mw
from tests.perf.test_compare_memory import OWNER, _jpeg
from tests.perf.test_grid_perf import _ms, _open, _paint, _record, session  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


class _Probe:
    """Largest gap of a 10 ms timer: how long the Qt thread was blocked."""

    def __init__(self) -> None:
        self.clock, self.last, self.worst = QElapsedTimer(), 0, 0
        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        now = self.clock.elapsed()
        self.worst = max(self.worst, now - self.last)
        self.last = now

    def __enter__(self) -> _Probe:
        self.clock.start()
        self.last = self.worst = 0
        self.timer.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.timer.stop()


def _mark(w, rows: list[int]) -> None:  # noqa: ANN001
    sel = w.grid.selectionModel()
    sel.clearSelection()
    for r in rows:
        sel.select(w.model.index(r), QItemSelectionModel.SelectionFlag.Select)


def _hover(w, asset_id: int) -> None:  # noqa: ANN001
    QTest.mouseMove(w.compare.back_button, w.compare.back_button.rect().center())
    vp = w.compare.tile(asset_id).viewer.viewport()
    QTest.mouseMove(vp, vp.rect().center())


def test_compare_on_a_large_session(session) -> None:  # noqa: ANN001, F811
    w, make = session
    _open(w, make(10000))
    w.select_row(5000)
    _mark(w, [5000, 5001, 5002, 5003])
    t0 = time.perf_counter()
    assert w.show_compare()
    w.compare.repaint()
    _paint(w)
    enter_ms = _ms(t0)
    ids = [r.id for r in w.compare.records()]
    _hover(w, ids[1])
    times = []
    for i in range(200):  # P / X on the active photo, end to end (decision, tile, counts, panel, repaint)
        t0 = time.perf_counter()
        w.set_flag("keep" if i % 2 == 0 else "reject")
        w.compare.repaint()
        _paint(w)
        times.append(_ms(t0))
    with _Probe() as probe:  # the pointer sweeping the tiles: the active photo changes at every move
        for i in range(40):
            _hover(w, ids[i % 4])
            QApplication.processEvents()
    t0 = time.perf_counter()
    w.leave_compare()
    _paint(w)
    leave_ms = _ms(t0)
    _record("compare_large_session", 10000, enter_ms=enter_ms, px_median_ms=statistics.median(times),
            px_worst_ms=max(times), px_p95_ms=sorted(times)[int(len(times) * 0.95)],
            hover_sweep_worst_block_ms=probe.worst, leave_ms=leave_ms)
    assert enter_ms <= 100
    assert statistics.median(times) <= 50 and max(times) <= 100
    assert probe.worst <= 50


def _cold_files(tmp: Path) -> list[tuple[str, list[Path]]]:
    sets = []
    nefs = sorted(OWNER.glob("*.NEF"))[:4] if OWNER.is_dir() else []
    if len(nefs) == 4:
        folder = tmp / "nef"
        folder.mkdir()
        sets.append(("24mp_nef", [Path(shutil.copy2(p, folder / p.name)) for p in nefs]))
    folder = tmp / "jpg"
    folder.mkdir()
    sets.append(("24mp_jpeg", [_jpeg(folder / f"J{i}.jpg", (6000, 4000), i) for i in range(4)]))
    return sets


def test_cold_preview_and_full_loading(qtbot, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """A fresh window and session per set (nothing cached): Compare on 4 photos — time until every tile shows its
    preview, then 100 % on each tile one after another — with the Qt thread's longest block meanwhile."""
    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    for label, files in _cold_files(tmp_path):
        w = mw.MainWindow(settings=QSettings(str(tmp_path / f"{label}.ini"), QSettings.Format.IniFormat))
        qtbot.addWidget(w)
        w._maximize_on_show = False
        w.resize(1920, 1000)
        w.show()
        w.start_import(files[0].parent)
        qtbot.waitUntil(lambda: w.import_thread is None, timeout=120_000)  # noqa: B023
        w.select_row(0)
        _mark(w, [0, 1, 2, 3])
        tiles = []
        with _Probe() as probe_preview:
            t0 = time.perf_counter()
            assert w.show_compare(), (w.status.text(), w.model.rowCount(), len(w.grid.selectionModel().selectedRows()))
            tiles = [w.compare.tile(r.id) for r in w.compare.records()]
            qtbot.waitUntil(lambda: all(t.viewer.source_label for t in tiles), timeout=60_000)  # noqa: B023
            preview_s = time.perf_counter() - t0
        full = []
        with _Probe() as probe_full:
            for t in tiles:
                w.compare._set_active(t.asset_id)
                t0 = time.perf_counter()
                t.viewer.set_zoom(1.0)
                qtbot.waitUntil(t.viewer.is_full_resolution_shown, timeout=60_000)
                full.append(time.perf_counter() - t0)
        _record(f"compare_cold_{label}", 4, previews_all_s=preview_s, preview_worst_block_ms=probe_preview.worst,
                full_median_s=statistics.median(full), full_worst_s=max(full),
                full_worst_block_ms=probe_full.worst, held_full_mpx=w.compare.full_pixels() / 1e6)
        assert probe_preview.worst < 250 and probe_full.worst < 250  # never a visible freeze
        w.leave_compare()
        w.close()
