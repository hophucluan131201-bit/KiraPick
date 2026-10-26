from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.ingest.fingerprint import full_sha256
from app.storage import decisions
from app.storage.project import Project
from app.workers.import_job import STAGE, ImportJob, ImportProgress

ROOT = Path(__file__).resolve().parents[2]


def _photo(path: Path, seed: int, size: tuple[int, int] = (900, 600), orientation: int | None = None,
           taken: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if taken:
        exif.get_ifd(0x8769)[0x9003] = taken
    Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)).save(
        path, "JPEG", quality=80, exif=exif.tobytes()
    )
    return path


def _status(p: Project) -> dict[str, str]:
    return {r[0]: r[1] for r in p.conn.execute("SELECT relative_path, status FROM assets")}


@pytest.fixture
def shoot(tmp_path: Path) -> Path:
    root = tmp_path / "Buổi chụp"
    _photo(root / "DSC_0001.jpg", 1)
    _photo(root / "DSC_0002.jpg", 2, orientation=6)
    _photo(root / "Ngày 2" / "DSC_0003.jpg", 3)
    (root / "broken.jpg").write_bytes(b"not a jpeg" * 50)
    (root / "notes.txt").write_text("x")
    return root


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "proj", "Shoot")
    yield p
    p.close()


def test_first_import_builds_assets_thumbnails_and_metadata(project: Project, shoot: Path) -> None:
    hashes = {f: full_sha256(f) for f in shoot.rglob("*") if f.is_file()}
    events: list[ImportProgress] = []
    summary = ImportJob(project, shoot, workers=2).run(progress=events.append)

    assert (summary.found, summary.new, summary.ingested, summary.failed) == (4, 4, 3, 1)
    assert summary.unsupported_extensions == {".txt": 1}
    assert _status(project) == {
        "DSC_0001.jpg": "ok", "DSC_0002.jpg": "ok", "Ngày 2/DSC_0003.jpg": "ok", "broken.jpg": "error",
    }
    row = project.conn.execute(
        "SELECT p.file_name, p.width, p.height, a.width AS fw, a.height AS fh FROM previews p "
        "JOIN assets a ON a.id = p.asset_id WHERE a.relative_path = 'DSC_0002.jpg'"
    ).fetchone()
    assert (row["width"], row["height"]) == (267, 400)  # EXIF 6 -> portrait thumbnail
    assert (row["fw"], row["fh"]) == (600, 900)
    with Image.open(project.cache_dir / row["file_name"]) as thumb:
        assert thumb.size == (267, 400)
    assert {e.phase for e in events} >= {"scan", "register", "ingest", "pair"}
    assert project.conn.execute("SELECT state FROM jobs").fetchone()[0] == "done"
    assert hashes == {f: full_sha256(f) for f in shoot.rglob("*") if f.is_file()}, "sources modified"
    assert sorted(p.name for p in shoot.iterdir()) == ["DSC_0001.jpg", "DSC_0002.jpg", "Ngày 2", "broken.jpg", "notes.txt"]


def test_reimport_detects_unchanged_changed_missing_and_returned(project: Project, shoot: Path) -> None:
    ImportJob(project, shoot).run()
    asset_id = project.conn.execute("SELECT id FROM assets WHERE relative_path = 'DSC_0001.jpg'").fetchone()[0]
    decisions.set_flag(project.conn, asset_id, "keep")

    again = ImportJob(project, shoot).run()
    assert (again.unchanged, again.new, again.changed, again.ingested) == (4, 0, 0, 0)
    assert again.failed == 1  # the broken file is retried once more, then left alone
    assert ImportJob(project, shoot).run().failed == 0

    _photo(shoot / "DSC_0003_new.jpg", 9)
    _photo(shoot / "Ngày 2" / "DSC_0003.jpg", 33)  # edited in place
    os.utime(shoot / "Ngày 2" / "DSC_0003.jpg", ns=(1, 1))
    moved = shoot.parent / "DSC_0001.jpg"
    shutil.move(shoot / "DSC_0001.jpg", moved)
    s = ImportJob(project, shoot).run()
    assert (s.new, s.changed, s.missing, s.ingested) == (1, 1, 1, 2)
    assert _status(project)["DSC_0001.jpg"] == "missing"

    shutil.move(moved, shoot / "DSC_0001.jpg")
    s = ImportJob(project, shoot).run()
    assert s.ingested == 1 and _status(project)["DSC_0001.jpg"] == "ok"
    assert decisions.get(project.conn, asset_id).flag == "keep", "user decision lost across missing/return"


def test_duplicates_across_folders_are_not_reprocessed(project: Project, shoot: Path, tmp_path: Path) -> None:
    ImportJob(project, shoot).run()
    backup = tmp_path / "Backup"
    backup.mkdir()
    shutil.copy2(shoot / "DSC_0001.jpg", backup / "copy of DSC_0001.jpg")
    s = ImportJob(project, backup).run()
    assert (s.duplicates, s.ingested) == (1, 0)
    row = project.conn.execute("SELECT status, duplicate_of FROM assets WHERE relative_path LIKE 'copy%'").fetchone()
    assert row["status"] == "duplicate" and row["duplicate_of"] is not None


