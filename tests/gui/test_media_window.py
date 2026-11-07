"""M8, offscreen: event list -> import -> analyse -> filter -> edit -> undo, and leaving / reopening keeps the data.

The analysis runs in the window's worker thread with a stand-in detector (the real one runs in a child process with
YOLOX / YuNet; that path is covered by tests/media/test_shot.py with the dev weights). This is GUI logic, not a test
of the AI on real photos.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt

from app.media import analysis
from app.media import event as ev
from app.media import labels as lb
from app.media import moments as mo
from app.storage import decisions
from app.storage.project import Project
from app.ui.media_home import MediaHome
from tests.media.fixtures import hashes, photo

DAY = datetime(2026, 6, 19, 9, 0, 0)
FACE = {0: 0.3, 1: 0.08, 2: 0.02, 3: 0.3, 4: None}  # by import order: Cận, Trung, Toàn, Cận, Chưa xác định


def _runner(folder: Path, progress, cancelled) -> dict:  # noqa: ANN001
    seen = []

    def detect(bgr):  # noqa: ANN001, ANN202
        f = FACE.get(len(seen))
        seen.append(1)
        h, w = bgr.shape[:2]
        if f is None:
            return [], []
        return [((w * 0.3, h * 0.05, w * 0.4, h * 0.9), 0.9)], [((w * 0.45, h * 0.1, f * h * 0.8, f * h), 0.95)]

    with Project.open(folder) as event:
        return asdict(analysis.analyse_event(event, detect=detect, progress=progress, should_cancel=cancelled,
                                             load_full=lambda p: np.full((240, 320), 120, np.uint8)))


@pytest.fixture
def home(qtbot, tmp_path: Path):  # noqa: ANN001, ANN201
    shoot = tmp_path / "Shoot"
    for i, t in enumerate([0, 60, 120, 1800, 1860]):
        photo(shoot / f"DSC_{i:04d}.jpg", i, taken=(DAY + timedelta(seconds=t)).strftime("%Y:%m:%d %H:%M:%S"),
              make="NIKON", model="Z 6")
    h = MediaHome(root=tmp_path / "media", analysis_runner=_runner)
    qtbot.addWidget(h)
    h.resize(1400, 900)
    h.show()
    qtbot.waitExposed(h)
    h.shoot = shoot
    return h


def _names(view) -> list[str]:  # noqa: ANN001
    return [r.name for r in view.model.records()]


def _ids(view) -> dict[str, int]:  # noqa: ANN001
    return {Path(r[1]).stem: r[0] for r in view.media_event.conn.execute("SELECT id, relative_path FROM assets")}


def _import_and_analyse(qtbot, home):  # noqa: ANN001, ANN202
    view = home.view
    view.start_import(home.shoot)
    qtbot.waitUntil(lambda: view.import_thread is None, timeout=30000)
    assert len(_names(view)) == 5
    view.start_analysis()
    qtbot.waitUntil(lambda: view.analysis_thread is None, timeout=30000)
    return view


def test_import_analyse_filter_edit_undo(qtbot, home) -> None:  # noqa: ANN001
    before = hashes(home.shoot)
    home.create("Hội nghị VNNIC")
    view = _import_and_analyse(qtbot, home)
    assert "Đã phân tích 5 ảnh" in view.status.text() and lb.EXPERIMENTAL in view.status.text()
    assert view.moment_strip.count() == 2
    ids = _ids(view)

    # the three Mốc 1 filter groups
    view.shot_filter.setCurrentIndex(view.shot_filter.findData("can"))
    assert _names(view) == ["DSC_0000.jpg", "DSC_0003.jpg"]
    assert view.model.info[ids["DSC_0000"]].lines() == [f"Cận {lb.EXPERIMENTAL}"]
    view.shot_filter.setCurrentIndex(0)
    view.focus_filter.setCurrentIndex(view.focus_filter.findData(lb.UNKNOWN))
    assert len(_names(view)) == 5  # synthetic flat photos: "không đo được", never a fake warning
    view.focus_filter.setCurrentIndex(0)

    # keys: T (shot), 2 (content), P / X
    view.select([ids["DSC_0004"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_T)
    assert lb.labels_of(view.media_event.conn, ids["DSC_0004"])["shot"] == [("toan", "confirmed", None)]
    view.select([ids["DSC_0003"], ids["DSC_0004"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_2)
    view.content_filter.setCurrentIndex(view.content_filter.findData("booth"))
    assert _names(view) == ["DSC_0003.jpg", "DSC_0004.jpg"]
    view.content_filter.setCurrentIndex(0)
    view.select([ids["DSC_0001"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_P)
    view.select([ids["DSC_0002"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_X)
    view.flag_filter.setCurrentIndex(view.flag_filter.findData("keep"))
    assert _names(view) == ["DSC_0001.jpg"]
    view.flag_filter.setCurrentIndex(0)

    # undo, newest first: X, P, content, T
    for expected in ("loại X", "chọn P", "Booth / Gian hàng", "gán Toàn"):
        qtbot.keyClick(view.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert expected in view.status.text()
    conn = view.media_event.conn
    assert decisions.get(conn, ids["DSC_0001"]).flag is None and decisions.get(conn, ids["DSC_0002"]).flag is None
    assert "content" not in lb.labels_of(conn, ids["DSC_0003"]) or not lb.labels_of(conn, ids["DSC_0003"])["content"]
    assert lb.labels_of(conn, ids["DSC_0004"])["shot"] == [("?", "unknown", None)]
    assert hashes(home.shoot) == before


def test_r1_undo_ai_split_reanalyse_undo_with_p_x_in_the_window(qtbot, home) -> None:  # noqa: ANN001
    home.create("R1")
    view = _import_and_analyse(qtbot, home)
    ids = _ids(view)
    conn = view.media_event.conn
    view.select([ids["DSC_0000"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_C)  # confirmed label
    view.select([ids["DSC_0001"]])
    view.split_here()  # Tách tại đây
    assert len(mo.moments(conn)) == 3
    view.select([ids["DSC_0003"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_P)  # P after the split
    view.start_analysis()  # Phân tích lại
    qtbot.waitUntil(lambda: view.analysis_thread is None, timeout=30000)
    view.select([ids["DSC_0004"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_X)
    split_state = sorted(len(m.assets) for m in mo.moments(conn))

    qtbot.keyClick(view.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # X
    assert decisions.get(conn, ids["DSC_0004"]).flag is None and sorted(len(m.assets) for m in mo.moments(conn)) == \
        split_state
    qtbot.keyClick(view.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # P
    assert decisions.get(conn, ids["DSC_0003"]).flag is None and len(mo.moments(conn)) == 3
    qtbot.keyClick(view.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # the split, before re-analysis
    assert "khôi phục cách chia khoảnh khắc trước đó" in view.status.text()
    assert sorted(len(m.assets) for m in mo.moments(conn)) == [2, 3] and view.moment_strip.count() == 2
    assert [x[:2] for x in lb.labels_of(conn, ids["DSC_0000"])["shot"]] == [("can", "confirmed")]
    qtbot.keyClick(view.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # the label
    assert "khôi phục" not in view.status.text()
    assert lb.labels_of(conn, ids["DSC_0000"])["shot"][0][1] == "suggested"


def test_leaving_and_reopening_keeps_everything_and_delete_keeps_photos(qtbot, home) -> None:  # noqa: ANN001
    before = hashes(home.shoot)
    home.create("Giữ dữ liệu")
    view = _import_and_analyse(qtbot, home)
    ids = _ids(view)
    view.select([ids["DSC_0002"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_P)
    qtbot.keyClick(view.grid, Qt.Key.Key_U)
    view.rename_moment("Khai mạc")
    view.back_button.click()
    assert home.view is None and home.media_event is None and home.events.count() == 1
    home.open_selected()
    conn = home.view.media_event.conn
    assert decisions.get(conn, ids["DSC_0002"]).flag == "keep"
    assert lb.labels_of(conn, ids["DSC_0002"])["shot"] == [("trung", "confirmed", None)]
    assert any(m.name == "Khai mạc" for m in mo.moments(conn))
    assert home.view.undo.next_label() == "đổi tên khoảnh khắc"  # Media history survives, P/X history does not
    home.view.back_button.click()
    assert home.delete_selected(confirm=False) and home.events.count() == 0
    assert ev.list_events(home.root) == []
    assert hashes(home.shoot) == before  # deleting an event never touches a photo
