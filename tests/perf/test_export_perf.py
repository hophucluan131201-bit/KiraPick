"""Part 3 export, timing (marker `perf`; numbers only): planning from the imported folders on the GUI thread (1 000 and
10 000 photos), scanning another folder of 5 000 files, matching 1 000 photos by capture time (EXIF reads =
candidates), and the longest GUI-thread block while a scan + plan runs in the background."""

from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QElapsedTimer, QSettings, QTimer

from app.export import sources
from app.export.copy_export import plan_export
from app.export.formats import ExportFormat
from app.export.sources import SourceSpec, scan_external
from app.ingest.fingerprint import quick_fingerprint
from app.storage import decisions
from app.storage.project import Project, utc_now
from app.ui.export_dialog import ExportDialog
from tests.perf.test_grid_perf import _record
from tests.unit.test_export_match import exif_file

pytestmark = pytest.mark.perf


def _session(tmp_path: Path, n: int, *, exif: bool = False) -> tuple[Project, Path, list[int]]:
    root = tmp_path / "shoot"
    root.mkdir()
    project = Project.create(tmp_path / "session", "perf")
    conn = project.conn
    source_id = conn.execute("INSERT INTO sources (root_path, added_at) VALUES (?, ?)", (str(root), utc_now())).lastrowid
    rows, now = [], utc_now()
    for i in range(n):
        name = f"DSC_{i:05d}.JPG"
        path = root / name
        if exif:
            exif_file(path, f"2026:10:25 {10 + i // 3600:02d}:{i // 60 % 60:02d}:{i % 60:02d}", seed=i)
        else:
            path.write_bytes(i.to_bytes(4, "little") * 512)
        fp = quick_fingerprint(path)
        stamp = f"2026-10-25T{10 + i // 3600:02d}:{i // 60 % 60:02d}:{i % 60:02d}"
        rows.append((source_id, name, ".jpg", "raster", "full", fp.size, fp.mtime_ns, fp.quick_hash, "ok", stamp,
                     "NIKON", "Z 5", now, now))
    conn.executemany(
        """INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
                               quick_hash, status, capture_time, make, model, added_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows)
    ids = [r[0] for r in conn.execute("SELECT id FROM assets ORDER BY id")]
    for aid in ids:
        decisions.set_flag(conn, aid, "keep")
    conn.commit()
    return project, root, ids


@pytest.mark.parametrize("n", [1000, 10_000])
def test_plan_imported_on_gui_thread(tmp_path: Path, n: int) -> None:
    project, _root, ids = _session(tmp_path, n)
    try:
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            plan = plan_export(project, ids, tmp_path / "out")
            times.append((time.perf_counter() - t0) * 1000)
        assert len(plan.operations) == n
        _record("export_plan_imported", n, best_ms=min(times), worst_ms=max(times))
        if n == 1000:
            assert min(times) <= 100, "imported planning must move to the plan thread (spec §5)"
    finally:
        project.close()


def test_external_scan_5000_files(tmp_path: Path) -> None:
    card = tmp_path / "card"
    for folder in range(50):
        d = card / "DCIM" / f"{100 + folder}NIKON"
        d.mkdir(parents=True)
        for i in range(100):
            (d / f"DSC_{folder * 100 + i:04d}.NEF").write_bytes(b"")
    t0 = time.perf_counter()
    index = scan_external(card, session_folder=tmp_path / "session", destination=tmp_path / "out")
    ms = (time.perf_counter() - t0) * 1000
    assert index.files == 5000
    _record("export_scan_external", 5000, ms=ms)


def test_matching_1000_photos_by_capture_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _root, ids = _session(tmp_path, 1000)
    card = tmp_path / "card"
    for i in range(1000):
        exif_file(card / f"DSC_{i:05d}.NEF", f"2026:10:25 {10 + i // 3600:02d}:{i // 60 % 60:02d}:{i % 60:02d}",
                  seed=i)
    reads = []
    real = sources.read_metadata

    def counted(path: Path, **kw):  # noqa: ANN003, ANN202
        reads.append(path)
        return real(path, **kw)

    monkeypatch.setattr(sources, "read_metadata", counted)
    try:
        index = scan_external(card, session_folder=project.folder, destination=tmp_path / "out")
        # match_file's default argument was bound at import: pass the counter explicitly through a wrapper
        monkeypatch.setattr(sources, "match_file", _with_read_meta(sources.match_file, counted))
        from app.export import copy_export
        monkeypatch.setattr(copy_export, "match_file", sources.match_file)
        t0 = time.perf_counter()
        plan = plan_export(project, ids, tmp_path / "out", source=SourceSpec("external", card, index),
                           fmt=ExportFormat.RAW)
        ms = (time.perf_counter() - t0) * 1000
        assert len(plan.operations) == 1000 and {op.match for op in plan.operations} == {"time"}
        assert len(reads) == 1000  # EXIF read once per candidate, never for the rest of the card
        _record("export_match_cross_format", 1000, ms=ms, exif_reads=len(reads))
    finally:
        project.close()


def _with_read_meta(fn, read_meta):  # noqa: ANN001, ANN202
    def wrapped(*a, **kw):  # noqa: ANN002, ANN003, ANN202
        kw["read_meta"] = read_meta
        return fn(*a, **kw)
    return wrapped


def test_gui_thread_worst_block_during_scan(qtbot, tmp_path: Path) -> None:  # noqa: ANN001
    project, root, _ids = _session(tmp_path, 1000)
    card = tmp_path / "card"
    for folder in range(50):
        d = card / f"{100 + folder}NIKON"
        d.mkdir(parents=True)
        for i in range(100):
            (d / f"DSC_{folder * 100 + i:05d}.NEF").write_bytes(b"")
    for i in range(1000):  # same-name copies: content proof (full SHA-256) in the plan thread
        (card / "JPG").mkdir(exist_ok=True)
        (card / "JPG" / f"DSC_{i:05d}.JPG").write_bytes((root / f"DSC_{i:05d}.JPG").read_bytes())
    try:
        dialog = ExportDialog(project, [], settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(200)  # the first paint is not part of the measurement
        gaps: list[int] = []
        clock = QElapsedTimer()
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: (gaps.append(clock.restart())))
        clock.start()
        timer.start()
        t0 = time.perf_counter()
        dialog.dest.setText(str(tmp_path / "out"))
        dialog.external_path.setText(str(card))
        dialog.source_external.setChecked(True)
        qtbot.waitUntil(lambda: dialog.plan is not None and not dialog.scanning, timeout=120_000)
        total = (time.perf_counter() - t0) * 1000
        timer.stop()
        assert len(dialog.plan.operations) == 1000
        worst = max(gaps[1:]) if len(gaps) > 1 else 0
        _record("export_dialog_scan_plan_gui_block", 6000, total_ms=total, worst_gui_block_ms=worst)
        assert worst <= 100
        dialog._cancel_plans()
        qtbot.waitUntil(lambda: not dialog.plan_threads, timeout=10000)
    finally:
        project.close()


def test_gui_thread_block_planning_10000_imported(qtbot, tmp_path: Path) -> None:  # noqa: ANN001
    project, _root, _ids = _session(tmp_path, 10_000)
    try:
        dialog = ExportDialog(project, [], settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)
        qtbot.wait(200)  # the first paint is not part of the measurement
        gaps: list[int] = []
        clock, timer = QElapsedTimer(), QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: gaps.append(clock.restart()))
        clock.start()
        timer.start()
        t0 = time.perf_counter()
        dialog.dest.setText(str(tmp_path / "out"))
        dialog.refresh()  # what "Chọn…" for the destination does
        qtbot.waitUntil(lambda: dialog.plan is not None and not dialog.scanning, timeout=120_000)
        total = (time.perf_counter() - t0) * 1000
        timer.stop()
        assert len(dialog.plan.operations) == 10_000
        worst = max(gaps[1:]) if len(gaps) > 1 else 0
        _record("export_dialog_plan_imported_gui_block", 10_000, total_ms=total, worst_gui_block_ms=worst)
        assert worst <= 100
    finally:
        project.close()