def test_project_folder_inside_photo_folder_is_not_imported(tmp_path: Path, shoot: Path) -> None:
    with Project.create(shoot / "_snorlu_project", "Inside") as p:
        ImportJob(p, shoot).run()
        assert ImportJob(p, shoot).run().new == 0  # its own cache/thumbs/*.jpg are never picked up
        assert not any("_snorlu_project" in rel for rel in _status(p))


def test_cancel_then_resume(project: Project, tmp_path: Path) -> None:
    root = tmp_path / "many"
    for i in range(20):
        _photo(root / f"IMG_{i:03d}.jpg", 100 + i)
    calls = {"ingest": 0}

    def cancel_after_a_few() -> bool:
        return calls["ingest"] >= 1

    def progress(p: ImportProgress) -> None:
        if p.phase == "ingest" and p.done:
            calls["ingest"] += 1

    first = ImportJob(project, root, workers=1).run(progress=progress, should_cancel=cancel_after_a_few)
    assert first.cancelled and 0 < first.ingested < 20
    assert project.conn.execute("SELECT state FROM jobs").fetchone()[0] == "paused"
    pending = project.conn.execute(
        "SELECT count(*) FROM stage_status WHERE stage = ? AND state = 'pending'", (STAGE,)
    ).fetchone()[0]
    assert pending == 20 - first.ingested

    second = ImportJob(project, root).run()
    assert not second.cancelled and second.new == 0 and second.ingested == pending
    assert set(_status(project).values()) == {"ok"}


def test_raw_jpeg_pairing_uses_capture_time(project: Project, tmp_path: Path, public_nef: Path) -> None:
    root = tmp_path / "pairs"
    root.mkdir()
    shutil.copy2(public_nef, root / "ISS.NEF")
    _photo(root / "ISS.JPG", 1, taken="2012:03:04 17:20:59")  # same moment as the NEF
    shutil.copy2(public_nef, root / "OTHER.NEF")
    _photo(root / "OTHER.jpg", 2, taken="2019:01:01 10:00:00")  # reused file number, different shot
    s = ImportJob(project, root).run()
    assert s.pairs == 1
    groups = project.conn.execute(
        "SELECT a.relative_path, g.status FROM assets a JOIN pair_groups g ON g.id = a.pair_group_id ORDER BY 1"
    ).fetchall()
    assert [tuple(r) for r in groups] == [("ISS.JPG", "confirmed"), ("ISS.NEF", "confirmed")]
    # OTHER.NEF is a byte-identical copy of ISS.NEF -> duplicate, never paired.
    assert _status(project)["OTHER.NEF"] == "duplicate"


def test_relink_after_folder_moved(project: Project, shoot: Path, tmp_path: Path) -> None:
    ImportJob(project, shoot).run()
    new_home = tmp_path / "Moved drive" / "Buổi chụp"
    new_home.parent.mkdir()
    shutil.move(shoot, new_home)
    project.relink_source(1, new_home)
    asset_id = project.conn.execute("SELECT id FROM assets WHERE relative_path = 'DSC_0002.jpg'").fetchone()[0]
    assert project.asset_path(asset_id).is_file()
    s = ImportJob(project, new_home).run()
    assert (s.new, s.missing, s.unchanged) == (0, 0, 4)


_CHILD = """
import sys, time
from pathlib import Path
sys.path.insert(0, {root!r})
from app.storage.project import Project
from app.workers.import_job import ImportJob

def slow(p):
    if p.phase == "ingest" and p.done:
        print("PROGRESS", p.done, flush=True)
        time.sleep(0.3)

with Project.open(Path({proj!r})) as proj:
    ImportJob(proj, Path({photos!r}), workers=1).run(progress=slow)
"""


@pytest.mark.skipif(os.name == "nt", reason="uses SIGKILL")
def test_killed_process_resumes_without_losing_work(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    for i in range(30):
        _photo(photos / f"IMG_{i:03d}.jpg", 500 + i)
    proj_dir = tmp_path / "proj"
    Project.create(proj_dir, "Kill test").close()

    child = subprocess.Popen(
        [sys.executable, "-c", _CHILD.format(root=str(ROOT), proj=str(proj_dir), photos=str(photos))],
        stdout=subprocess.PIPE, text=True,
    )
    assert child.stdout is not None
    for line in child.stdout:
        if line.startswith("PROGRESS") and int(line.split()[1]) >= 5:
            break
    child.send_signal(signal.SIGKILL)  # no cleanup, no finally blocks
    child.wait(timeout=30)

    with Project.open(proj_dir) as p:  # recovery marks the job paused
        assert p.conn.execute("SELECT state FROM jobs").fetchone()[0] == "paused"
        done_before = p.conn.execute("SELECT count(*) FROM stage_status WHERE state = 'done'").fetchone()[0]
        assert 5 <= done_before < 30
        for name, in p.conn.execute("SELECT file_name FROM previews"):
            with Image.open(p.cache_dir / name) as im:
                im.verify()  # every recorded thumbnail is complete
        start = time.perf_counter()
        s = ImportJob(p, photos).run()
        assert s.new == 0 and s.ingested == 30 - done_before, "finished work was redone or lost"
        assert set(_status(p).values()) == {"ok"}
        assert time.perf_counter() - start < 30
