from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path

import pytest

from app.export.formats import ExportFormat
from app.export.copy_export import ExportError, Selection, plan_export, run_export, select_assets
from app.ingest.fingerprint import full_sha256
from app.storage import decisions
from app.storage.project import Project
from app.workers.import_job import ImportJob
from tests.integration.test_import_job import _photo


def _ids(p: Project) -> dict[str, int]:
    """relative_path -> id (only for names that are unique in the test)."""
    return {r[1]: r[0] for r in p.conn.execute("SELECT id, relative_path FROM assets")}


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Project, Path, Path]:
    a = tmp_path / "Ngày 1"
    b = tmp_path / "Ngày 2"
    _photo(a / "DSC_0001.jpg", 1)
    _photo(a / "sub" / "DSC_0002.jpg", 2)
    _photo(b / "DSC_0001.jpg", 3)  # same name as in "Ngày 1", different photo
    project = Project.create(tmp_path / "proj", "Export")
    ImportJob(project, a).run()
    ImportJob(project, b).run()
    yield project, a, b
    project.close()


def test_select_by_keep_favorite_rating(setup: tuple[Project, Path, Path]) -> None:
    p, _, _ = setup
    ids = _ids(p)
    decisions.set_flag(p.conn, ids["DSC_0001.jpg"], "keep")
    decisions.set_favorite(p.conn, ids["sub/DSC_0002.jpg"], True)
    decisions.set_rating(p.conn, ids["sub/DSC_0002.jpg"], 4)
    assert len(select_assets(p, Selection.KEEP)) == 1
    assert select_assets(p, Selection.FAVORITE) == [ids["sub/DSC_0002.jpg"]]
    assert select_assets(p, Selection.RATED, min_rating=4) == [ids["sub/DSC_0002.jpg"]]
    assert select_assets(p, Selection.RATED, min_rating=5) == []
    assert select_assets(p, Selection.IDS, ids=[3, 3, 1]) == [3, 1]


def test_export_copies_without_touching_or_overwriting(setup: tuple[Project, Path, Path], tmp_path: Path) -> None:
    p, a, b = setup
    all_ids = [r[0] for r in p.conn.execute("SELECT id FROM assets ORDER BY id")]
    sources = {f: full_sha256(f) for root in (a, b) for f in root.rglob("*.jpg")}
    dest = tmp_path / "Xuất ảnh"
    dest.mkdir()
    (dest / "DSC_0001.jpg").write_bytes(b"user's existing file")

    plan = plan_export(p, all_ids, dest)
    names = sorted(i.dest_relative for i in plan.items)
    assert names == ["DSC_0001 (1).jpg", "DSC_0001 (2).jpg", "DSC_0002.jpg"]  # no collision, no overwrite

    result = run_export(plan)
    assert sorted(result.copied) == names and not result.failed
    assert (dest / "DSC_0001.jpg").read_bytes() == b"user's existing file"
    for item in plan.items:
        assert full_sha256(dest / item.dest_relative) == full_sha256(item.source)
        assert os.path.getmtime(dest / item.dest_relative) == pytest.approx(os.path.getmtime(item.source), abs=1)
    assert sources == {f: full_sha256(f) for f in sources}, "originals changed"

    rows = list(csv.DictReader(open(result.manifest_csv, encoding="utf-8-sig")))
    assert sorted(r["exported_as"] for r in rows) == names and {r["status"] for r in rows} == {"copied"}
    assert any("Ngày 1" in r["source"] for r in rows)  # Unicode survives (root folder name + relative path)
    assert len(json.loads(result.manifest_json.read_text(encoding="utf-8"))["rows"]) == 3  # manifest v2 (Part 3)


def test_source_subfolders_are_not_reproduced(setup: tuple[Project, Path, Path], tmp_path: Path) -> None:
    """"Giữ cấu trúc thư mục con" was removed (Part 3, review Q1): one folder, names made unique."""
    p, _, _ = setup
    plan = plan_export(p, [r[0] for r in p.conn.execute("SELECT id FROM assets")], tmp_path / "out")
    assert sorted(i.dest_relative for i in plan.items) == ["DSC_0001 (1).jpg", "DSC_0001.jpg", "DSC_0002.jpg"]


def test_file_created_after_planning_is_not_overwritten(setup: tuple[Project, Path, Path], tmp_path: Path) -> None:
    p, _, _ = setup
    ids = _ids(p)
    dest = tmp_path / "out"
    plan = plan_export(p, [ids["sub/DSC_0002.jpg"]], dest)
    dest.mkdir()
    (dest / "DSC_0002.jpg").write_bytes(b"appeared meanwhile")
    result = run_export(plan)
    assert result.renamed == {"DSC_0002.jpg": "DSC_0002 (1).jpg"}
    assert (dest / "DSC_0002.jpg").read_bytes() == b"appeared meanwhile"


def test_refuses_source_or_project_folder_as_destination(setup: tuple[Project, Path, Path]) -> None:
    p, a, _ = setup
    with pytest.raises(ExportError):
        plan_export(p, [1], a)
    with pytest.raises(ExportError):
        plan_export(p, [1], p.folder / "exports")
    plan_export(p, [1], a / "Đã chọn")  # a subfolder of the shoot is fine


