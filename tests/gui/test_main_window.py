"""GUI tests (pytest-qt, offscreen). They drive the real window with key presses."""

from __future__ import annotations

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
    monkeypatch.setattr(mw, "default_projects_dir", lambda: tmp_path / "projects")
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
    w = mw.MainWindow(settings=QSettings(env["ini"], QSettings.Format.IniFormat))
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
    assert w.project is not None and w.project.folder.parent.name == "projects"
    errors = [r for r in w.model.records() if r.status == "error"]
    assert [r.name for r in errors] == ["hong.jpg"]


def test_keyboard_culling_persists_and_survives_restart(qtbot, env: dict) -> None:
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

    w2 = _window(qtbot, env)  # reopens the last project automatically
    assert w2.project is not None and w2.model.rowCount() == 7
    rec = w2.model.record(w2.model.index_of(first.id))
    assert (rec.flag, rec.rating, rec.favorite) == ("keep", 4, True)


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
    assert len(list(dest.glob("snorlu_export_*.csv"))) == 1


def test_window_fits_the_screen_and_remembers_its_size(qtbot, env: dict) -> None:
    w = _window(qtbot, env)
    area = w.screen().availableGeometry()
    assert w.geometry().height() <= area.height() and w.geometry().width() <= area.width()
    # Must shrink to a 1920x1080 laptop at 150% scaling minus the taskbar (~1280x690 logical).
    hint = w.minimumSizeHint()
    assert hint.width() <= 1280 and hint.height() <= 690
    w.showNormal()
    w.resize(1000, 600)
    w.close()
    w2 = _window(qtbot, env)
    assert (w2.width(), w2.height()) == (1000, 600)
