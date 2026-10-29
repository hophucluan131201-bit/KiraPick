"""Real RAW folder, cold cache (review RV14-02): import time, first paint, time until the visible cards have their
HD thumbnails at 340 px on a 200 % screen, and how long the Qt thread is ever blocked meanwhile (a 10 ms timer's
largest gap) — alone and with the AI analysis running (CPU here; no GPU in this container). Marker `perf`. Photos
are copied, the copies only read; only timings are reported, never photo content."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QElapsedTimer, QSettings, QTimer

from app.ui import asset_model
from tests.perf.test_grid_perf import _record
from tests.perf.test_hd_perf import RAW_DIRS, ROOT

pytestmark = pytest.mark.perf
RAW_EXTS = {".nef", ".arw", ".cr3", ".cr2", ".dng", ".raf", ".orf", ".rw2", ".pef", ".rwl", ".srw"}
EXTRA = [ROOT / "test_photos" / "public"]


def _sources() -> list[Path]:
    return [p for d in (*RAW_DIRS, *EXTRA) if d.is_dir() for p in sorted(d.iterdir()) if p.suffix.lower() in RAW_EXTS]


class _Probe:
    """Largest gap between ticks of a 10 ms timer: how long the Qt thread was blocked."""

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
        self.last, self.worst = 0, 0
        self.timer.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.timer.stop()


def _visible_rows(w) -> list[int]:  # noqa: ANN001
    view = w.grid.viewport().rect()
    return [r for r in range(w.model.rowCount()) if w.grid.visualRect(w.model.index(r)).intersects(view)]


def _hd_wait(qtbot, w, probe: _Probe) -> tuple[float, int]:  # noqa: ANN001
    """Card size 340 at 200 %: seconds until every visible card's HD decode has arrived."""
    t0 = time.perf_counter()
    with probe:
        w.set_grid_cell(340)
        w.grid.viewport().update()
        qtbot.wait(50)
        rows = _visible_rows(w)
        qtbot.waitUntil(lambda: not w.model._pending and all(
            w.model._pix_gen.get(w.model.record(w.model.index(r)).id, -1) >= w.model._gen for r in rows),
            timeout=600_000)
    return time.perf_counter() - t0, len(rows)


