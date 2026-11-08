"""Media event window (the Chụp cá nhân 3.0.0 window on an event), offscreen: event list -> import -> analyse ->
filter -> keys -> undo -> leave / reopen; export; sample labelling; 3.0.0 parity (keys, tick box, compare, filters).

The analysis runs in the window's worker thread with a stand-in detector (the real one runs in a child process with
YOLOX / YuNet; covered by tests/media/test_shot.py with the dev weights). GUI logic, not a test of the AI.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QItemSelectionModel, Qt

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
ALT = Qt.KeyboardModifier.AltModifier


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
    from PySide6.QtCore import QSettings

    shoot = tmp_path / "Shoot"
    for i, t in enumerate([0, 60, 120, 1800, 1860]):
        photo(shoot / f"DSC_{i:04d}.jpg", i, taken=(DAY + timedelta(seconds=t)).strftime("%Y:%m:%d %H:%M:%S"),
              make="NIKON", model="Z 6")
    h = MediaHome(root=tmp_path / "media", analysis_runner=_runner,
                  settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(h)
    h.resize(1400, 900)
    h.show()
    qtbot.waitExposed(h)
    h.shoot = shoot
    yield h
    w = h.event_window
    if w is not None:
        w._shutdown_ready = False
        w._switching_mode = True
        w.close()


def _open(qtbot, home, name: str):  # noqa: ANN001, ANN202
    home.create(name)
    w = home.event_window
    w._maximize_on_show = False
    w.resize(1500, 950)
    qtbot.waitExposed(w)
    w.activateWindow()
    return w


def _names(w) -> list[str]:  # noqa: ANN001
    return [r.name for r in w.model.records()]


def _ids(w) -> dict[str, int]:  # noqa: ANN001
    return {Path(r[1]).stem: r[0] for r in w.project.conn.execute("SELECT id, relative_path FROM assets")}


def _select(w, ids: list[int]) -> None:  # noqa: ANN001
    sel = w.grid.selectionModel()
    sel.clearSelection()
    for i, a in enumerate(ids):
        idx = w.model.index_of(a)
        if i == 0:
            sel.setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)
        sel.select(idx, QItemSelectionModel.SelectionFlag.Select)
    w.grid.setFocus()


def _import(qtbot, w, folder: Path) -> None:  # noqa: ANN001
    w.start_import(folder)
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=30000)


def _import_and_analyse(qtbot, home, name: str):  # noqa: ANN001, ANN202
    w = _open(qtbot, home, name)
    _import(qtbot, w, home.shoot)
    assert len(_names(w)) == 5
    w.start_analysis("people")
    qtbot.waitUntil(lambda: w.analyze_thread is None, timeout=30000)
    return w


def test_same_window_as_3_0_0_with_media_parts(qtbot, home) -> None:  # noqa: ANN001
    """The event window is the 3.0.0 window: same top bar steps (Nhập ảnh, 🧠, Xuất ảnh), bottom bar, sidebar
    P/X filters, Compare page, detail panel; Media adds the event / filters / moments sections."""
    from app.ui.main_window import MainWindow

    w = _open(qtbot, home, "Giao diện")
    assert isinstance(w, MainWindow)
    visible = [k for k, b in w.top_bar.buttons.items() if not b.isHidden()]
    assert visible == ["import", "people", "export"]
    assert "Phân tích sự kiện" in w.top_bar.buttons["people"].text()
    assert not w.sections["people"].isVisible() and w.sections["filters"].isVisible()
    assert w.sections["moments"].isVisible() and w.sections["media_filters"].isVisible()
    for name in ("bottom_bar", "compare", "viewer", "detail", "search"):
        assert getattr(w, name) is not None


def test_import_analyse_filter_edit_undo(qtbot, home) -> None:  # noqa: ANN001
    before = hashes(home.shoot)
    w = _import_and_analyse(qtbot, home, "Hội nghị VNNIC")
    assert "Đã phân tích 5 ảnh" in w.status.text() and lb.EXPERIMENTAL in w.status.text()
    assert w.moment_list.count() == 3  # "Tất cả" + 2 moments
    ids = _ids(w)
    w.shot_filter.setCurrentIndex(w.shot_filter.findData("can"))
    assert _names(w) == ["DSC_0000.jpg", "DSC_0003.jpg"]
    assert w.model.info[ids["DSC_0000"]].lines() == [f"Cận {lb.EXPERIMENTAL}"]
    w.shot_filter.setCurrentIndex(0)
    w.focus_filter.setCurrentIndex(w.focus_filter.findData(lb.UNKNOWN))
    assert len(_names(w)) == 5  # flat synthetic photos: "không đo được", never a fake warning
    w.focus_filter.setCurrentIndex(0)
    _select(w, [ids["DSC_0004"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_T, ALT)
    assert lb.labels_of(w.project.conn, ids["DSC_0004"])["shot"] == [("toan", "confirmed", None)]
    _select(w, [ids["DSC_0003"], ids["DSC_0004"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_2, ALT)
    w.content_filter.setCurrentIndex(w.content_filter.findData("booth"))
    assert _names(w) == ["DSC_0003.jpg", "DSC_0004.jpg"]
    w.content_filter.setCurrentIndex(0)
    _select(w, [ids["DSC_0001"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    _select(w, [ids["DSC_0002"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_X)
    for expected in ("Loại", "Chọn", "Booth / Gian hàng", "gán Toàn"):
        qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert expected in w.status.text(), w.status.text()
    conn = w.project.conn
    assert decisions.get(conn, ids["DSC_0001"]).flag is None and decisions.get(conn, ids["DSC_0002"]).flag is None
    assert not lb.labels_of(conn, ids["DSC_0003"]).get("content")
    assert lb.labels_of(conn, ids["DSC_0004"])["shot"] == [("?", "unknown", None)]
    assert hashes(home.shoot) == before


def test_r1_undo_ai_split_reanalyse_undo_with_p_x(qtbot, home) -> None:  # noqa: ANN001
    w = _import_and_analyse(qtbot, home, "R1")
    ids = _ids(w)
    conn = w.project.conn
    _select(w, [ids["DSC_0000"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_C, ALT)  # confirmed label
    _select(w, [ids["DSC_0001"]])
    w.split_here()
    assert len(mo.moments(conn)) == 3
    _select(w, [ids["DSC_0003"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    w.start_analysis("people")  # Phân tích lại
    qtbot.waitUntil(lambda: w.analyze_thread is None, timeout=30000)
    _select(w, [ids["DSC_0004"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_X)
    split_state = sorted(len(m.assets) for m in mo.moments(conn))
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # X
    assert decisions.get(conn, ids["DSC_0004"]).flag is None
    assert sorted(len(m.assets) for m in mo.moments(conn)) == split_state
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # P
    assert decisions.get(conn, ids["DSC_0003"]).flag is None and len(mo.moments(conn)) == 3
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # the split, before re-analysis
    assert "khôi phục cách chia khoảnh khắc trước đó" in w.status.text()
    assert sorted(len(m.assets) for m in mo.moments(conn)) == [2, 3]
    assert [x[:2] for x in lb.labels_of(conn, ids["DSC_0000"])["shot"]] == [("can", "confirmed")]
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # the label
    assert "khôi phục" not in w.status.text()
    assert lb.labels_of(conn, ids["DSC_0000"])["shot"][0][1] == "suggested"


def test_leaving_and_reopening_keeps_everything_and_delete_keeps_photos(qtbot, home) -> None:  # noqa: ANN001
    before = hashes(home.shoot)
    w = _import_and_analyse(qtbot, home, "Giữ dữ liệu")
    ids = _ids(w)
    _select(w, [ids["DSC_0002"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    qtbot.keyClick(w.grid, Qt.Key.Key_U, ALT)
    w.rename_moment("Khai mạc")
    w._ask_leave_mode = lambda: True
    w.events_button.click()  # ⟵ Danh sách sự kiện
    qtbot.waitUntil(lambda: home.isVisible() and home.event_window is None, timeout=15000)
    assert home.events.count() == 1
    home.open_selected()
    w2 = home.event_window
    conn = w2.project.conn
    assert decisions.get(conn, ids["DSC_0002"]).flag == "keep"
    assert [x[:2] for x in lb.labels_of(conn, ids["DSC_0002"])["shot"]] == [("trung", "confirmed")]
    assert any(m.name == "Khai mạc" for m in mo.moments(conn))
    assert w2.undo.next_label() == "đổi tên khoảnh khắc"  # Media history survives, P/X history does not
    w2._ask_leave_mode = lambda: True
    w2.events_button.click()
    qtbot.waitUntil(lambda: home.isVisible() and home.event_window is None, timeout=15000)
    assert home.delete_selected(confirm=False) and home.events.count() == 0
    assert ev.list_events(home.root) == []
    assert hashes(home.shoot) == before


def test_export_dialog_previews_then_copies_p_photos(qtbot, home, tmp_path: Path) -> None:  # noqa: ANN001
    from app.media import export as mx

    before = hashes(home.shoot)
    w = _open(qtbot, home, "Xuất")
    _import(qtbot, w, home.shoot)
    ids = _ids(w)
    _select(w, [ids["DSC_0000"], ids["DSC_0003"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    dialog = w.open_export_dialog()  # ⤴ Xuất ảnh (Ctrl+E), the same step as 3.0.0
    qtbot.addWidget(dialog)
    out = tmp_path / "Giao khách"
    dialog.dest.setText(str(out))
    assert not dialog.copy_button.isEnabled()
    assert dialog.preview() is not None and "2 ảnh P → 2 tệp" in dialog.summary.text()
    dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.thread is None, timeout=30000)
    assert "Đã sao chép 2 tệp" in dialog.summary.text()
    assert sorted(p.name for p in (out / mx.NO_MOMENT).iterdir()) == ["DSC_0000.jpg", "DSC_0003.jpg"]
    assert hashes(home.shoot) == before


def test_sample_labelling_mode_writes_reference_answers_only(qtbot, home) -> None:  # noqa: ANN001
    from app.media import samples as sm

    w = _import_and_analyse(qtbot, home, "Mẫu")
    ids = _ids(w)
    conn = w.project.conn
    working = list(conn.execute("SELECT * FROM labels ORDER BY asset_id, grp, value"))
    w.sample_button.setChecked(True)
    _select(w, [ids["DSC_0001"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_C, ALT)
    qtbot.keyClick(w.grid, Qt.Key.Key_W)
    qtbot.keyClick(w.grid, Qt.Key.Key_3, ALT)
    qtbot.keyClick(w.grid, Qt.Key.Key_B)
    assert sm.samples_of(conn, ids["DSC_0001"]) == {"boundary": ["start"], "content": ["decor"], "focus": ["out_net"],
                                                   "shot": ["can"]}
    assert "Mẫu: Cận, Out nét, Decor" in w.media_info.text()
    qtbot.keyClick(w.grid, Qt.Key.Key_C, ALT)  # the same key takes it away
    assert "shot" not in sm.samples_of(conn, ids["DSC_0001"])
    assert list(conn.execute("SELECT * FROM labels ORDER BY asset_id, grp, value")) == working
    assert not w.undo.can_undo()
    w.sample_button.setChecked(False)
    qtbot.keyClick(w.grid, Qt.Key.Key_C, ALT)
    assert [x[:2] for x in lb.labels_of(conn, ids["DSC_0001"])["shot"]] == [("can", "confirmed")]


def test_typing_in_the_search_box_never_changes_a_photo(qtbot, home) -> None:  # noqa: ANN001
    w = _open(qtbot, home, "Gõ chữ")
    _import(qtbot, w, home.shoot)
    ids = _ids(w)
    conn = w.project.conn
    _select(w, [ids["DSC_0000"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    qtbot.keyClick(w.grid, Qt.Key.Key_3)
    w.search.setFocus()
    qtbot.waitUntil(w.search.hasFocus, timeout=5000)
    qtbot.keyClicks(w.search, "x5u")
    qtbot.keyClick(w.search, Qt.Key.Key_Backspace)
    assert w.search.text() == "x5"
    d = decisions.get(conn, ids["DSC_0000"])
    assert (d.flag, d.rating) == ("keep", 3)


def test_keys_and_operations_follow_3_0_0(qtbot, home) -> None:  # noqa: ANN001
    w = _import_and_analyse(qtbot, home, "3.0.0")
    ids = _ids(w)
    conn = w.project.conn
    _select(w, [ids["DSC_0001"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    qtbot.keyClick(w.grid, Qt.Key.Key_4)
    assert (decisions.get(conn, ids["DSC_0001"]).flag, decisions.get(conn, ids["DSC_0001"]).rating) == ("keep", 4)
    qtbot.keyClick(w.grid, Qt.Key.Key_U)  # 3.0.0: Bỏ chọn
    assert decisions.get(conn, ids["DSC_0001"]).flag is None
    qtbot.keyClick(w.grid, Qt.Key.Key_W)  # 3.0.0 W (soft) = Out nét
    assert ("out_net", "confirmed", None) in lb.labels_of(conn, ids["DSC_0001"])["focus"]
    qtbot.keyClick(w.grid, Qt.Key.Key_Q)  # 3.0.0 Q (sharp) = no focus warning
    assert [x for x in lb.labels_of(conn, ids["DSC_0001"]).get("focus", []) if x[0] != "?"] == []
    w.grid.tick_clicked.emit(ids["DSC_0002"], False)  # the card's tick box
    assert decisions.get(conn, ids["DSC_0002"]).flag == "keep"
    w.filters.setCurrentRow(next(i for i in range(w.filters.count()) if "Giữ" in w.filters.item(i).text()))
    assert _names(w) == ["DSC_0002.jpg"]  # the 3.0.0 sidebar filter works on the event
    w.filters.setCurrentRow(0)
    _select(w, [ids["DSC_0000"], ids["DSC_0003"]])
    qtbot.keyClick(w.grid, Qt.Key.Key_C)  # Compare, as 3.0.0
    assert w.in_compare() and len(w.compare.records()) == 2
    qtbot.keyClick(w.grid, Qt.Key.Key_Escape)
    assert not w.in_compare()
    w.search.setText("0004")
    qtbot.waitUntil(lambda: _names(w) == ["DSC_0004.jpg"], timeout=3000)


def test_client_list_works_in_an_event_as_in_3_0_0(qtbot, home, tmp_path: Path) -> None:  # noqa: ANN001
    """REG-1: 📋 Khách chọn (Ctrl+L) is not hidden in Media: paste the client's list, the photos are listed and
    selected, the export dialog offers the list; the photographer's own P/X are untouched."""
    w = _open(qtbot, home, "Khách chọn")
    _import(qtbot, w, home.shoot)
    assert w.act_client_list.isVisible() and w.client_list_button.isVisible()
    dialog = w.open_client_list_dialog()
    dialog.text.setPlainText("0001, 0003")
    dialog.name.setText("Khách sự kiện")
    dialog.refresh()
    dialog.create()
    assert dialog.collection_id is not None
    assert sorted(_names(w)) == ["DSC_0001.jpg", "DSC_0003.jpg"] and len(w.selected_records()) == 2
    assert all(r.flag is None for r in w.model.records())
    export = w.open_export_dialog()  # the list being viewed is preselected, as in 3.0.0
    qtbot.addWidget(export)
    assert export.which_box.currentText().startswith("Danh sách khách: Khách sự kiện (2)")
    export.dest.setText(str(tmp_path / "Giao khách"))
    plan = export.preview()
    assert plan is not None and len(plan.photos) == 2


