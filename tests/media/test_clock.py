"""M3: clock offsets per camera source, from a pair of photos or seconds, undo; EXIF and capture_time unchanged (CAM-04
is completed in M4 / M5 with moments and labels)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media import cameras as cam
from app.media import clock, journal
from app.media import event as ev
from app.storage import decisions
from tests.media.fixtures import hashes, photo


@pytest.fixture
def two_cameras(tmp_path: Path):  # noqa: ANN201
    a, b = tmp_path / "A", tmp_path / "B"
    photo(a / "A1.jpg", 1, taken="2026:06:19 10:00:00", make="NIKON", model="Z 6")
    photo(b / "B1.jpg", 2, taken="2026:06:19 09:57:00", make="NIKON", model="Z 6")  # camera B is 3 minutes slow
    e = ev.create_event("Lệch giờ", tmp_path / "media")
    cam.import_folder(e, a)
    cam.import_folder(e, b)
    ids = {r[1]: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    yield e, ids, (a, b)
    e.close()


def test_offset_from_a_pair_then_undo(two_cameras) -> None:  # noqa: ANN001
    e, ids, folders = two_cameras
    before_files = [hashes(f) for f in folders]
    before_db = [tuple(r) for r in e.conn.execute("SELECT id, capture_time, exif_json FROM assets ORDER BY id")]
    b_cam = cam.camera_of(e.conn, ids["B1.jpg"])
    decisions.set_flag(e.conn, ids["B1.jpg"], "keep")
    seconds = clock.offset_from_pair(e.conn, ids["A1.jpg"], ids["B1.jpg"])
    assert seconds == 180.0
    clock.set_offset(e, b_cam, seconds)
    times = clock.corrected_times(e.conn)
    assert times[ids["A1.jpg"]] == times[ids["B1.jpg"]]
    assert [tuple(r) for r in e.conn.execute("SELECT id, capture_time, exif_json FROM assets ORDER BY id")] == before_db
    assert [hashes(f) for f in folders] == before_files  # nothing written into the photos
    assert decisions.get(e.conn, ids["B1.jpg"]).flag == "keep"
    assert journal.undo(e) == f"chỉnh giờ nguồn {b_cam}"
    assert clock.offset(e.conn, b_cam) == 0.0
    assert clock.corrected_times(e.conn)[ids["B1.jpg"]] - clock.corrected_times(e.conn)[ids["A1.jpg"]] == -180.0
    assert journal.undo(e) is None


def test_seconds_entered_by_hand_and_a_second_change(two_cameras) -> None:  # noqa: ANN001
    e, ids, _ = two_cameras
    b_cam = cam.camera_of(e.conn, ids["B1.jpg"])
    clock.set_offset(e, b_cam, 120)
    clock.set_offset(e, b_cam, 180)
    assert clock.offset(e.conn, b_cam) == 180
    journal.undo(e)
    assert clock.offset(e.conn, b_cam) == 120  # one step back, not to zero
    journal.undo(e)
    assert clock.offset(e.conn, b_cam) == 0


def test_photo_without_time_has_no_corrected_time(tmp_path: Path) -> None:
    shoot = tmp_path / "S"
    photo(shoot / "x.jpg", 1, make="NIKON", model="Z 6")
    with ev.create_event("x", tmp_path / "media") as e:
        cam.import_folder(e, shoot)
        (asset,) = clock.corrected_times(e.conn).items()
        assert asset[1] is None
        with pytest.raises(ValueError, match="không có giờ"):
            clock.offset_from_pair(e.conn, asset[0], asset[0])


def test_history_survives_reopening_and_is_bounded(two_cameras, tmp_path: Path) -> None:  # noqa: ANN001
    e, ids, _ = two_cameras
    b_cam = cam.camera_of(e.conn, ids["B1.jpg"])
    for s in range(journal.MAX_ENTRIES + 5):
        clock.set_offset(e, b_cam, s + 1)
    assert e.conn.execute("SELECT COUNT(*) FROM media_journal").fetchone()[0] == journal.MAX_ENTRIES
    event_id = e.event_id
    e.close()
    with ev.open_event(event_id, tmp_path / "media") as again:
        journal.undo(again)
        assert clock.offset(again.conn, b_cam) == journal.MAX_ENTRIES + 4
