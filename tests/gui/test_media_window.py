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
    qtbot.keyClick(view.grid, Qt.Key.Key_T, Qt.KeyboardModifier.AltModifier)
    assert lb.labels_of(view.media_event.conn, ids["DSC_0004"])["shot"] == [("toan", "confirmed", None)]
    view.select([ids["DSC_0003"], ids["DSC_0004"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)
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
    qtbot.keyClick(view.grid, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)  # confirmed label
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
    qtbot.keyClick(view.grid, Qt.Key.Key_U, Qt.KeyboardModifier.AltModifier)
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


def test_export_dialog_previews_then_copies_p_photos(qtbot, home, tmp_path: Path) -> None:  # noqa: ANN001
    from app.media import export as mx
    from app.ui.media_export import MediaExportDialog

    before = hashes(home.shoot)
    home.create("Xuất")
    view = home.view
    view.start_import(home.shoot)
    qtbot.waitUntil(lambda: view.import_thread is None, timeout=30000)
    ids = _ids(view)
    view.select([ids["DSC_0000"], ids["DSC_0003"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_P)  # P before any analysis: no moment yet
    dialog = MediaExportDialog(view.media_event, view)
    qtbot.addWidget(dialog)
    out = tmp_path / "Giao khách"
    dialog.dest.setText(str(out))
    assert not dialog.copy_button.isEnabled()  # nothing is copied before the preview
    plan = dialog.preview()
    assert plan is not None and "2 ảnh P → 2 tệp" in dialog.summary.text() and mx.NO_MOMENT in dialog.summary.text()
    assert not out.exists() or not any(out.rglob("*.jpg"))
    dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.thread is None, timeout=30000)
    assert "Đã sao chép 2 tệp" in dialog.summary.text()
    assert sorted(p.name for p in (out / mx.NO_MOMENT).iterdir()) == ["DSC_0000.jpg", "DSC_0003.jpg"]
    assert hashes(home.shoot) == before


def test_sample_labelling_mode_writes_reference_answers_only(qtbot, home) -> None:  # noqa: ANN001
    from app.media import samples as sm

    home.create("Mẫu")
    view = _import_and_analyse(qtbot, home)
    ids = _ids(view)
    conn = view.media_event.conn
    working = list(conn.execute("SELECT * FROM labels ORDER BY asset_id, grp, value"))
    view.sample_button.setChecked(True)
    view.select([ids["DSC_0001"]])
    for key, mod in ((Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier), (Qt.Key.Key_W, None), (Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier), (Qt.Key.Key_B, None)):
        qtbot.keyClick(view.grid, key, mod) if mod else qtbot.keyClick(view.grid, key)
    assert sm.samples_of(conn, ids["DSC_0001"]) == {"boundary": ["start"], "content": ["decor"], "focus": ["out_net"],
                                                   "shot": ["can"]}
    assert "Mẫu: Cận, Out nét, Decor" in view.details.text()
    qtbot.keyClick(view.grid, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)  # the same key takes it away
    assert "shot" not in sm.samples_of(conn, ids["DSC_0001"])
    assert list(conn.execute("SELECT * FROM labels ORDER BY asset_id, grp, value")) == working
    assert not view.undo.can_undo()  # reference answers are not in Ctrl+Z
    view.sample_button.setChecked(False)
    qtbot.keyClick(view.grid, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)  # back to working labels
    assert lb.labels_of(conn, ids["DSC_0001"])["shot"] == [("can", "confirmed", None)]


def test_backspace_and_alt_digits_do_nothing_to_photos_while_typing(qtbot, home) -> None:  # noqa: ANN001
    """Review 2026-11-07: Backspace (bỏ P/X) in a text field edits the text, never a photo's P / X."""
    from PySide6.QtWidgets import QLineEdit

    home.create("Gõ chữ")
    view = home.view
    view.start_import(home.shoot)
    qtbot.waitUntil(lambda: view.import_thread is None, timeout=30000)
    ids = _ids(view)
    conn = view.media_event.conn
    view.select([ids["DSC_0000"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_P)
    qtbot.keyClick(view.grid, Qt.Key.Key_3)  # stars: 0-5 as in 3.0.0
    assert decisions.get(conn, ids["DSC_0000"]).flag == "keep" and decisions.get(conn, ids["DSC_0000"]).rating == 3
    field = QLineEdit(view)  # any text field inside the Media window (search, rename…)
    view.layout().addWidget(field)
    field.show()
    field.setFocus()
    qtbot.waitUntil(field.hasFocus, timeout=5000)
    qtbot.keyClicks(field, "Khai mac")  # ASCII: QTest cannot type composed Vietnamese letters
    qtbot.keyClick(field, Qt.Key.Key_Backspace)
    qtbot.keyClick(field, Qt.Key.Key_5)
    qtbot.keyClick(field, Qt.Key.Key_U)
    assert field.text() == "Khai ma5u"  # Backspace removed "c"; 5 and U were typed, not applied to the photo
    assert decisions.get(conn, ids["DSC_0000"]).flag == "keep"  # Backspace did not clear P
    assert decisions.get(conn, ids["DSC_0000"]).rating == 3  # 5 did not rate
    view.grid.setFocus()
    qtbot.keyClick(view.grid, Qt.Key.Key_Backspace)  # back on the grid: Backspace clears P
    assert decisions.get(conn, ids["DSC_0000"]).flag is None


def test_media_keys_and_operations_follow_3_0_0(qtbot, home) -> None:  # noqa: ANN001
    """Review 2026-11-07 (3.0.0 is the reference): U clears P/X, 0-5 rate, C compares 2-4 marked photos, the card's
    tick box is Chọn, Q/W/R are the focus keys, Ctrl+F searches; Media labels moved to Alt+T/U/C and Alt+1-5."""
    home.create("3.0.0")
    view = _import_and_analyse(qtbot, home)
    ids = _ids(view)
    conn = view.media_event.conn
    view.select([ids["DSC_0001"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_P)
    qtbot.keyClick(view.grid, Qt.Key.Key_4)
    assert decisions.get(conn, ids["DSC_0001"]).flag == "keep" and decisions.get(conn, ids["DSC_0001"]).rating == 4
    qtbot.keyClick(view.grid, Qt.Key.Key_U)
    assert decisions.get(conn, ids["DSC_0001"]).flag is None
    assert "shot" not in lb.labels_of(conn, ids["DSC_0001"]) or \
        lb.labels_of(conn, ids["DSC_0001"])["shot"][0][1] != "confirmed"  # U no longer means Trung
    qtbot.keyClick(view.grid, Qt.Key.Key_U, Qt.KeyboardModifier.AltModifier)
    assert lb.labels_of(conn, ids["DSC_0001"])["shot"] == [("trung", "confirmed", 0.95)]
    qtbot.keyClick(view.grid, Qt.Key.Key_W)
    assert ("out_net", "confirmed", None) in lb.labels_of(conn, ids["DSC_0001"])["focus"]
    qtbot.keyClick(view.grid, Qt.Key.Key_Q)  # sharp: warnings removed
    assert [x for x in lb.labels_of(conn, ids["DSC_0001"]).get("focus", []) if x[0] != "?"] == []
    # tick box on the card
    idx = view.model.index_of(ids["DSC_0002"])
    view.grid.tick_clicked.emit(ids["DSC_0002"], False)
    assert decisions.get(conn, ids["DSC_0002"]).flag == "keep"
    view.grid.tick_clicked.emit(ids["DSC_0002"], False)
    assert decisions.get(conn, ids["DSC_0002"]).flag is None and idx.isValid()
    # compare: C with 2 marked photos, P acts on the active tile, Esc back to the grid
    view.select([ids["DSC_0000"], ids["DSC_0003"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_C)
    assert view.in_compare() and len(view.compare.records()) == 2
    active = view.compare.active_id
    qtbot.keyClick(view.compare, Qt.Key.Key_X)
    assert decisions.get(conn, active).flag == "reject"
    qtbot.keyClick(view.compare, Qt.Key.Key_Escape)
    assert not view.in_compare()
    view.select([ids["DSC_0000"]])
    qtbot.keyClick(view.grid, Qt.Key.Key_C)
    assert not view.in_compare() and "2–4" in view.status.text()
    # search, as Chụp cá nhân
    view.search.setText("0004")
    assert _names(view) == ["DSC_0004.jpg"]
    view.search.clear()
    assert len(_names(view)) == 5