def _content(conn, asset_id: int) -> list[str]:  # noqa: ANN001
    return sorted(v for v, state, _ in lb.labels_of(conn, asset_id).get("content", []) if state != "removed")


def test_regression_real_operations_on_an_event(qtbot, home, tmp_path: Path) -> None:  # noqa: ANN001
    """REG-2 (1): compare 2, 3, 4 photos; Xoay xem (display only, file untouched); export by client list; one Ctrl+Z
    history over P, stars, rotation-free Media labels and moment edits."""
    before = hashes(home.shoot)
    w = _import_and_analyse(qtbot, home, "Hồi quy")
    ids = _ids(w)
    conn = w.project.conn
    order = [ids[f"DSC_000{i}"] for i in range(5)]
    for n in (2, 3, 4):
        _select(w, order[:n])
        qtbot.keyClick(w.grid, Qt.Key.Key_C)
        assert w.in_compare() and len(w.compare.records()) == n
        qtbot.keyClick(w.grid, Qt.Key.Key_Escape)
        assert not w.in_compare()
    # Xoay xem: the marked photos turn on screen; the files never change
    _select(w, order[:2])
    w.rotate_view()
    assert [r.rotation for r in w.model.records() if r.id in order[:2]] == [1, 1]  # quarter turns
    # one Ctrl+Z history: P, 3 sao, Alt+U Trung, Alt+1 Sân khấu, ✂ split — undone newest first
    _select(w, [order[4]])
    shots_before = lb.labels_of(conn, order[4]).get("shot")
    moments_before = conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0]
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    qtbot.keyClick(w.grid, Qt.Key.Key_3)
    qtbot.keyClick(w.grid, Qt.Key.Key_U, ALT)
    qtbot.keyClick(w.grid, Qt.Key.Key_1, ALT)
    w.split_here()
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == moments_before + 1
    for _ in range(5):
        qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == moments_before
    assert _content(conn, order[4]) == []
    assert lb.labels_of(conn, order[4]).get("shot") == shots_before
    d = decisions.get(conn, order[4])
    assert d.flag is None and not d.rating
    # Khách chọn → xuất theo danh sách, real copy
    dialog = w.open_client_list_dialog()
    dialog.text.setPlainText("0002 0004")
    dialog.name.setText("Khách")
    dialog.refresh()
    dialog.create()
    export = w.open_export_dialog()
    qtbot.addWidget(export)
    export.dest.setText(str(tmp_path / "Giao"))
    assert export.preview() is not None
    export.start_copy()
    qtbot.waitUntil(lambda: export.thread is None, timeout=30000)
    copied = sorted(p.name for p in (tmp_path / "Giao").rglob("*.jpg"))
    assert copied == ["DSC_0002.jpg", "DSC_0004.jpg"]
    assert hashes(home.shoot) == before  # originals untouched (rotation was display only)


