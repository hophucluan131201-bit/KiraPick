"""Grid, culling and layout timings on synthetic sessions of 1,000 / 5,000 / 10,000 photos (marker `perf`).

Every number is end-to-end on the Qt thread: the call AND the repaint it causes (grid viewport, bottom bar, detail
panel), measured with ``time.perf_counter``. Results are printed and, when KIRAPICK_PERF_OUT names a file, appended
there as JSON lines (the review reads them). Targets come from the UI spec (Task 14).
"""

from __future__ import annotations

import contextlib
import gc
import json
import os
import statistics
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from app.storage.sessions import open_session
from app.storage.project import DB_NAME
from app.ui import gc_guard
from app.ui import main_window as mw
from app.ui.asset_model import Filter, Sort
from tests.perf.synthetic_session import build_session

pytestmark = pytest.mark.perf
SIZES = [1000, 5000, 10000]


def _record(name: str, n: int, **values: float) -> None:
    line = {"name": name, "photos": n, **{k: round(v, 2) for k, v in values.items()}}
    print("\nPERF", json.dumps(line, ensure_ascii=False))
    out = os.environ.get("KIRAPICK_PERF_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def _ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000


def _paint(w) -> None:  # noqa: ANN001
    """What a key press makes Qt draw: the grid, the bottom bar and the detail panel (synchronously)."""
    w.grid.viewport().repaint()
    w.bottom_bar.repaint()
    if w.detail.isVisible():
        w.detail.repaint()


def _rss_mb() -> float:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return float("nan")


@pytest.fixture
def session(qtbot, tmp_path: Path, monkeypatch):  # noqa: ANN001, ANN201
    """(window, root, n): an open window, and a function opening an N-photo session in it (timed by the caller)."""
    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    w = mw.MainWindow(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    w._maximize_on_show = False
    w.resize(1920, 1000)
    w.show()
    w.layout_controller.evaluate()

    def make(n: int) -> Path:
        root = tmp_path / f"photos_{n}"
        build_session(tmp_path / "sessions", root, n).close()
        return root

    yield w, make
    w.close()


def _open(w, root: Path) -> float:  # noqa: ANN001
    t0 = time.perf_counter()
    project, _ = open_session(mw.sessions_dir(), root)
    w._set_project(project, root)
    _paint(w)
    return _ms(t0)


@pytest.mark.parametrize("n", SIZES)
def test_open_filter_sort_scroll(session, n: int) -> None:  # noqa: ANN001
    w, make = session
    root = make(n)
    first_paint = _open(w, root)
    assert w.model.rowCount() == n

    def timed(fn) -> float:  # noqa: ANN001
        t0 = time.perf_counter()
        fn()
        _paint(w)
        return _ms(t0)

    keep_row = next(i for i in range(w.filters.count())
                    if (w.filters.item(i).data(Qt.ItemDataRole.UserRole) or (None,))[0] is Filter.KEEP)
    filter_keep = timed(lambda: w.filters.setCurrentRow(keep_row))
    filter_all = timed(lambda: w.filters.setCurrentRow(0))
    sort_score = timed(lambda: w.sort.setCurrentIndex(w.sort.findData(Sort.SCORE.value)))
    sort_time = timed(lambda: w.sort.setCurrentIndex(w.sort.findData(Sort.TIME.value)))
    scroll = _scroll_with_thumbnails(w, timed)
    w.model.set_device_pixel_ratio(2.0)  # RV13-02: large cards on a 200 % screen
    w.set_grid_cell(340)
    scroll_large = _scroll_with_thumbnails(w, timed)
    _record("open_filter_sort_scroll", n, first_paint_ms=first_paint, filter_keep_ms=filter_keep,
            filter_all_ms=filter_all, sort_score_ms=sort_score, sort_time_ms=sort_time,
            scroll_median_ms=statistics.median(scroll), scroll_worst_ms=max(scroll),
            scroll_340_dpr2_median_ms=statistics.median(scroll_large), scroll_340_dpr2_worst_ms=max(scroll_large))
    limits = {1000: (500, 200), 5000: (1500, 600), 10000: (3000, 1200)}[n]
    assert first_paint <= limits[0]
    assert max(filter_keep, filter_all, sort_score, sort_time) <= limits[1]
    assert statistics.median(scroll) <= 16 and max(scroll) <= 50
    assert statistics.median(scroll_large) <= 16 and max(scroll_large) <= 50


def _scroll_with_thumbnails(w, timed) -> list[float]:  # noqa: ANN001
    """40 page steps, timed on the second pass: the thumbnails of those pages are decoded and cached (the first pass
    would mostly paint "Đang tải…" cards and measure nothing)."""
    bar = w.grid.verticalScrollBar()
    bar.setValue(0)
    positions = [min(bar.maximum(), (step + 1) * w.grid.viewport().height()) for step in range(40)]
    for pos in positions:
        bar.setValue(pos)
        w.grid.viewport().repaint()
        w.model.wait_for_thumbnails(10000)
        QApplication.processEvents()
    bar.setValue(0)
    return [timed(lambda pos=pos: bar.setValue(pos)) for pos in positions]


@pytest.mark.parametrize("n", SIZES)
def test_sustained_culling(session, n: int, monkeypatch) -> None:  # noqa: ANN001
    """RV3-03 / RV10-03: alternating P / X, end-to-end (decision, counts, workflow steps, detail panel, repaint);
    GC pauses of the GUI-thread collector and memory over the run (Task 11 review)."""
    w, make = session
    _open(w, make(n))
    w.select_row(0)
    w.grid.setFocus()
    presses = 200 if n == 10000 else 60
    pauses: list[float] = []
    started: list[float] = []

    def on_gc(phase: str, _info: dict) -> None:
        if phase == "start":
            started.append(time.perf_counter())
        elif started:
            pauses.append(_ms(started.pop()))

    # Where the time of one press goes (to explain an outlier on another machine): each part's duration per press.
    parts: dict[str, float] = {}

    def timed_part(obj, name: str, label: str) -> None:  # noqa: ANN001
        real = getattr(obj, name)

        def wrapper(*a, **k):  # noqa: ANN002, ANN003, ANN202
            t0 = time.perf_counter()
            try:
                return real(*a, **k)
            finally:
                parts[label] = parts.get(label, 0.0) + _ms(t0)

        monkeypatch.setattr(obj, name, wrapper)

    for name in ("_learn_taste", "_show_inspector", "_update_counts", "refresh_steps", "retrain_taste", "step"):
        timed_part(w, name, name.strip("_"))
    timed_part(w.model, "refresh_record", "refresh_record")
    real_transaction = w.project.transaction

    @contextlib.contextmanager
    def timed_transaction():  # noqa: ANN202 - the decision write incl. COMMIT (a WAL checkpoint would land here)
        t0 = time.perf_counter()
        with real_transaction() as conn:
            yield conn
        parts["transaction"] = parts.get("transaction", 0.0) + _ms(t0)

    monkeypatch.setattr(w.project, "transaction", timed_transaction)
    wal = w.project.folder / (DB_NAME + "-wal")

    def wal_size() -> int:
        try:
            return wal.stat().st_size
        except OSError:
            return 0
    gc.callbacks.append(on_gc)
    rss0 = _rss_mb()
    times = []
    slowest: tuple[float, dict[str, float]] = (0.0, {})
    try:
        for i in range(presses):
            parts.clear()
            pauses_before = len(pauses)
            wal_before = wal_size()
            t0 = time.perf_counter()
            w.set_flag("keep" if i % 2 == 0 else "reject")  # what P / X call (auto-advance on)
            t_paint = time.perf_counter()
            _paint(w)
            parts["paint"] = _ms(t_paint)
            times.append(_ms(t0))
            if len(pauses) > pauses_before:
                parts["gc"] = sum(pauses[pauses_before:])
            wal_shrank = wal_size() < wal_before  # the WAL was checkpointed and restarted during this press
            if times[-1] > slowest[0]:  # "other": the decision commit, auto-advance, Qt events in between
                slowest = (times[-1], {**parts, "other": times[-1] - sum(parts.values()),
                                       "wal_checkpoint": float(wal_shrank)})
            if i % 20 == 0:  # the GUI-thread collector runs on its timer; let it run like in real use
                gc_guard.GuiThreadCollector.check()
    finally:
        gc.callbacks.remove(on_gc)
    inspector = []
    for _ in range(30):  # CR9-03: detail refresh (incl. burst lookup) after Chọn / sao / ♥
        rec = w.current_record()
        t0 = time.perf_counter()
        w._show_inspector(rec)
        inspector.append(_ms(t0))
    _record("sustained_culling", n, presses=presses, median_ms=statistics.median(times), worst_ms=max(times),
            p95_ms=sorted(times)[int(len(times) * 0.95)], inspector_median_ms=statistics.median(inspector),
            gc_pauses=len(pauses), gc_pause_median_ms=statistics.median(pauses) if pauses else 0.0,
            gc_pause_worst_ms=max(pauses) if pauses else 0.0, rss_start_mb=rss0, rss_end_mb=_rss_mb())
    _record("sustained_culling_slowest_press", n, total_ms=slowest[0],
            **{f"{k}_ms": v for k, v in sorted(slowest[1].items())})
    assert statistics.median(times) <= 50 and max(times) <= 100
    assert statistics.median(inspector) <= 30


@pytest.mark.parametrize("n", SIZES)
def test_mode_changes_and_short_resize(session, qtbot, n: int) -> None:  # noqa: ANN001
    """Task 12 approval: resize + mode change end-to-end (layout, scroll restore, repaint); SHORT Detail Focus
    resize within the mode."""
    w, make = session
    _open(w, make(n))
    w.select_row(min(n - 1, 4000))
    lc = w.layout_controller
    changes = []
    for size in ((960, 1000), (1920, 484), (580, 400), (1920, 1000)) * 2:
        t0 = time.perf_counter()
        w.resize(*size)
        lc.evaluate()
        _paint(w)
        changes.append(_ms(t0))
    w.resize(1920, 500)
    lc.evaluate()
    lc.toggle_detail()  # SHORT Detail Focus
    short = []
    for height in (420, 540, 460, 520) * 2:
        t0 = time.perf_counter()
        w.resize(1920, height)
        lc.evaluate()
        _paint(w)
        short.append(_ms(t0))
    _record("mode_change", n, median_ms=statistics.median(changes), worst_ms=max(changes),
            short_resize_median_ms=statistics.median(short), short_resize_worst_ms=max(short))
    assert max(changes) <= (150 if n == 10000 else 100)


@pytest.mark.parametrize("n", [10000])
def test_pixmap_cache_memory_at_dpr_2(session, n: int) -> None:  # noqa: ANN001
    """Thumbnails held in memory with the largest cards on a 200 % screen, after scrolling through the session."""
    w, make = session
    _open(w, make(n))
    w.model.set_device_pixel_ratio(2.0)
    w.set_grid_cell(340)
    # A long session: thumbnails of 1,500 photos asked for (scrolling everywhere), more than the cache keeps.
    for row in range(0, 1500):
        w.model.pixmap(w.model.record(w.model.index(row)))
        if row % 100 == 99:
            w.model.wait_for_thumbnails(30000)
            QApplication.processEvents()
    w.model.wait_for_thumbnails(30000)
    QApplication.processEvents()
    pixmaps = list(w.model._pixmaps.values())
    mb = sum(p.width() * p.height() * 4 for p in pixmaps) / 1e6
    _record("pixmap_cache_dpr2", n, pixmaps=len(pixmaps), megabytes=mb, decode_px=w.model.decode_size,
            rss_mb=_rss_mb())
    assert mb <= 300


@pytest.mark.parametrize("n", [10000])
def test_close_and_switch_with_work_running(session, tmp_path: Path, n: int) -> None:  # noqa: ANN001
    """RV9-02 / RV11-V4-02: time of a folder switch and of closing while thumbnail and histogram work is queued."""
    w, make = session
    _open(w, make(n))
    bar = w.grid.verticalScrollBar()
    for step in range(5):  # thumbnails queued
        bar.setValue(step * 2000)
        w.grid.viewport().repaint()
    w.select_row(3)  # histogram queued
    t0 = time.perf_counter()
    assert w._close_session()
    switch = _ms(t0)
    _open(w, make(1000))
    for step in range(5):
        bar.setValue(step * 500)
        w.grid.viewport().repaint()
    t0 = time.perf_counter()
    assert w.close()
    close = _ms(t0)
    _record("close_switch", n, switch_ms=switch, close_ms=close)
    assert switch <= 1000 and close <= 1000


def _long_session(w) -> tuple[list[float], list[float], float]:  # noqa: ANN001
    """2,000 P/X presses with browsing in between; returns (GC pauses ms, RSS samples, seconds)."""
    w.select_row(0)
    pauses: list[float] = []
    started: list[float] = []

    def on_gc(phase: str, _info: dict) -> None:
        if phase == "start":
            started.append(time.perf_counter())
        elif started:
            pauses.append(_ms(started.pop()))

    gc.callbacks.append(on_gc)
    rss = [_rss_mb()]
    bar = w.grid.verticalScrollBar()
    t_start = time.perf_counter()
    try:
        for i in range(2000):
            w.set_flag("keep" if i % 2 == 0 else "reject")
            if i % 50 == 0:  # browse: jump somewhere else, repaint, let timers (incl. the collector) run
                bar.setValue((i * 977) % max(1, bar.maximum()))
                _paint(w)
                w.model.wait_for_thumbnails(10000)
                QApplication.processEvents()
            if i % 500 == 499:
                rss.append(_rss_mb())
    finally:
        gc.callbacks.remove(on_gc)
    return pauses, rss, time.perf_counter() - t_start


@pytest.mark.parametrize("n", [10000])
def test_long_session_gc_and_memory(session, n: int) -> None:  # noqa: ANN001
    """Task 11 review: GC pauses of the GUI-thread collector and memory over a long session (2,000 P/X presses with
    browsing in between, gc_guard on: the collector runs on its own timer through processEvents)."""
    w, make = session
    _open(w, make(n))
    pauses, rss, seconds = _long_session(w)
    _record("long_session", n, presses=2000, seconds=seconds, gc_runs=len(pauses),
            gc_pause_median_ms=statistics.median(pauses) if pauses else 0.0,
            gc_pause_worst_ms=max(pauses) if pauses else 0.0, rss_start_mb=rss[0], rss_end_mb=rss[-1],
            rss_growth_mb=rss[-1] - rss[0])
    assert gc_guard.installed() is not None
    assert (max(pauses) if pauses else 0.0) <= 100


@pytest.mark.parametrize("n", [10000])
def test_long_session_gc_freeze_experiment(session, n: int) -> None:  # noqa: ANN001
    """RV14-03 evidence only (the app does NOT freeze): the same long session after ``gc.collect(); gc.freeze()``
    once the session is open, so full collections skip the objects alive at that point (the 10,000 records, Qt
    wrappers). No target asserted: the numbers are for the reviewer's decision."""
    w, make = session
    _open(w, make(n))
    gc.collect()
    tracked = len(gc.get_objects())
    gc.freeze()
    try:
        pauses, rss, seconds = _long_session(w)
    finally:
        gc.unfreeze()
    _record("long_session_gc_freeze_experiment", n, presses=2000, seconds=seconds, frozen_objects=tracked,
            gc_runs=len(pauses), gc_pause_median_ms=statistics.median(pauses) if pauses else 0.0,
            gc_pause_worst_ms=max(pauses) if pauses else 0.0, rss_growth_mb=rss[-1] - rss[0])
