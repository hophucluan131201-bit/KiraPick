"""M5: label states, labels set by hand, booth names (spec §3, CT-F1/F2/F3, BT-F1) and CAM-04 (a clock change keeps
P/X, labels, pinned moments and booth names)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media import cameras as cam
from app.media import event as ev
from app.media import journal
from app.media import labels as lb
from app.media import moments as mo
from app.storage import decisions
from tests.media.fixtures import photo


@pytest.fixture
def event(tmp_path: Path):  # noqa: ANN201
    a, b = tmp_path / "A", tmp_path / "B"
    for i, t in enumerate(["09:00:00", "09:01:00", "09:02:00", "09:40:00", "09:41:00"]):
        photo(a / f"A{i}.jpg", i, taken=f"2026:06:19 {t}", make="NIKON", model="Z 6")
    photo(b / "B0.jpg", 50, taken="2026:06:19 08:58:30", make="Canon", model="EOS R6")
    e = ev.create_event("Nhãn", tmp_path / "media")
    cam.import_folder(e, a)
    cam.import_folder(e, b)
    mo.analyse(e)
    ids = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    yield e, ids
    e.close()


def _states(e, a: int, grp: str) -> dict[str, str]:  # noqa: ANN001
    return {v: s for v, s, _ in lb.labels_of(e.conn, a).get(grp, [])}


def test_states_and_nothing_overwrites_a_user_decision(event) -> None:  # noqa: ANN001
    e, ids = event
    a = ids["A0"]
    assert "shot" not in lb.labels_of(e.conn, a)  # no row = Đang phân tích
    with e.transaction() as conn:
        lb.write_ai(conn, a, "shot", {}, None)  # AI not sure
    assert _states(e, a, "shot") == {"?": "unknown"}
    with e.transaction() as conn:
        lb.write_ai(conn, a, "shot", {"trung": 0.7}, None)
    assert _states(e, a, "shot") == {"trung": "suggested"}
    lb.confirm(e, [a], "shot", "can")  # key C
    assert _states(e, a, "shot") == {"can": "confirmed"}  # the replaced AI value is 'removed' (hidden)
    with e.transaction() as conn:  # re-analysis: the confirmed size stays, the AI value is not stored
        lb.write_ai(conn, a, "shot", {"toan": 0.9}, None)
    assert _states(e, a, "shot") == {"can": "confirmed"}
    # focus: the user removes an AI warning; re-analysis never suggests it again
    with e.transaction() as conn:
        lb.write_ai(conn, a, "focus", {"out_net": 0.8}, None)
    lb.remove(e, [a], "focus", "out_net")
    with e.transaction() as conn:
        lb.write_ai(conn, a, "focus", {"out_net": 0.9, "trat_net": 0.6}, None)
    assert _states(e, a, "focus") == {"trat_net": "suggested"}
    assert e.conn.execute("SELECT state FROM labels WHERE asset_id = ? AND value = 'out_net'", (a,)).fetchone()[0] \
        == "removed"


def test_ct_f1_f2_content_by_hand_several_per_photo_and_undo(event) -> None:  # noqa: ANN001
    e, ids = event
    assert not lb.content_suggestions_available()  # CT-F1 / F3: CLIP pending -> no AI content, no 'Gợi ý lại'
    photos = [ids["A0"], ids["A1"]]
    for key in "12345":
        lb.toggle_content(e, photos, key)
    assert set(_states(e, ids["A0"], "content")) == set(lb.CONTENT) and \
        set(_states(e, ids["A0"], "content").values()) == {"confirmed"}
    lb.toggle_content(e, photos, "3")  # all already have Decor -> taken away
    assert "decor" not in _states(e, ids["A1"], "content")
    journal.undo(e)
    assert "decor" in _states(e, ids["A1"], "content")
    assert e.conn.execute("SELECT COUNT(*) FROM labels WHERE grp = 'content' AND state = 'suggested'").fetchone()[0] \
        == 0


def test_bt_f1_booth_suggested_within_the_moment_only(event) -> None:  # noqa: ANN001
    e, ids = event
    first = mo.moment_of(e.conn, ids["A0"])
    later = mo.moment_of(e.conn, ids["A3"])
    assert first != later  # 38-minute pause
    lb.assign_booth(e, [ids["A0"]], "VNNIC")
    lb.assign_booth(e, [ids["A3"]], "Viettel")
    lb.confirm(e, [ids["A1"]], "content", "booth")
    n = lb.suggest_booths(e)
    assert lb.booth_of(e.conn, ids["A1"]) == ("VNNIC", "suggested")
    assert lb.booth_of(e.conn, ids["A2"]) == ("VNNIC", "suggested")
    assert lb.booth_of(e.conn, ids["A4"]) == ("Viettel", "suggested")  # its own moment, not across
    assert lb.booth_of(e.conn, ids["A0"]) == ("VNNIC", "confirmed")
    assert n == 4  # A1, A2, B0 (same first moment) and A4
    journal.undo(e)
    assert lb.booth_of(e.conn, ids["A1"]) is None and lb.booth_of(e.conn, ids["A0"]) == ("VNNIC", "confirmed")


def test_cam04_clock_change_keeps_everything_attached_to_the_photo(event) -> None:  # noqa: ANN001
    e, ids = event
    b0 = ids["B0"]
    decisions.set_flag(e.conn, b0, "keep")
    decisions.set_rating(e.conn, b0, 4)
    lb.confirm(e, [b0], "shot", "toan")
    lb.toggle_content(e, [b0], "1")
    lb.assign_booth(e, [b0], "Sân khấu chính")
    pinned = mo.moment_of(e.conn, b0)
    mo.rename(e, pinned, "Khai mạc")
    mo.set_clock(e, cam.camera_of(e.conn, b0), 90)
    assert decisions.get(e.conn, b0).flag == "keep" and decisions.get(e.conn, b0).rating == 4
    assert _states(e, b0, "shot") == {"toan": "confirmed"} and _states(e, b0, "content") == {"san_khau": "confirmed"}
    assert lb.booth_of(e.conn, b0) == ("Sân khấu chính", "confirmed")
    assert mo.moment_of(e.conn, b0) == pinned  # pinned moment keeps its photo list


def test_shot_coverage_of_a_moment_over_p_photos(event) -> None:  # noqa: ANN001
    e, ids = event
    m = mo.moment_of(e.conn, ids["A0"])
    lb.confirm(e, [ids["A0"]], "shot", "toan")
    lb.confirm(e, [ids["A1"]], "shot", "can")
    decisions.set_flag(e.conn, ids["A0"], "keep")
    assert lb.shot_coverage(e.conn, m) == {"toan": True, "trung": False, "can": False}  # A1 is not P