def test_star_keys_and_content_keys_never_mix(qtbot, home) -> None:  # noqa: ANN001
    """REG-2 (1): 0–5 = sao (3.0.0), Alt+1–5 = nội dung (Media). In the grid and the large view each key does only its
    own job; while typing (search box, client list) neither changes a photo."""
    w = _open(qtbot, home, "Phím")
    _import(qtbot, w, home.shoot)
    ids = _ids(w)
    conn = w.project.conn
    a = ids["DSC_0001"]
    _select(w, [a])
    qtbot.keyClick(w.grid, Qt.Key.Key_2)
    assert decisions.get(conn, a).rating == 2 and _content(conn, a) == []
    qtbot.keyClick(w.grid, Qt.Key.Key_2, ALT)  # Booth / Gian hàng
    assert decisions.get(conn, a).rating == 2 and _content(conn, a) == [lb.CONTENT_KEYS["2"]]
    qtbot.keyClick(w.grid, Qt.Key.Key_0)  # 0 = xoá sao, content stays
    assert not decisions.get(conn, a).rating and _content(conn, a) == [lb.CONTENT_KEYS["2"]]
    qtbot.keyClick(w.grid, Qt.Key.Key_Return)  # large view: same keys
    assert w.center.currentIndex() == 2
    qtbot.keyClick(w.viewer, Qt.Key.Key_5)
    qtbot.keyClick(w.viewer, Qt.Key.Key_4, ALT)  # Sản phẩm
    assert decisions.get(conn, a).rating == 5
    assert _content(conn, a) == sorted([lb.CONTENT_KEYS["2"], lb.CONTENT_KEYS["4"]])
    qtbot.keyClick(w.viewer, Qt.Key.Key_Escape)
    # typing in the search box: digits and Alt+digits change nothing
    w.search.setFocus()
    qtbot.keyClicks(w.search, "0001")
    qtbot.keyClick(w.search, Qt.Key.Key_3, ALT)
    qtbot.keyClick(w.search, Qt.Key.Key_1)
    assert decisions.get(conn, a).rating == 5
    assert _content(conn, a) == sorted([lb.CONTENT_KEYS["2"], lb.CONTENT_KEYS["4"]])
    assert w.search.text() == "00011"
    w.search.clear()
    # typing in the client list dialog
    dialog = w.open_client_list_dialog()
    dialog.text.setFocus()
    qtbot.keyClicks(dialog.text, "0001 3")
    qtbot.keyClick(dialog.text, Qt.Key.Key_1, ALT)
    dialog.reject()
    assert decisions.get(conn, a).rating == 5
    assert _content(conn, a) == sorted([lb.CONTENT_KEYS["2"], lb.CONTENT_KEYS["4"]])
    # B and Alt+0 only act in 🏷 sample mode; outside it they change nothing
    _select(w, [a])
    w.grid.setFocus()
    qtbot.keyClick(w.grid, Qt.Key.Key_B)
    qtbot.keyClick(w.grid, Qt.Key.Key_0, ALT)
    assert conn.execute("SELECT COUNT(*) FROM sample_labels").fetchone()[0] == 0


