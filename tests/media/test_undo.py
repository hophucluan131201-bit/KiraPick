"""M8 / R1-UNDO-AI: one Ctrl+Z history for Media actions and P / X, checked after EVERY undo.

Cases asked by the review (2026-11-07):
- Tách -> Phân tích lại -> Ctrl+Z: the earlier split comes back, the window is told so (notice);
- the same, interleaved with P / X: after each Ctrl+Z, moments, confirmed labels and the photo choices are checked.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.media import cameras as cam
from app.media import event as ev
from app.media import journal
from app.media import labels as lb
from app.media import moments as mo
from app.media.undo import EventUndo
from app.storage import decisions
from tests.media.fixtures import photo

DAY = datetime(2026, 6, 19, 9, 0, 0)


def _event(tmp_path: Path):  # noqa: ANN202
    shoot = tmp_path / "S"
    times = [0, 60, 120, 1800, 1860]  # 09:00, 09:01, 09:02 | 09:30, 09:31
    for i, t in enumerate(times):
        photo(shoot / f"P{i}.jpg", i, taken=(DAY + timedelta(seconds=t)).strftime("%Y:%m:%d %H:%M:%S"),
              make="NIKON", model="Z 6")
    e = ev.create_event("undo", tmp_path / "media")
    cam.import_folder(e, shoot)
    p = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    mo.analyse(e)
    return e, p


def _state(e, p):  # noqa: ANN001, ANN202
    back = {v: k for k, v in p.items()}
    groups = sorted((sorted(back[a] for a in m.assets), m.pinned) for m in mo.moments(e.conn))
    confirmed = sorted((back[r[0]], r[1]) for r in e.conn.execute(
        "SELECT asset_id, value FROM labels WHERE state = 'confirmed'"))
    flags = {back[a]: decisions.get(e.conn, a).flag for a in p.values() if decisions.get(e.conn, a).flag}
    return groups, confirmed, flags


AI = [(["P0", "P1", "P2"], False), (["P3", "P4"], False)]


def test_split_reanalyse_undo_restores_the_earlier_split_and_says_so(tmp_path: Path) -> None:
    e, p = _event(tmp_path)
    u = EventUndo(e)
    u.media(lb.confirm, [p["P1"]], "shot", "can")
    u.media(mo.split_here, p["P2"])
    assert _state(e, p)[0] == sorted([(["P0", "P1"], True), (["P2"], True), (["P3", "P4"], False)])
    mo.analyse(e, gap_s=30)  # Phân tích lại with a smaller pause: the AI part (P3 / P4) is split again
    assert _state(e, p)[0] == sorted([(["P0", "P1"], True), (["P2"], True), (["P3"], False), (["P4"], False)])
    assert u.notice() is not None and "Phân tích lại" in u.notice()
    done = u.undo()
    assert done.kind == "media" and done.label == "tách khoảnh khắc" and done.notice == u_notice_text("tách khoảnh khắc")
    assert _state(e, p) == (AI, [("P1", "can")], {})  # earlier split back; the confirmed label is kept
    assert u.notice() is None  # the next entry (the label) did not save the moments
    done = u.undo()
    assert (done.label, done.notice) == ("gán Cận", None)
    assert _state(e, p) == (AI, [], {})
    assert u.undo() is None
    e.close()


def u_notice_text(label: str) -> str:
    return journal.RESPLIT_NOTICE.format(label=label)


def test_interleaved_with_p_x_every_undo_checked(tmp_path: Path) -> None:
    e, p = _event(tmp_path)
    u = EventUndo(e)
    u.set_flag([p["P0"]], "keep")  # 1  P on P0
    u.media(lb.confirm, [p["P0"]], "shot", "toan")  # 2  confirmed label
    u.media(mo.split_here, p["P1"])  # 3  Tách tại đây
    u.set_flag([p["P1"], p["P3"]], "reject")  # 4  X on P1 and P3
    mo.analyse(e, gap_s=30)  # 5  Phân tích lại (not an undo step)
    u.set_flag([p["P3"]], "keep")  # 6  P3 changed to P
    after_reanalysis = sorted([(["P0"], True), (["P1", "P2"], True), (["P3"], False), (["P4"], False)])
    assert _state(e, p) == (after_reanalysis, [("P0", "toan")], {"P0": "keep", "P1": "reject", "P3": "keep"})

    assert u.undo().label == "chọn P"  # undo 6
    assert _state(e, p) == (after_reanalysis, [("P0", "toan")], {"P0": "keep", "P1": "reject", "P3": "reject"})
    assert u.undo().label == "loại X"  # undo 4: moments untouched by a P / X undo
    assert _state(e, p) == (after_reanalysis, [("P0", "toan")], {"P0": "keep"})
    done = u.undo()  # undo 3, made before the re-analysis: the earlier split comes back, with the notice
    assert done.label == "tách khoảnh khắc" and done.notice is not None
    assert _state(e, p) == (AI, [("P0", "toan")], {"P0": "keep"})
    assert u.undo().label == "gán Toàn"  # undo 2
    assert _state(e, p) == (AI, [], {"P0": "keep"})
    assert u.undo().label == "chọn P"  # undo 1
    assert _state(e, p) == (AI, [], {})
    assert not u.can_undo()
    e.close()


def test_media_history_survives_reopening_decisions_do_not(tmp_path: Path) -> None:
    e, p = _event(tmp_path)
    u = EventUndo(e)
    u.media(mo.rename, mo.moments(e.conn)[0].id, "Khai mạc")
    u.set_flag([p["P0"]], "keep")
    event_id, root = e.event_id, e.folder.parent
    e.close()
    with ev.open_event(event_id, root) as again:
        u2 = EventUndo(again)
        assert len(u2) == 1 and u2.next_label() == "đổi tên khoảnh khắc"
        u2.undo()
        assert mo.moments(again.conn)[0].name != "Khai mạc"
        assert decisions.get(again.conn, p["P0"]).flag == "keep"  # P / X history is per window, as in Chụp cá nhân
