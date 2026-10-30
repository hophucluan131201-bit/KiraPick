"""Which photos an export really copied (for export_runs): renames, subfolders, partial failures, pairs, big lists."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.export import copy_export
from app.export.copy_export import ExportResult, plan_export, run_export
from app.storage import exports
from app.storage.project import Project
from app.workers.import_job import ImportJob
from tests.integration.test_export import _ids, setup  # noqa: F401 - fixture
from tests.integration.test_import_job import _photo


def test_copied_ids_follow_race_renames_and_subfolders(setup, tmp_path: Path) -> None:  # noqa: ANN001, F811
    p, _, _ = setup
    ids = _ids(p)
    dest = tmp_path / "out"
    plan = plan_export(p, sorted(ids.values()), dest)  # subfolders: subject folders, tests/unit/test_export_layout.py
    sub = next(i for i in plan.items if i.asset_id == ids["sub/DSC_0002.jpg"])
    (dest / sub.dest_relative).parent.mkdir(parents=True, exist_ok=True)
    (dest / sub.dest_relative).write_bytes(b"appeared meanwhile")  # forces a rename at copy time
    result = run_export(plan)
    assert sub.dest_relative in result.renamed
    assert sorted(result.copied_ids) == sorted(ids.values())
    assert len(result.copied_ids) == len(result.copied)


def test_partial_failure_lists_only_copied_photos(setup, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001, F811
    p, _, _ = setup
    ids = _ids(p)
    plan = plan_export(p, sorted(ids.values()), tmp_path / "out")
    broken = plan.items[1]
    real = copy_export._copy_exclusive

    def flaky(src, root, rel, **kw):  # noqa: ANN001, ANN003, ANN202
        if rel == broken.dest_relative:
            raise OSError(28, "No space left on device")
        return real(src, root, rel, **kw)

    monkeypatch.setattr(copy_export, "_copy_exclusive", flaky)
    result = run_export(plan)
    assert broken.dest_relative in result.failed
    assert broken.asset_id not in result.copied_ids and len(result.copied_ids) == len(plan.items) - 1


def test_cancelled_export_lists_what_was_copied_before_the_stop(setup, tmp_path: Path) -> None:  # noqa: ANN001, F811
    p, _, _ = setup
    plan = plan_export(p, sorted(_ids(p).values()), tmp_path / "out")
    stop = []  # the user presses Dừng once the first file is done (checks run between files and 1 MiB chunks)
    result = run_export(plan, should_cancel=lambda: bool(stop), progress=lambda done, _total: stop.append(done))
    assert result.cancelled and result.copied_ids == [plan.items[0].asset_id]


def test_pair_is_one_photo_two_files(tmp_path: Path) -> None:
    root = tmp_path / "shoot"
    _photo(root / "DSC_0001.jpg", 1)
    _photo(root / "DSC_0001_alt.jpg", 2)
    with Project.create(tmp_path / "proj", "p") as project:
        ImportJob(project, root).run()
        conn = project.conn
        group = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
        conn.execute("UPDATE assets SET pair_group_id = ?", (group,))
        first = min(_ids(project).values())
        plan = plan_export(project, [first], tmp_path / "out")  # the pair's other file comes along
        result = run_export(plan)
        assert len(result.copied) == 2 and exports.photo_count(conn, result.copied_ids) == 1


def _assets(conn, n: int) -> list[int]:  # noqa: ANN001
    src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
    conn.executemany(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at) VALUES (?, ?, 'jpg', 'raster', 'full', 1, 1, 'h', 'ok', 't', 't')",
        [(src, f"{i}.jpg") for i in range(n)])
    return [r[0] for r in conn.execute("SELECT id FROM assets ORDER BY id")]


def test_photo_count_handles_lists_beyond_sqlite_limits(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    with Project.create(tmp_path / "proj", "p") as project:
        conn = project.conn
        ids = _assets(conn, 40_000)  # more than SQLite's default 32,766 variables
        assert exports.photo_count(conn, ids) == 40_000
        group = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
        conn.execute("UPDATE assets SET pair_group_id = ? WHERE id IN (?, ?)", (group, ids[99], ids[100]))
        monkeypatch.setattr(exports, "BATCH", 100)  # the pair's two files fall into two different batches
        assert exports.photo_count(conn, ids[:200]) == 199
        assert exports.photo_count(conn, ids[:200] + ids[:200]) == 199  # duplicates count once
        with pytest.raises(ValueError):
            exports.photo_count(conn, [ids[0], 10**9])  # an id that is not a photo of this session


def test_dialog_records_only_finished_exports_that_copied(qtbot, setup, tmp_path: Path) -> None:  # noqa: ANN001, F811
    from app.ui.export_dialog import ExportDialog

    p, _, _ = setup
    ids = sorted(_ids(p).values())
    dialog = ExportDialog(p, ids)
    qtbot.addWidget(dialog)
    dialog.plan = plan_export(p, ids, tmp_path / "out")
    signals = []
    dialog.run_recorded.connect(lambda: signals.append(1))
    first = dialog.plan.items[0].asset_id
    dialog._record_run(ExportResult(copied=["a.jpg"], copied_ids=[first], cancelled=True))
    dialog._record_run(ExportResult())  # nothing copied
    assert exports.count(p.conn) == 0 and signals == []
    dialog._record_run(ExportResult(copied=["a.jpg"], failed={"b.jpg": "full"}, copied_ids=[first]))
    assert tuple(p.conn.execute("SELECT photos, files FROM export_runs").fetchone()) == (1, 1)
    assert signals == [1]


def test_dialog_refuses_a_result_whose_lists_disagree(qtbot, setup, tmp_path: Path) -> None:  # noqa: ANN001, F811
    """Invariant: one asset id per copied file; otherwise nothing is recorded (and the copies stay)."""
    from app.ui.export_dialog import ExportDialog

    p, _, _ = setup
    ids = sorted(_ids(p).values())
    dialog = ExportDialog(p, ids)
    qtbot.addWidget(dialog)
    dialog._record_run(ExportResult(copied=["a.jpg", "b.jpg"], copied_ids=[ids[0]]))
    assert exports.count(p.conn) == 0