def test_near_duplicate_experiment_is_off_by_default_and_counts_actions(qtbot, home, tmp_path: Path,
                                                                        caplog) -> None:  # noqa: ANN001
    """REG-2 (3): 🧪 off by default (the window is as before); on: groups, 'chỉ ảnh gợi ý', open / fix a group, the
    '⚠ chưa có ảnh P' moments; every action is one local log line read back by --media-counts (numbers only)."""
    import logging

    from app.media import similar as sim
    from app.media import trial

    caplog.set_level(logging.INFO, logger="app.media.trial")
    w = _import_and_analyse(qtbot, home, "Thử nghiệm")
    assert not w.act_near_dup.isChecked() and not w.group_filter.isVisible() and w.grouping is None
    n_all = w.model.rowCount()
    w.act_near_dup.setChecked(True)
    qtbot.waitUntil(lambda: w.grouping is not None, timeout=10000)
    assert w.group_filter.isVisible() and sim.is_on(w.project.conn)
    assert any("chưa có ảnh P" in w.moment_list.item(i).text() for i in range(w.moment_list.count()))
    w.group_filter.setCurrentIndex(w.group_filter.findData("reps"))
    assert w.model.rowCount() == len(w.grouping.representatives()) <= n_all
    first = w.model.records()[0].id
    w.open_group(first)
    assert {r.id for r in w.model.records()} == set(w.grouping.group(first).members)
    w.close_group()
    w.group_fix(first, "break")
    assert sim.fixes(w.project.conn) == {first: "break"}
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # group fixes are in Ctrl+Z too
    assert sim.fixes(w.project.conn) == {}
    w.group_fix(first, "break")
    _select(w, [first])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    lines = [r.getMessage() for r in caplog.records if r.name == "app.media.trial"]
    eid = w.media_event.event_id
    assert f"media action: event={eid} kind=experiment_on n=1" in lines
    assert any(x.startswith(f"media action: event={eid} kind=keep n=1") for x in lines)
    assert all("DSC_" not in x and str(home.shoot) not in x for x in lines)  # no photo names or paths
    log_file = tmp_path / "kirapick.log"
    log_file.write_text("\n".join(f"2026-11-08 10:00:{i:02d},000 INFO app.media.trial: {x}" for i, x in enumerate(lines)),
                        encoding="utf-8")
    result = trial.counts(w.media_event.folder, [log_file])
    assert result["experiment_on"] and result["P"] == 1 and result["actions_by_kind"]["keep"] == 1
    assert result["groups"]["fixes_break"] == 1 and result["groups"]["groups"] == len(w.grouping.groups)
    assert result["actions_by_kind"]["group_break"] == 2 and result["actions_by_kind"]["undo"] == 1
    assert result["moments_without_P"] == result["moments"] - 1
    # off again: everything as before
    w.act_near_dup.setChecked(False)
    assert w.grouping is None and w.model.rowCount() == n_all and not w.group_filter.isVisible()


