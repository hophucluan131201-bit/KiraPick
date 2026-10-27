"""GUI tests (pytest-qt, offscreen). They drive the real window with key presses."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, Qt, QTimer

from app.storage import decisions
from app.ui import main_window as mw
from app.ui.asset_model import Filter
from tests.integration.test_import_job import _photo

pytestmark = pytest.mark.gui


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    photos = tmp_path / "Ảnh buổi chụp"
    for i in range(6):
        _photo(photos / f"DSC_{i:04d}.jpg", i, orientation=6 if i == 2 else None,
               taken=f"2026:10:25 16:00:{i:02d}")
    (photos / "hong.jpg").write_bytes(b"broken" * 100)
    return {"photos": photos, "ini": str(tmp_path / "settings.ini")}


def _window(qtbot, env: dict) -> mw.MainWindow:
    from app.ui.theme import apply_dark_theme
    from PySide6.QtWidgets import QApplication

    apply_dark_theme(QApplication.instance())
    settings = QSettings(env["ini"], QSettings.Format.IniFormat)
    w = mw.MainWindow(settings=settings)
    qtbot.addWidget(w)
    w.show()
    return w


def _import(qtbot, w: mw.MainWindow, root: Path) -> None:
    w.start_import(root)
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=30000)


def _key(qtbot, w: mw.MainWindow, key: Qt.Key) -> None:
    qtbot.keyClick(w, key)


def test_empty_state_then_import_without_freezing(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    assert w.center.currentIndex() == 0  # "Nhập thư mục ảnh" hint
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start(10)
    _import(qtbot, w, env["photos"])
    timer.stop()
    assert len(ticks) >= 3, "UI event loop must keep running during import"
    assert w.model.rowCount() == 7 and w.center.currentIndex() == 1
    assert "Nhập xong" in w.status.text() and "1 lỗi" in w.status.text()
    assert w.project is not None and w.project.folder.parent.name == "sessions"
    errors = [r for r in w.model.records() if r.status == "error"]
    assert [r.name for r in errors] == ["hong.jpg"]


def test_keyboard_culling_and_new_session_on_restart(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    first = w.current_record()
    _key(qtbot, w, Qt.Key.Key_K)
    _key(qtbot, w, Qt.Key.Key_4)
    _key(qtbot, w, Qt.Key.Key_F)
    _key(qtbot, w, Qt.Key.Key_Right)
    second = w.current_record()
    _key(qtbot, w, Qt.Key.Key_X)
    assert first is not None and second is not None and first.id != second.id
    assert decisions.get(w.project.conn, first.id) == decisions.Decision("keep", 4, True)
    assert decisions.get(w.project.conn, second.id).flag == "reject"
    _key(qtbot, w, Qt.Key.Key_U)
    _key(qtbot, w, Qt.Key.Key_0)
    assert decisions.get(w.project.conn, second.id) == decisions.Decision()
    assert "Giữ 1" in w.counts.text()
    w.close()

    w2 = _window(qtbot, env)  # every start is an empty session ...
    assert w2.project is None and w2.model.rowCount() == 0 and w2.center.currentIndex() == 0
    _import(qtbot, w2, env["photos"])  # ... and re-importing the same folder remembers the work
    rec = w2.model.record(w2.model.index_of(first.id))
    assert (rec.flag, rec.rating, rec.favorite) == ("keep", 4, True)
    assert "Đã nhớ từ lần trước: 1 Giữ" in w2.status.text()


def test_reset_forgets_folder_and_switching_folders(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    other = tmp_path / "Buổi khác"
    _photo(other / "IMG_0001.jpg", 77)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    _key(qtbot, w, Qt.Key.Key_K)
    _import(qtbot, w, other)  # switching folder = switching session
    assert [r.name for r in w.model.records()] == ["IMG_0001.jpg"] and "Giữ 0" in w.counts.text()
    _import(qtbot, w, env["photos"])
    assert "Giữ 1" in w.counts.text()

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w.reset_current_folder()
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=30000)
    assert w.model.rowCount() == 7 and "Giữ 0" in w.counts.text()
    assert "Đã nhớ" not in w.status.text()
    assert sorted(p.name for p in env["photos"].iterdir())[:2] == ["DSC_0000.jpg", "DSC_0001.jpg"]  # photos untouched


def test_multi_select_and_filters(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    sel = w.grid.selectionModel()
    sel.clearSelection()  # import auto-selects the first photo
    for row in (1, 2, 3):
        sel.select(w.model.index(row), sel.SelectionFlag.Select)
    _key(qtbot, w, Qt.Key.Key_K)
    w.filters.setCurrentRow([f for f, _ in mw._FILTERS].index(Filter.KEEP))
    assert w.model.rowCount() == 3
    w.filters.setCurrentRow([f for f, _ in mw._FILTERS].index(Filter.ERRORS))
    assert [r.name for r in w.model.records()] == ["hong.jpg"]
    w.filters.setCurrentRow(0)
    assert w.model.rowCount() == 7


def test_loupe_preview_and_true_100_percent_zoom(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(2)  # the EXIF-rotated one
    _key(qtbot, w, Qt.Key.Key_Space)
    assert w.center.currentIndex() == 2
    qtbot.waitUntil(lambda: "Xem trước" in w.status.text(), timeout=10000)
    assert w.viewer.pixmap_size() == (600, 900)  # portrait, oriented
    _key(qtbot, w, Qt.Key.Key_Z)
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=10000)
    assert w.viewer.zoom_100 and w.viewer.transform().m11() == pytest.approx(1 / w.viewer.devicePixelRatioF())
    _key(qtbot, w, Qt.Key.Key_Right)  # stays at 100% on the next photo
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=10000)
    assert w.viewer.pixmap_size() == (900, 600)
    _key(qtbot, w, Qt.Key.Key_Escape)
    assert w.center.currentIndex() == 1


def test_zoom_closer_than_100_percent_and_jump_to_eyes(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    ratio = w.viewer.devicePixelRatioF()
    _key(qtbot, w, Qt.Key.Key_Plus)  # from the grid: opens the loupe at 100%, loads the real pixels
    assert w.center.currentIndex() == 2 and w.viewer.zoom == 1.0
    qtbot.waitUntil(w.viewer.is_full_resolution_shown, timeout=10000)
    _key(qtbot, w, Qt.Key.Key_Plus)
    _key(qtbot, w, Qt.Key.Key_Plus)
    assert w.viewer.zoom == 4.0 and w.viewer.transform().m11() == pytest.approx(4.0 / ratio)
    assert "Zoom 400%" in w.status.text() and "ảnh gốc" in w.status.text()
    for _ in range(5):
        _key(qtbot, w, Qt.Key.Key_Plus)
    assert w.viewer.zoom == 8.0  # capped
    _key(qtbot, w, Qt.Key.Key_Minus)
    assert w.viewer.zoom == 4.0
    for _ in range(4):
        _key(qtbot, w, Qt.Key.Key_Minus)
    assert w.viewer.zoom is None  # back to fit

    rec = w.current_record()
    with w.project.transaction() as conn:
        conn.execute("""INSERT INTO occurrences (asset_id, person_box, face_box, prominence, is_main, analysis_version,
                        created_at) VALUES (?, '[0.1,0.1,0.5,0.8]', '[0.6,0.2,0.1,0.15]', 1, 1, 1, 'n')""", (rec.id,))
    _key(qtbot, w, Qt.Key.Key_E)
    assert w.viewer.zoom == 2.0  # small face: 200%
    centre = w.viewer.mapToScene(w.viewer.viewport().rect().center())
    width, height = w.viewer.pixmap_size()
    assert abs(centre.x() / width - 0.65) < 0.05 and abs(centre.y() / height - 0.263) < 0.05


def test_broken_photo_in_loupe_shows_message_not_crash(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.filters.setCurrentRow([f for f, _ in mw._FILTERS].index(Filter.ERRORS))
    _key(qtbot, w, Qt.Key.Key_Space)
    qtbot.waitUntil(lambda: "Không đọc được" in w.status.text(), timeout=10000)
    assert w.inspector.error.text().startswith("Lỗi:")


def test_pause_and_resume_import(qtbot, env: dict, tmp_path: Path) -> None:
    many = tmp_path / "many"
    for i in range(40):
        _photo(many / f"IMG_{i:03d}.jpg", 1000 + i, size=(1600, 1200))
    w = _window(qtbot, env)
    thread = w.start_import(many)
    assert thread is not None
    qtbot.waitUntil(lambda: "Đang tạo ảnh xem trước" in w.status.text(), timeout=20000)
    w.pause_button.click()
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)
    assert w.pause_button.isVisible() and w.pause_button.text() == "Tiếp tục"
    done_first = w.project.conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'ok'").fetchone()[0]
    assert done_first < 40
    w.pause_button.click()
    qtbot.waitUntil(lambda: w.import_thread is None and "Nhập xong" in w.status.text(), timeout=30000)
    assert w.project.conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'ok'").fetchone()[0] == 40
    assert not w.pause_button.isVisible()


def test_export_dialog_previews_then_copies(qtbot, env: dict, tmp_path: Path) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    for row in (0, 1):
        w.select_row(row)
        _key(qtbot, w, Qt.Key.Key_K)
    dialog = w.open_export_dialog()
    assert dialog is not None
    qtbot.addWidget(dialog)
    assert not dialog.copy_button.isEnabled()  # no destination yet
    dest = tmp_path / "Ảnh chọn"
    dialog.dest.setText(str(dest))
    dialog.refresh()
    assert dialog.table.rowCount() == 2 and dialog.copy_button.isEnabled()
    dialog.dest.setText(str(env["photos"]))  # the shoot folder itself is refused
    dialog.refresh()
    assert not dialog.copy_button.isEnabled() and "thư mục ảnh gốc" in dialog.summary.text()
    dialog.dest.setText(str(dest))
    dialog.refresh()
    dialog.hide()  # skip the final message box in tests
    thread = dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    thread.wait()
    assert sorted(p.name for p in dest.glob("*.jpg")) == ["DSC_0000.jpg", "DSC_0001.jpg"]
    assert len(list((dest / "_snorlu_danh_sach").glob("snorlu_export_*.csv"))) == 1
    dialog.refresh()  # exporting again: nothing new to copy
    assert not dialog.copy_button.isEnabled() and "đã có ở thư mục này" in dialog.summary.text()


def test_window_fits_the_screen_and_remembers_its_size(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    # Must shrink to a 1920x1080 laptop at 150% scaling minus the taskbar (~1280x690 logical).
    hint = w.minimumSizeHint()
    assert hint.width() <= 1280 and hint.height() <= 690
    # Long texts (empty-state hint, status messages) must not raise the minimum width.
    w.status.setText("Nhập xong: 439 file, 439 mới, 12 cặp RAW+JPEG. Đã nhớ từ lần trước: 25 Giữ, 3 Loại, 10 có sao.")
    assert w.minimumSizeHint().width() == hint.width()
    area = w.screen().availableGeometry()
    if hint.width() <= area.width() and hint.height() <= area.height():
        # (The offscreen test screen is only 800x800; skip when fonts make that impossible.)
        assert w.geometry().height() <= area.height() and w.geometry().width() <= area.width()
    w.showNormal()
    w.resize(700, 500)  # smaller than the offscreen screen
    size = (w.width(), w.height())
    w.close()
    w2 = _window(qtbot, env)
    assert (w2.width(), w2.height()) == size


def test_search_by_file_name(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.activateWindow()
    qtbot.waitUntil(w.isActiveWindow, timeout=3000)
    qtbot.keyClick(w, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(w.search.hasFocus, timeout=3000)
    qtbot.keyClicks(w.search, "0003 0005")  # typing into the box must not trigger K/X/1-5 shortcuts
    qtbot.waitUntil(lambda: w.model.rowCount() == 2, timeout=3000)
    assert sorted(r.name for r in w.model.records()) == ["DSC_0003.jpg", "DSC_0005.jpg"]
    assert all(decisions.get(w.project.conn, r.id) == decisions.Decision() for r in w.model.records())
    w.search.clear()
    qtbot.waitUntil(lambda: w.model.rowCount() == 7, timeout=3000)


def test_client_list_creates_list_selects_and_exports(qtbot, env: dict, tmp_path: Path) -> None:
    from app.ui.client_list_dialog import ClientListDialog

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    dialog = w.open_client_list_dialog()
    assert isinstance(dialog, ClientListDialog)
    assert dialog.pattern.text() == "DSC_####"  # detected from the imported names
    dialog.text.setPlainText("Em chọn: 1-2 tấm nha, 0001, 0003-0004, DSC_0009.jpg")
    dialog.name.setText("Khách Aki")
    dialog.refresh()
    assert "Tìm thấy 3/4" in dialog.report.text() and "DSC_0009" in dialog.report.text()
    dialog.create()
    assert dialog.collection_id is not None
    assert w.model.rowCount() == 3 and len(w.selected_records()) == 3
    assert "Khách Aki (3)" in w.filters.currentItem().text()
    assert all(r.flag is None for r in w.model.records())  # photographer's own flags untouched

    export = w.open_export_dialog()
    qtbot.addWidget(export)
    assert export.radios[export._selection()].text() == "Danh sách khách:"
    export.dest.setText(str(tmp_path / "Giao khách"))
    export.refresh()
    assert export.table.rowCount() == 3


def test_closing_window_with_open_dialog_is_safe(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    dialog = w.open_client_list_dialog()
    dialog.text.setPlainText("0001")  # starts the debounce timer
    w.close()  # closes the dialog and then the database
    qtbot.wait(400)  # the timer would have fired here
    assert not dialog.isVisible()


def test_people_recognition_flow_on_real_photos(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:
    """Import -> automatic analysis -> people list -> filter -> rename -> merge -> remove photo."""
    import shutil

    from PySide6.QtWidgets import QMessageBox

    from app.identity import actions
    from tests.conftest import PHOTOS

    photos = sorted((PHOTOS / "user_nikon").glob("*.NEF"))
    if len(photos) < 3:
        pytest.skip("owner's sample NEFs absent")
    shoot = tmp_path / "Aki"
    shoot.mkdir()
    for f in photos:
        shutil.copy2(f, shoot / f.name)

    w = _window(qtbot, env)
    if not w.models_ready():
        pytest.skip("AI models not fetched")
    # Step by step: importing does not start the AI; each later step waits for the previous one.
    w.start_import(shoot)
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=60000)
    assert w.analyze_thread is None and "🧠 Nhận diện người" in w.status.text()
    assert w.act_analyze.isEnabled() and not w.act_quality.isEnabled() and not w.act_select.isEnabled()
    w.start_analysis("people")
    qtbot.waitUntil(lambda: w.analyze_thread is None and "Nhận diện xong" in w.status.text(), timeout=120000)
    assert not w.project.conn.execute("SELECT 1 FROM measurements").fetchone()  # no scoring yet
    assert w.act_quality.isEnabled() and not w.act_select.isEnabled()
    w.start_analysis("quality")
    qtbot.waitUntil(lambda: w.analyze_thread is None and "Phân tích xong" in w.status.text(), timeout=120000)
    assert w.act_select.isEnabled()
    subjects = actions.subjects_summary(w.project.conn)
    assert len(subjects) >= 3  # distinct cosplayers with clear faces
    kinds = [w.people.item(i).data(Qt.ItemDataRole.UserRole)[0] for i in range(w.people.count())]
    assert kinds.count("subject") == len(subjects) and "unidentified" in kinds  # DSC_0198: face hidden by hands

    # Quality: every main person measured on the full-resolution photo, a score shown with its parts.
    measured = w.project.conn.execute(
        "SELECT input_source, values_json FROM measurements WHERE extractor = 'quality'").fetchall()
    assert measured and all(r[0] == "embedded_jpeg" for r in measured)  # full-size camera JPEG, not the thumbnail
    assert any(json.loads(r[1])["eye_sharp"] for r in measured)
    w.people.setCurrentRow(0)  # filter the grid to the first person
    first = w.people.item(0).data(Qt.ItemDataRole.UserRole)[1]
    assert w.model.rowCount() == subjects[0]["photos"]
    assert w.inspector.fields["Chủ thể"].text().startswith(actions.subject_label(w.project.conn, first))
    explained = w.inspector.fields["Điểm chất lượng"].text()
    assert "/100" in explained and "Điểm mạnh" in explained and "Chưa đánh giá" in explained

    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("Aki", True))
    w.rename_current_person()
    assert w.people.item(0).text().startswith("Aki")

    w.people.item(0).setSelected(True)
    w.people.item(1).setSelected(True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w.merge_selected_people()
    merged = actions.subjects_summary(w.project.conn)
    assert len(merged) == len(subjects) - 1
    aki = next(r for r in merged if r["display_name"] == "Aki")
    assert aki["photos"] == subjects[0]["photos"] + subjects[1]["photos"]

    # Re-running the analysis/grouping keeps the user's merge and name.
    w.start_analysis("people")
    qtbot.waitUntil(lambda: w.analyze_thread is None, timeout=60000)
    again = {r["id"]: r for r in actions.subjects_summary(w.project.conn)}
    assert again[aki["id"]]["display_name"] == "Aki" and again[aki["id"]]["photos"] == aki["photos"]

    # Remove one photo from Aki; it must not come back after regrouping.
    asset = w.project.conn.execute("SELECT asset_id FROM occurrences WHERE subject_id = ? LIMIT 1",
                                   (aki["id"],)).fetchone()[0]
    with w.project.transaction() as conn:
        actions.remove_photos_from_subject(conn, aki["id"], [asset])
    w.start_analysis("people")
    qtbot.waitUntil(lambda: w.analyze_thread is None, timeout=60000)
    assert not w.project.conn.execute("SELECT 1 FROM occurrences WHERE subject_id = ? AND asset_id = ?",
                                      (aki["id"], asset)).fetchone()
    w.close()

    w2 = _window(qtbot, env)  # new session: re-import remembers people and names
    w2.start_import(shoot)
    qtbot.waitUntil(lambda: w2.import_thread is None and w2.analyze_thread is None, timeout=60000)
    assert any(r["display_name"] == "Aki" for r in actions.subjects_summary(w2.project.conn))


def test_tick_people_and_merge_from_toolbar(qtbot, env: dict, monkeypatch) -> None:
    """No models needed: people are written directly, as the grouping would."""
    from PySide6.QtWidgets import QMessageBox

    from app.identity import actions

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    conn = w.project.conn
    assets = [r[0] for r in conn.execute("SELECT id FROM assets WHERE status = 'ok' ORDER BY id")]
    with w.project.transaction():
        for sid, owned in ((1, assets[:3]), (2, assets[3:4]), (3, assets[4:5])):
            conn.execute("INSERT INTO subjects (id, created_at) VALUES (?, 'n')", (sid,))
            for a in owned:
                conn.execute("""INSERT INTO occurrences (asset_id, person_box, prominence, is_main, subject_id,
                                assignment, analysis_version, created_at) VALUES (?, '[0,0,1,1]', 1, 1, ?, 'auto', 1, 'n')""",
                             (a, sid))
        actions.rename_subject(conn, 3, "Aki")
    w._fill_people()
    assert not w.act_merge.isEnabled()
    assert w.teacher.store is not None and w.teacher.store.path.parent == mw.sessions_dir().parent / "learning"
    items = {w.people.item(i).data(Qt.ItemDataRole.UserRole)[1]: w.people.item(i) for i in range(w.people.count())}
    items[1].setCheckState(Qt.CheckState.Checked)
    assert not w.act_merge.isEnabled()  # one ticked person: nothing to merge
    items[3].setCheckState(Qt.CheckState.Checked)
    assert w.act_merge.isEnabled() and w.act_merge.text() == "🔗 Gộp 2 người"

    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.Yes)
    w.act_merge.trigger()
    assert "4 ảnh" in asked[0] and '"Aki"' in asked[0]
    summary = {r["id"]: r for r in actions.subjects_summary(conn)}
    assert set(summary) == {2, 3}  # the named person is kept, with all photos
    assert summary[3]["display_name"] == "Aki" and summary[3]["photos"] == 4
    assert all(w.people.item(i).checkState() == Qt.CheckState.Unchecked for i in range(w.people.count()))
    assert not w.act_merge.isEnabled()


def test_ai_selection_puts_picks_first_marks_keep_and_explains(qtbot, env: dict) -> None:
    import numpy as np

    from tests.unit.test_quality import add_scored

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    conn = w.project.conn
    ids = [r[0] for r in conn.execute("SELECT id FROM assets WHERE status = 'ok' ORDER BY capture_time")]
    a, b = np.eye(4, dtype=np.float32)[0], np.eye(4, dtype=np.float32)[1]
    with w.project.transaction():
        for asset, sharp, lay in zip(ids, (0.3, 0.7, 0.68, 0.6, 0.2, 0.5), (a, a, a, b, b, b)):
            add_scored(w.project, asset, 1, sharp, lay)
        decisions.set_flag(conn, ids[3], "reject")  # the user already rejected this one
    w.reload_preserving_view()
    w.open_select_dialog(accept=True)  # defaults: per person, N = 10 -> every scored photo, best/varied first
    order = [r.id for r in w.model.records()]
    assert order[:2] == [ids[1], ids[3]]  # best, then the best of the other pose (not the near copy ids[2])
    recs = {r.id: r for r in w.model.records()}
    assert recs[ids[1]].pick_rank == 1 and recs[ids[1]].flag == "keep"
    assert recs[ids[3]].flag == "reject"  # never overrides the user's own decision
    assert "AI đã chọn" in w.status.text()
    w.select_row(0)
    text = w.inspector.fields["Điểm chất lượng"].text()
    assert "/100" in text and "AI chọn" in text and "Chưa đánh giá" in text and "mắt nhắm/mở" in text
    before = w.teacher.store.culling_count()
    w.set_flag("reject")  # the user disagrees with the AI's first choice: a taste example
    assert w.teacher.store.culling_count() == before + 1
    w.set_sort(mw.Sort.TIME)
    assert [r.id for r in w.model.records() if r.status == "ok"] == ids


def test_per_person_selection_covers_everyone_even_from_a_person_view(qtbot, env: dict) -> None:
    import numpy as np

    from tests.unit.test_quality import add_scored

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    ids = [r[0] for r in w.project.conn.execute("SELECT id FROM assets WHERE status = 'ok' ORDER BY capture_time")]
    a, b = np.eye(4, dtype=np.float32)[0], np.eye(4, dtype=np.float32)[1]
    with w.project.transaction():
        for asset, person, lay in zip(ids, (1, 1, 1, 2, 2, 3), (a, b, a, a, b, a)):
            add_scored(w.project, asset, person, 0.6, lay)
    w._fill_people()
    w.people.setCurrentRow(0)  # looking at one person, like in the owner's screenshot
    assert w.model.current_filter is Filter.SUBJECT

    def per_person_two(d) -> None:  # noqa: ANN001
        d.per_person.setChecked(True)
        d.count.setValue(2)
        assert d.count_label.text() == "Số ảnh cho mỗi người:" and d.count.prefix() == ""

    w.open_select_dialog(accept=True, configure=per_person_two)
    chosen = {r[0]: r[1] for r in w.project.conn.execute("SELECT asset_id, subject_id FROM picks")}
    assert sorted(set(chosen.values())) == [1, 2, 3]  # every person got photos
    assert len(chosen) == 5  # 2 + 2 + 1 (person 3 has a single photo)
    assert w.model.current_filter is Filter.ALL  # the grid shows everyone's picks
    assert "cho 3 người" in w.status.text()
    first = [r.id for r in w.model.records()][:5]
    assert set(first) == set(chosen)


def test_ctrl_and_shift_click_select_several_in_grid_and_filmstrip(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])

    def click(view, row: int, modifier=Qt.KeyboardModifier.NoModifier) -> None:  # noqa: ANN001
        rect = view.visualRect(w.model.index(row))
        view.scrollTo(w.model.index(row))
        rect = view.visualRect(w.model.index(row))
        qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifier, rect.center())

    click(w.grid, 0)
    click(w.grid, 2, Qt.KeyboardModifier.ControlModifier)
    assert sorted(r.name for r in w.selected_records()) == ["DSC_0000.jpg", "DSC_0002.jpg"]
    _key(qtbot, w, Qt.Key.Key_K)
    assert [r.flag for r in w.model.records()][:3] == ["keep", None, "keep"]

    _key(qtbot, w, Qt.Key.Key_Space)  # loupe + filmstrip, like the owner's screen
    assert w.center.currentIndex() == 2
    click(w.filmstrip, 0)
    click(w.filmstrip, 2, Qt.KeyboardModifier.ShiftModifier)
    assert len(w.selected_records()) == 3
    _key(qtbot, w, Qt.Key.Key_U)  # clears all three ticks
    assert [r.flag for r in w.model.records()][:3] == [None, None, None]
    _key(qtbot, w, Qt.Key.Key_Right)  # moving on selects a single photo again
    assert len(w.selected_records()) == 1


def test_view_buttons_back_button_and_key_hints(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    assert w.act_grid_view.isChecked() and not w.act_loupe.isChecked()
    hints = lambda: w.key_hints.text().replace("&nbsp;", " ")  # noqa: E731
    assert w.key_hints.isVisible() and "chọn nhiều ảnh" in hints()
    w.act_loupe.trigger()
    assert w.center.currentIndex() == 2 and w.act_loupe.isChecked() and not w.act_grid_view.isChecked()
    assert "về lưới ảnh" in hints() and "phóng tới mắt" in hints()
    assert w.viewer.back_button.isVisible()
    qtbot.mouseClick(w.viewer.back_button, Qt.MouseButton.LeftButton)
    assert w.center.currentIndex() == 1 and w.act_grid_view.isChecked()
    w.act_help.setChecked(False)  # the cheat sheet can be hidden, and stays hidden next time
    assert not w.key_hints.isVisible()
    w.close()
    w2 = _window(qtbot, env)
    assert not w2.act_help.isChecked() and not w2.key_hints.isVisible()
