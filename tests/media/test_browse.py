"""M8: the three Mốc 1 filter groups + source / moment / state / P-X, and corrected-time order."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.media import analysis
from app.media import cameras as cam
from app.media import clock
from app.media import event as ev
from app.media import labels as lb
from app.media import moments as mo
from app.media.browse import MediaFilter, card_info, matching_ids
from app.storage import decisions
from tests.media.fixtures import photo

DAY = datetime(2026, 6, 19, 9, 0, 0)


def _at(s: int) -> str:
    return (DAY + timedelta(seconds=s)).strftime("%Y:%m:%d %H:%M:%S")


def test_filters_and_order(tmp_path: Path) -> None:
    a, b = tmp_path / "A", tmp_path / "B"
    for i, t in enumerate([0, 60, 120]):
        photo(a / f"A{i}.jpg", i, taken=_at(t), make="NIKON", model="Z 6")
    for i, t in enumerate([30, 90]):  # camera B is 100 s slow: recorded -70 and -10, really 30 and 90
        photo(b / f"B{i}.jpg", 10 + i, taken=_at(t - 100), make="Canon", model="R6")
    e = ev.create_event("browse", tmp_path / "media")
    cam.import_folder(e, a)
    cam.import_folder(e, b)
    p = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    names = {v: k for k, v in p.items()}

    def shown(**kw) -> list[str]:  # noqa: ANN003
        return [names[i] for i in matching_ids(e.conn, MediaFilter(**kw))]

    assert shown() == ["B0", "B1", "A0", "A1", "A2"]  # capture time as recorded
    b_cam = cam.camera_of(e.conn, p["B0"])
    clock.set_offset(e, b_cam, 100)
    assert shown() == ["A0", "B0", "A1", "B1", "A2"]  # corrected time
    assert shown(camera_id=b_cam) == ["B0", "B1"]
    assert shown(state="waiting") == ["A0", "B0", "A1", "B1", "A2"]

    sizes = {"A0": 0.3, "A1": 0.08, "A2": None, "B0": 0.02, "B1": 0.3}
    order = ["A0", "A1", "A2", "B0", "B1"]  # the job goes through the photos in import order

    def detect(bgr):  # noqa: ANN001, ANN202
        name = order[detect.n]
        detect.n += 1
        f = sizes[name]
        if f is None:
            return [], []
        h, w = bgr.shape[:2]
        return [((w * 0.3, h * 0.05, w * 0.4, h * 0.9), 0.9)], [((w * 0.45, h * 0.1, f * h * 0.8, f * h), 0.95)]

    detect.n = 0
    analysis.analyse_event(e, detect=detect, load_full=lambda path: __import__("numpy").full((240, 320), 120, "uint8"))
    assert shown(state="waiting") == []
    assert shown(shot="can") == ["A0", "B1"] and shown(shot="trung") == ["A1"] and shown(shot="?") == ["A2"]
    lb.confirm(e, [p["B1"]], "shot", "toan")
    assert shown(shot="can") == ["A0"] and shown(shot="toan") == ["B0", "B1"]
    assert shown(state="confirmed") == ["B1"]
    lb.toggle_content(e, [p["A0"], p["A1"]], "1")
    assert shown(content="san_khau") == ["A0", "A1"] and shown(content="none") == ["B0", "B1", "A2"]
    assert shown(focus="none") == []  # every photo here is flat: '?' (could not be measured), not 'no warning'
    assert shown(focus="?") == ["A0", "B0", "A1", "B1", "A2"]
    decisions.set_flag(e.conn, p["A1"], "keep")
    decisions.set_flag(e.conn, p["B0"], "reject")
    assert shown(flag="keep") == ["A1"] and shown(flag="reject") == ["B0"]
    assert shown(flag="unflagged") == ["A0", "B1", "A2"]
    m = mo.moment_of(e.conn, p["A0"])
    assert shown(moment_id=m) == ["A0", "B0", "A1", "B1", "A2"]
    assert shown(shot="can", content="san_khau", flag="unflagged") == ["A0"]  # groups combine

    info = card_info(e.conn)
    assert info[p["A0"]].lines() == [f"Cận {lb.EXPERIMENTAL}"]
    assert info[p["B1"]].lines() == ["Toàn"]  # the user's: no "(thử nghiệm)"
    assert info[p["A2"]].lines() == ["Chưa xác định"]
    e.close()
