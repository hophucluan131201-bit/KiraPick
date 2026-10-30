"""Part 3 Task 2 — photos of an export and the file kinds each format wants."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.export.formats import ExportFormat, file_kind, wanted_kinds
from app.export.photos import load_photos
from tests.fixtures_export import make_export_session


@pytest.mark.parametrize(("name", "kind"), [
    ("DSC_0001.NEF", "raw"), ("a.cr3", "raw"), ("A.JPG", "jpeg"), ("b.jpeg", "jpeg"),
    ("c.tif", "other"), ("d.PNG", "other"), ("e.heic", None), ("f.TIFF", "other"), ("notes.txt", None), ("noext", None),
])
def test_file_kind(name: str, kind: str | None) -> None:
    assert file_kind(name) == kind
    assert file_kind(Path("x") / name) == kind


def test_wanted_kinds() -> None:
    assert wanted_kinds(ExportFormat.RAW_JPEG, external=False) == {"raw", "jpeg", "other"}
    assert wanted_kinds(ExportFormat.RAW_JPEG, external=True) == {"raw", "jpeg"}
    for external in (False, True):
        assert wanted_kinds(ExportFormat.RAW, external=external) == {"raw"}
        assert wanted_kinds(ExportFormat.JPEG, external=external) == {"jpeg"}
    assert ExportFormat("raw_jpeg") is ExportFormat.RAW_JPEG


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


def test_load_photos_pair_and_singles(fx) -> None:  # noqa: ANN001
    keys = ["jpeg_only", "pair", "pair_missing_jpeg", "tiff"]
    photos = load_photos(fx.project.conn, [fx.ids[k] for k in keys])
    assert [p.photo_id for p in photos] == [fx.ids[k] for k in keys]  # order of the request
    jpeg_only, pair, missing, tiff = photos
    assert pair.stem == "DSC_0001" and [f.kind for f in pair.files] == ["raw", "jpeg"]
    assert [f.asset_id for f in pair.files] == fx.files["pair"]  # primary first
    assert pair.files[0].path == fx.root / "DSC_0001.NEF" and pair.files[0].relative_path == "DSC_0001.NEF"
    assert pair.files[0].source_root == fx.root and pair.files[0].size == 500_000 and pair.files[0].quick_hash
    assert pair.capture_time == datetime(2026, 10, 25, 16, 0, 0) and pair.camera == "NIKON Z 5"
    assert pair.flag == "keep" and pair.favorite is True and pair.rating == 0
    assert len(missing.files) == 2  # the JPEG gone from disk is still listed: the planner checks the disk
    assert [f.kind for f in tiff.files] == ["other"] and [f.kind for f in jpeg_only.files] == ["jpeg"]


def test_load_photos_fallback_time(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    raw, jpg = fx.files["pair"]
    conn.execute("UPDATE assets SET capture_time = NULL, make = NULL, model = NULL WHERE id = ?", (raw,))
    conn.execute("UPDATE assets SET capture_time = '2026-10-25T16:00:05', subsec = '42' WHERE id = ?", (jpg,))
    (photo,) = load_photos(conn, [raw])
    assert photo.capture_time == datetime(2026, 10, 25, 16, 0, 5) and photo.subsec == "42"
    assert photo.camera == "NIKON Z 5"


def test_load_photos_skips_unknown_ids_and_not_ok_files(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    conn.execute("UPDATE assets SET status = 'missing' WHERE id = ?", (fx.files["pair"][1],))
    photos = load_photos(conn, [fx.ids["pair"], 99_999])
    assert len(photos) == 1 and [f.kind for f in photos[0].files] == ["raw"]


def test_load_photos_many_ids_batched(fx) -> None:  # noqa: ANN001
    ids = [fx.ids[k] for k in ("pair", "raw_only")] * 600  # repeats are one photo each time asked
    photos = load_photos(fx.project.conn, ids)
    assert len(photos) == 2
