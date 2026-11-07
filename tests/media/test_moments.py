"""M4: moments — AI split by pauses (MT-F1), 📌 user edits kept, ⚠ drift rule and undo (MED-03 S0–S4, 03b, 03c, 03d)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.media import cameras as cam
from app.media import event as ev
from app.media import journal
from app.media import moments as mo
from app.storage import decisions
from tests.media.fixtures import photo

EXIF = "%Y:%m:%d %H:%M:%S"
DAY = datetime(2026, 6, 19)


def _at(hms: str, minus_s: int = 0) -> str:
    h, m, s = (int(x) for x in hms.split(":"))
    return (DAY.replace(hour=h, minute=m, second=s) - timedelta(seconds=minus_s)).strftime(EXIF)


@pytest.fixture
def med03(tmp_path: Path):  # noqa: ANN201
    """Spec §8 MED-03: camera A on time, camera B 180 s slow."""
    a, b = tmp_path / "MayA", tmp_path / "MayB"
    for i, t in enumerate(["10:00:00", "10:01:00", "10:02:00", "10:03:00", "10:04:00"], start=1):
        photo(a / f"A-{i:02d}.jpg", i, taken=_at(t), make="NIKON", model="Z 6")
    for i, t in enumerate(["10:05:00", "10:06:00", "10:07:00", "10:08:00", "10:09:00"], start=6):
        photo(a / f"A-{i:02d}.jpg", i, taken=_at(t), make="NIKON", model="Z 6")
    real_b = ["10:00:30", "10:01:30", "10:02:30", "10:03:30", "10:04:00", "10:04:30", "10:05:20",
              "10:08:30", "10:09:00", "10:09:30"]
    for i, t in enumerate(real_b, start=1):
        photo(b / f"B-{i:02d}.jpg", 100 + i, taken=_at(t, minus_s=180), make="Canon", model="EOS R6")
    e = ev.create_event("MED-03", tmp_path / "media")
    cam.import_folder(e, a)
    cam.import_folder(e, b)
    ids = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    yield e, ids
    e.close()


def _names(e, ids: dict) -> list[list[str]]:  # noqa: ANN001
    back = {v: k for k, v in ids.items()}
    return [sorted(back[a] for a in m.assets) for m in mo.moments(e.conn)]


PHAT_BIEU_S0 = sorted([f"A-{i:02d}" for i in range(1, 6)] + [f"B-{i:02d}" for i in range(1, 8)])
TRAO_GIAI_S0 = sorted([f"A-{i:02d}" for i in range(6, 11)] + [f"B-{i:02d}" for i in range(8, 11)])


def test_med03_s0_to_s4(med03) -> None:  # noqa: ANN001
    e, ids = med03
    mo.analyse(e)
    assert len(mo.moments(e.conn)) == 1  # no pause > 5 min: one AI moment
    decisions.set_flag(e.conn, ids["B-07"], "keep")
    # S0: 'Tách tại đây' just before A-6, before any clock change
    trao = mo.split_here(e, ids["A-06"])
    phat = next(m.id for m in mo.moments(e.conn) if m.id != trao)
    assert _names(e, ids) == [PHAT_BIEU_S0, TRAO_GIAI_S0]
    assert all(m.pinned for m in mo.moments(e.conn))
    b_cam = cam.camera_of(e.conn, ids["B-01"])
    # S1: camera B +180 s -> pinned moments unchanged, only B-7 warned, suggested 'Trao giải'
    mo.set_clock(e, b_cam, 180)
    assert _names(e, ids) == [PHAT_BIEU_S0, TRAO_GIAI_S0]
    assert mo.warnings(e.conn) == {ids["B-07"]: trao}  # B-6 (overlap, 03b) and A-6 (not checked, 03d): no ⚠
    # S2: 'Chuyển'
    mo.accept_warning(e, ids["B-07"])
    assert mo.moment_of(e.conn, ids["B-07"]) == trao and mo.warnings(e.conn) == {}
    # re-analysis at S2: pinned moments unchanged, no ⚠ created
    mo.analyse(e)
    assert mo.moment_of(e.conn, ids["B-07"]) == trao and mo.warnings(e.conn) == {}
    # S3: Ctrl+Z -> back to S1
    assert journal.undo(e) == "chuyển ảnh lệch giờ"
    assert _names(e, ids) == [PHAT_BIEU_S0, TRAO_GIAI_S0] and mo.warnings(e.conn) == {ids["B-07"]: trao}
    # S4: Ctrl+Z again -> clock back to 0, its warnings gone: S0
    assert journal.undo(e).startswith("chỉnh giờ")
    assert _names(e, ids) == [PHAT_BIEU_S0, TRAO_GIAI_S0] and mo.warnings(e.conn) == {}
    assert mo.moment_of(e.conn, ids["B-07"]) == phat
    assert decisions.get(e.conn, ids["B-07"]).flag == "keep"  # P/X of B-7 never changed


def test_med03_keep_clears_the_warning_and_undo_brings_it_back(med03) -> None:  # noqa: ANN001
    e, ids = med03
    mo.analyse(e)
    mo.split_here(e, ids["A-06"])
    mo.set_clock(e, cam.camera_of(e.conn, ids["B-01"]), 180)
    mo.keep_warning(e, ids["B-07"])
    assert mo.warnings(e.conn) == {}
    journal.undo(e)
    assert ids["B-07"] in mo.warnings(e.conn)


def test_med03c_no_reference_range_no_warning(tmp_path: Path) -> None:
    """A pinned moment with B photos and only one A photo: fewer than 2 non-B photos -> no range, no ⚠."""
    a, b = tmp_path / "A", tmp_path / "B"
    photo(a / "A1.jpg", 1, taken=_at("09:00:00"), make="NIKON", model="Z 6")
    for i in range(3):
        photo(b / f"B{i}.jpg", 10 + i, taken=_at(f"09:00:{10 * i:02d}", minus_s=0), make="Canon", model="R6")
    # a second moment of A photos far later, so a moved B photo could land in its range
    for i in range(3):
        photo(a / f"A2{i}.jpg", 20 + i, taken=_at(f"09:30:{10 * i:02d}"), make="NIKON", model="Z 6")
    with ev.create_event("03c", tmp_path / "media") as e:
        cam.import_folder(e, a)
        cam.import_folder(e, b)
        mo.analyse(e)
        first = mo.moments(e.conn)[0]
        mo.rename(e, first.id, "Mở màn")  # pinned
        b_cam = next(c["id"] for c in cam.cameras(e.conn) if c["make"] == "Canon")
        mo.set_clock(e, b_cam, 1800)  # B photos now at 09:30, inside the second moment's range
        assert mo.warnings(e.conn) == {}


def test_mt_f1_split_by_pause_and_no_time_moment(tmp_path: Path) -> None:
    shoot = tmp_path / "S"
    for i, t in enumerate(["09:00:00", "09:01:00", "09:20:00", "09:21:00"]):
        photo(shoot / f"P{i}.jpg", i, taken=_at(t), make="NIKON", model="Z 6")
    photo(shoot / "notime.jpg", 9, make="NIKON", model="Z 6")
    with ev.create_event("MT", tmp_path / "media") as e:
        cam.import_folder(e, shoot)
        mo.analyse(e)
        ms = mo.moments(e.conn)
        assert [len(m.assets) for m in ms] == [2, 2, 1]
        assert ms[-1].no_time and ms[-1].name == mo.NO_TIME_NAME
        assert ms[0].name == "Khoảnh khắc 09:00"


def test_pinned_moments_survive_reanalysis_and_ai_part_is_resplit(tmp_path: Path) -> None:
    shoot = tmp_path / "S"
    for i, t in enumerate(["09:00:00", "09:01:00", "09:02:00", "09:30:00", "09:31:00"]):
        photo(shoot / f"P{i}.jpg", i, taken=_at(t), make="NIKON", model="Z 6")
    with ev.create_event("pin", tmp_path / "media") as e:
        cam.import_folder(e, shoot)
        mo.analyse(e)
        first = mo.moments(e.conn)[0]
        p = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
        new_id = mo.split_here(e, p["P2"])  # pinned: [P0, P1] and [P2]
        mo.analyse(e, gap_s=30)  # a much smaller pause would split everything - except pinned moments
        ms = {m.id: sorted(m.assets) for m in mo.moments(e.conn)}
        assert ms[first.id] == sorted([p["P0"], p["P1"]]) and ms[new_id] == [p["P2"]]
        assert len(ms) == 4  # P3 and P4 are 60 s apart > 30 s: two AI moments
        journal.undo(e)  # undo the split: one AI moment of 3 again, P3/P4 as split by the last analysis
        assert first.id in {m.id for m in mo.moments(e.conn)}


def test_merge_move_rename_are_undoable(tmp_path: Path) -> None:
    shoot = tmp_path / "S"
    for i, t in enumerate(["09:00:00", "09:30:00", "10:00:00"]):
        photo(shoot / f"P{i}.jpg", i, taken=_at(t), make="NIKON", model="Z 6")
    with ev.create_event("edit", tmp_path / "media") as e:
        cam.import_folder(e, shoot)
        mo.analyse(e)
        m1, m2, m3 = mo.moments(e.conn)
        mo.merge(e, m1.id, m2.id)
        assert [len(m.assets) for m in mo.moments(e.conn)] == [2, 1]
        mo.move_photos(e, list(m3.assets), m1.id)
        assert [len(m.assets) for m in mo.moments(e.conn)] == [3]
        mo.rename(e, m1.id, "Khai mạc")
        assert mo.moments(e.conn)[0].name == "Khai mạc"
        for _ in range(3):
            journal.undo(e)
        assert [len(m.assets) for m in mo.moments(e.conn)] == [1, 1, 1]
