"""M2: several folders, camera sources by sub-folder + make / model, hand assignment (spec §9: CAM-01/02/03/05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media import cameras as cam
from app.media import event as ev
from tests.media.fixtures import hashes, photo


@pytest.fixture
def event(tmp_path: Path):  # noqa: ANN201
    e = ev.create_event("Hội nghị", tmp_path / "media")
    yield e
    e.close()


def _ids(event, folder_name: str) -> list[int]:  # noqa: ANN001
    return [r[0] for r in event.conn.execute(
        """SELECT a.id FROM assets a JOIN sources s ON s.id = a.source_id WHERE s.root_path LIKE ?
           ORDER BY a.relative_path""", (f"%{folder_name}",))]


def test_cam01_same_model_in_two_folders_is_two_sources(tmp_path: Path, event) -> None:  # noqa: ANN001
    a, b = tmp_path / "May_A", tmp_path / "May_B"
    for i in range(3):
        photo(a / f"DSC_{i:04d}.jpg", i, taken=f"2026:06:19 09:00:0{i}", make="NIKON", model="Z 6")
        photo(b / f"DSC_{i:04d}.jpg", 10 + i, taken=f"2026:06:19 08:57:0{i}", make="NIKON", model="Z 6")
    cam.import_folder(event, a)
    cam.import_folder(event, b)
    sources = cam.cameras(event.conn)
    assert len(sources) == 2 and all(s["photos"] == 3 for s in sources)
    assert {cam.camera_of(event.conn, i) for i in _ids(event, "May_A")} != \
        {cam.camera_of(event.conn, i) for i in _ids(event, "May_B")}


def test_cam02_one_folder_two_bodies_split_by_hand_and_kept(tmp_path: Path, event) -> None:  # noqa: ANN001
    shoot = tmp_path / "Chung"
    for i in range(6):
        photo(shoot / f"IMG_{i:04d}.jpg", i, taken=f"2026:06:19 10:00:0{i}", make="Canon", model="EOS R6")
    cam.import_folder(event, shoot)
    assert len(cam.cameras(event.conn)) == 1
    ids = _ids(event, "Chung")
    with event.transaction() as conn:
        second = cam.new_camera(conn, "R6 thứ hai")
        cam.assign_photos(conn, ids[3:], second)
    assert [cam.camera_of(event.conn, i) for i in ids[3:]] == [second] * 3
    photo(shoot / "IMG_9999.jpg", 99, taken="2026:06:19 10:10:00", make="Canon", model="EOS R6")
    cam.import_folder(event, shoot)  # a re-import / refresh never undoes a hand assignment
    assert [cam.camera_of(event.conn, i) for i in ids[3:]] == [second] * 3
    assert len(cam.cameras(event.conn)) == 2


def test_cam03_same_file_names_in_two_folders_are_two_photos(tmp_path: Path, event) -> None:  # noqa: ANN001
    a, b = tmp_path / "A", tmp_path / "B"
    photo(a / "DSC_0001.jpg", 1, taken="2026:06:19 09:00:00", make="SONY", model="ILCE-7M4")
    photo(b / "DSC_0001.jpg", 2, taken="2026:06:19 09:00:00", make="SONY", model="ILCE-7M4")
    before = {**hashes(a), **{f"B/{k}": v for k, v in hashes(b).items()}}
    cam.import_folder(event, a)
    cam.import_folder(event, b)
    rows = event.conn.execute("SELECT id, source_id, relative_path FROM assets ORDER BY id").fetchall()
    assert len(rows) == 2 and rows[0]["source_id"] != rows[1]["source_id"]
    assert {**hashes(a), **{f"B/{k}": v for k, v in hashes(b).items()}} == before


def test_cam05_missing_exif_is_an_unknown_camera_and_assignable(tmp_path: Path, event) -> None:  # noqa: ANN001
    shoot = tmp_path / "Thieu"
    photo(shoot / "a.jpg", 1)  # no time, no make / model
    photo(shoot / "b.jpg", 2, taken="2026:06:19 09:00:00", make="FUJIFILM", model="X-T5")
    cam.import_folder(event, shoot)
    names = sorted(s["display_name"] for s in cam.cameras(event.conn))
    assert names[1].startswith(cam.UNKNOWN_CAMERA) and names[0].startswith("FUJIFILM X-T5")
    a, b = _ids(event, "Thieu")
    with event.transaction() as conn:
        cam.assign_photos(conn, [a], cam.camera_of(conn, b))  # 'Thuộc máy: FUJIFILM' without EXIF
    assert len(cam.cameras(event.conn)) == 1  # the empty unknown source is gone


def test_rename_and_merge_sources(tmp_path: Path, event) -> None:  # noqa: ANN001
    a, b = tmp_path / "A", tmp_path / "B"
    photo(a / "1.jpg", 1, make="NIKON", model="Z 8")
    photo(b / "2.jpg", 2, make="NIKON", model="Z 8")
    cam.import_folder(event, a)
    cam.import_folder(event, b)
    first, second = (s["id"] for s in cam.cameras(event.conn))
    with event.transaction() as conn:
        cam.rename_camera(conn, first, "Máy chính")
        cam.merge_cameras(conn, first, second)
    [only] = cam.cameras(event.conn)
    assert only["display_name"] == "Máy chính" and only["photos"] == 2