def test_media_flow_as_3_0_0_mark_compare_rotate_undo_export(qtbot, home, tmp_path: Path) -> None:  # noqa: ANN001
    """REG-3 (4): the 3.0.0 culling flow in an event: P / X / stars / ❤, compare, Xoay xem, Ctrl+Z, export copies of
    P photos; ✂ split and Gộp of moments are both undone by Ctrl+Z (one Media history with the P/X marks)."""
    before = hashes(home.shoot)
    w = _import_and_analyse(qtbot, home, "Luồng 3.0.0")
    ids = _ids(w)
    conn = w.project.conn
    a, b, c = ids["DSC_0000"], ids["DSC_0001"], ids["DSC_0004"]
    _select(w, [a])
    qtbot.keyClick(w.grid, Qt.Key.Key_P)
    qtbot.keyClick(w.grid, Qt.Key.Key_5)
    qtbot.keyClick(w.grid, Qt.Key.Key_F)
    _select(w, [b])
    qtbot.keyClick(w.grid, Qt.Key.Key_X)
    da, db = decisions.get(conn, a), decisions.get(conn, b)
    assert (da.flag, da.rating, bool(da.favorite), db.flag) == ("keep", 5, True, "reject")
    _select(w, [a, b])
    qtbot.keyClick(w.grid, Qt.Key.Key_C)
    assert w.in_compare() and len(w.compare.records()) == 2
    qtbot.keyClick(w.grid, Qt.Key.Key_Escape)
    w.rotate_view()
    # moments: ✂ split, then Gộp back, each undone by Ctrl+Z
    n = conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0]
    _select(w, [c])
    w.split_here()
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == n + 1
    _select(w, [c])
    w.merge_with_previous()
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == n
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # undo Gộp
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == n + 1
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # undo ✂
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == n
    qtbot.keyClick(w.grid, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)  # then the X, as one history
    assert decisions.get(conn, b).flag is None
    # export copies of the P photos (by moment), into a separate folder
    export = w.open_export_dialog()
    qtbot.addWidget(export)
    assert export.which_box.currentData() is None  # Ảnh đã chọn (P)
    export.dest.setText(str(tmp_path / "Xuat"))
    assert export.preview() is not None
    export.start_copy()
    qtbot.waitUntil(lambda: export.thread is None, timeout=30000)
    assert sorted(p.name for p in (tmp_path / "Xuat").rglob("*.jpg")) == ["DSC_0000.jpg"]
    assert hashes(home.shoot) == before  # originals never changed (rotation is display only)