def test_cancel_and_missing_files(setup: tuple[Project, Path, Path], tmp_path: Path) -> None:
    p, a, _ = setup
    ids = [r[0] for r in p.conn.execute("SELECT id FROM assets")]
    (a / "sub" / "DSC_0002.jpg").unlink()
    plan = plan_export(p, ids, tmp_path / "out")
    assert plan.missing == ["sub/DSC_0002.jpg"] and len(plan.items) == 2
    result = run_export(plan, should_cancel=lambda: True)
    assert result.cancelled and result.copied == []
    # Manifest v2 (Part 3 spec §3.7): written for every run that started, cancelled ones included
    statuses = sorted(r["status"] for r in csv.DictReader(open(result.manifest_csv, encoding="utf-8-sig")))
    assert statuses == ["missing", "not_started", "not_started"]


def test_raw_jpeg_pair_exported_together_with_shared_stem(tmp_path: Path, public_nef: Path) -> None:
    root = tmp_path / "pairs"
    root.mkdir()
    shutil.copy2(public_nef, root / "ISS.NEF")
    _photo(root / "ISS.JPG", 1, taken="2012:03:04 17:20:59")
    with Project.create(tmp_path / "proj", "Pairs") as p:
        ImportJob(p, root).run()
        raw_id = _ids(p)["ISS.NEF"]
        decisions.set_flag(p.conn, raw_id, "keep")
        dest = tmp_path / "out"
        dest.mkdir()
        (dest / "ISS.JPG").write_bytes(b"x")  # forces a new stem for BOTH files of the pair
        plan = plan_export(p, select_assets(p, Selection.KEEP), dest)
        assert sorted(i.dest_relative for i in plan.items) == ["ISS (1).JPG", "ISS (1).NEF"]
        assert all(plan.photos[i.photo_id].flag == "keep" for i in plan.items)  # the RAW's decision applies to its JPEG
        assert [i.dest_relative for i in plan_export(p, [raw_id], tmp_path / "o2", fmt=ExportFormat.RAW).items] == ["ISS.NEF"]


def test_re_export_skips_identical_files_instead_of_duplicating(setup: tuple[Project, Path, Path], tmp_path: Path) -> None:
    """User report: exporting 4x into one folder produced 'X (1)' copies of the same photos."""
    p, _, _ = setup
    all_ids = [r[0] for r in p.conn.execute("SELECT id FROM assets ORDER BY id")]
    dest = tmp_path / "Test"
    dest.mkdir()
    (dest / "DSC_0001.jpg").write_bytes(b"a different photo with the same name")
    first = run_export(plan_export(p, all_ids, dest))
    assert sorted(first.copied) == ["DSC_0001 (1).jpg", "DSC_0001 (2).jpg", "DSC_0002.jpg"]

    for _ in range(3):
        again = plan_export(p, all_ids, dest)
        assert again.to_copy == []  # nothing new to copy; the three stay operations to verify (CR-P3-A02)
        assert sorted(again.already_present) == ["DSC_0001 (1).jpg", "DSC_0001 (2).jpg", "DSC_0002.jpg"]
        rerun = run_export(again)
        assert rerun.copied == [] and sorted(rerun.already_present) == sorted(again.already_present)

    photos = sorted(f.name for f in dest.iterdir() if f.is_file())
    assert photos == ["DSC_0001 (1).jpg", "DSC_0001 (2).jpg", "DSC_0001.jpg", "DSC_0002.jpg"]  # no lists among photos
    assert first.manifest_csv is not None and first.manifest_csv.parent.name == "_kirapick_danh_sach"

    # A newly kept photo is still added; only it gets copied.
    (dest / "DSC_0002.jpg").unlink()
    partial = plan_export(p, all_ids, dest)
    assert [i.dest_relative for i in partial.to_copy] == ["DSC_0002.jpg"] and len(partial.already_present) == 2


def test_two_exports_in_one_second_keep_both_manifests(setup: tuple[Project, Path, Path], tmp_path: Path,
                                                       monkeypatch) -> None:  # noqa: ANN001
    """Found by Part 3 Task 4: a second export into the same folder within the same second raised FileExistsError
    after copying (the manifest name is the time to the second, opened with 'x')."""
    from app.export import copy_export

    class Frozen:
        @staticmethod
        def now():  # noqa: ANN205
            import datetime as dt
            return dt.datetime(2026, 10, 30, 12, 0, 0)

    monkeypatch.setattr(copy_export, "datetime", Frozen)
    p, _, _ = setup
    ids = sorted(_ids(p).values())
    dest = tmp_path / "out"
    first = run_export(plan_export(p, ids[:1], dest))
    second = run_export(plan_export(p, ids[1:], dest))
    assert first.manifest_csv != second.manifest_csv and second.manifest_csv.is_file()
    assert first.manifest_json != second.manifest_json and second.manifest_json.is_file()