def _shoot_and_window(qtbot, tmp_path: Path, monkeypatch):  # noqa: ANN001, ANN202
    from app.ui import main_window as mw

    shoot = tmp_path / "shoot"
    shoot.mkdir()
    for i, src in enumerate(_sources()):
        shutil.copy2(src, shoot / f"R{i:03d}{src.suffix}")
    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    w = mw.MainWindow(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    w._maximize_on_show = False
    w.resize(1920, 1000)
    w.show()
    w.model.set_device_pixel_ratio(2.0)
    return shoot, w


@pytest.mark.skipif(not _sources(), reason="no RAW samples in test_photos/ (git-ignored, not in CI)")
def test_real_raw_cold_cache_and_first_scroll(qtbot, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    shoot, w = _shoot_and_window(qtbot, tmp_path, monkeypatch)

    probe = _Probe()
    t0 = time.perf_counter()
    with probe:
        w.start_import(shoot)
        qtbot.waitUntil(lambda: w.import_thread is None, timeout=600_000)
    import_s, import_block = time.perf_counter() - t0, probe.worst
    shown, failed = w.model.rowCount(), w.project.conn.execute(
        "SELECT count(*) FROM assets WHERE status != 'ok'").fetchone()[0]

    t0 = time.perf_counter()
    with probe:
        qtbot.waitUntil(lambda: all(w.model.pixmap(w.model.record(w.model.index(r))) is not None
                                    for r in _visible_rows(w)), timeout=600_000)
    first_paint_s, first_block = time.perf_counter() - t0, probe.worst

    hd_s, rows = _hd_wait(qtbot, w, probe)
    hd_block = probe.worst
    hd_dir = w.project.cache_dir / asset_model.HD_DIR
    hd_first = len(list(hd_dir.glob("*.jpg")))

    t0 = time.perf_counter()  # first scroll to the end at 340 px: cards never seen before
    with probe:
        w.grid.scrollToBottom()
        qtbot.wait(50)
        bottom = _visible_rows(w)
        qtbot.waitUntil(lambda: not w.model._pending and all(
            w.model._pix_gen.get(w.model.record(w.model.index(r)).id, -1) >= w.model._gen for r in bottom),
            timeout=600_000)
    scroll_s, scroll_block = time.perf_counter() - t0, probe.worst
    w.grid.scrollToTop()
    hd_mb = sum(p.stat().st_size for p in hd_dir.glob("*.jpg")) / 1e6

    # The same again with a cold HD cache while the AI analysis runs (one heavy model at a time, CPU here).
    w.set_grid_cell(140)
    shutil.rmtree(hd_dir, ignore_errors=True)
    w.model._pix_gen.clear()
    w.model._pixmaps.clear()
    w.model._bytes = 0
    analysis = w.start_analysis("people")
    ai_running = analysis is not None
    qtbot.wait(2000)  # let the models load and the first photos start
    ai_hd_s, _rows = _hd_wait(qtbot, w, probe)
    ai_block = probe.worst
    ai_still_running = w.analyze_thread is not None
    t0 = time.perf_counter()
    w.close()
    close_s = time.perf_counter() - t0

    _record("real_raw_cold", shown, files=len(_sources()), not_ok=failed, import_s=import_s,
            import_worst_block_ms=import_block, first_paint_s=first_paint_s, first_paint_worst_block_ms=first_block,
            hd_visible_cards=rows, hd_340_dpr2_s=hd_s, hd_files_first_view=hd_first,
            hd_worst_block_ms=hd_block, first_scroll_cards=len(bottom), first_scroll_hd_s=scroll_s,
            first_scroll_worst_block_ms=scroll_block, hd_files=len(list(hd_dir.glob("*.jpg"))), hd_cache_mb=hd_mb,
            ai_running=ai_running, ai_still_running_at_end=ai_still_running, hd_with_ai_s=ai_hd_s,
            hd_with_ai_worst_block_ms=ai_block, close_with_ai_s=close_s)
    assert hd_block < 250 and scroll_block < 250 and ai_block < 250  # never a visible freeze


@pytest.mark.skipif(not _sources(), reason="no RAW samples in test_photos/ (git-ignored, not in CI)")
def test_real_raw_large_export_while_closing(qtbot, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Close the window during a large export of real RAW files and answer "Dừng xuất và thoát": it stops after the
    file being copied; every copy made is byte-identical. Exporting again into the same folder copies only what is
    missing, so the folder ends complete (what the question promises). Sources untouched (RV14-04)."""
    import hashlib

    from PySide6.QtWidgets import QMessageBox

    from app.storage import decisions

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    shoot, w = _shoot_and_window(qtbot, tmp_path, monkeypatch)
    w.start_import(shoot)
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=600_000)
    sources = {p.name: (sha(p), p.stat().st_mtime_ns) for p in shoot.iterdir()}
    with w.project.transaction() as conn:
        for (asset_id,) in conn.execute("SELECT id FROM assets WHERE status = 'ok'").fetchall():
            decisions.set_flag(conn, asset_id, "keep")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    out = tmp_path / "out"

    def export(window):  # noqa: ANN001, ANN202
        dialog = window.open_export_dialog()
        qtbot.addWidget(dialog)
        dialog.dest.setText(str(out))
        dialog.refresh()
        dialog.hide()
        return dialog

    dialog = export(w)
    assert dialog.plan is not None and len(dialog.plan.items) == len(sources)
    total_mb = dialog.plan.total_bytes / 1e6
    t0 = time.perf_counter()
    dialog.start_copy()
    qtbot.wait(300)  # a few files in
    t1 = time.perf_counter()
    w.close()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=600_000)
    close_s = time.perf_counter() - t1

    def copies() -> dict[str, str]:
        return {p.name: sha(p) for p in out.rglob("*") if p.is_file() and p.suffix.lower() in RAW_EXTS}

    first = copies()
    assert all(first[n] == sources[n][0] for n in first)  # what was copied is complete, never a half file

    from app.ui import main_window as mw

    w2 = mw.MainWindow(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w2)
    w2.start_import(shoot)  # the same session, remembered
    qtbot.waitUntil(lambda: w2.import_thread is None, timeout=600_000)
    again = export(w2)
    assert again.plan is not None and len(again.plan.items) == len(sources) - len(first)
    t2 = time.perf_counter()
    thread = again.start_copy()
    qtbot.waitUntil(lambda: not thread.isRunning(), timeout=600_000)
    second_s = time.perf_counter() - t2
    final = copies()
    w2.close()
    _record("real_raw_export_while_closing", len(sources), export_mb=total_mb, copied_before_close=len(first),
            close_after_yes_s=close_s, first_run_s=time.perf_counter() - t0, second_run_files=len(sources) - len(first),
            second_run_s=second_s)
    assert final == {n: d for n, (d, _m) in sources.items()}  # complete, byte-identical, no "(1)" duplicates
    assert {p.name: (sha(p), p.stat().st_mtime_ns) for p in shoot.iterdir()} == sources
