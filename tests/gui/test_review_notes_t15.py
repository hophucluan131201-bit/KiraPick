"""Review notes carried into Task 15: sessions from a newer app or a full disk (RV2-05, RV14-04), the people action on
a real session (RV9-03), a real RAW+JPEG pair through export (RV2-04), HD cache removed with the session."""

from __future__ import annotations

import errno
import hashlib
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from app.storage import db
from app.storage.sessions import session_dir
from app.ui import main_window as mw
from tests.gui.test_main_window import _import, _photo, _window, env  # noqa: F401 - fixture


def _warnings(monkeypatch) -> list[str]:  # noqa: ANN001
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text, *a, **k: shown.append(text))
    return shown


def _session_db(env: dict) -> Path:  # noqa: F811
    folder = session_dir(env["photos"].parent / "sessions", env["photos"].resolve())
    return next(folder.glob("*.db"))


# ------------------------------------------------------------------ RV2-05 / RV14-04
def test_session_from_a_newer_app_is_explained_and_left_untouched(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.close()
    path = _session_db(env)
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
    conn.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    shown = _warnings(monkeypatch)
    w2 = _window(qtbot, env)
    assert w2.start_import(env["photos"]) is None
    assert w2.project is None and w2.import_thread is None
    assert len(shown) == 1 and "phiên bản KiraPick mới hơn" in shown[0]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_full_disk_while_opening_a_session_is_explained(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    real, fail = mw.open_session, [True]

    def full(*a, **k):  # noqa: ANN002, ANN003, ANN202
        if fail[0]:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(*a, **k)

    monkeypatch.setattr(mw, "open_session", full)
    shown = _warnings(monkeypatch)
    w = _window(qtbot, env)
    assert w.start_import(env["photos"]) is None
    assert w.project is None
    assert len(shown) == 1 and "đã đầy" in shown[0]
    fail[0] = False  # space freed: the same window opens the folder
    _import(qtbot, w, env["photos"])
    assert w.model.rowCount() > 0


# ------------------------------------------------------------------ RV9-03
_ASSET_TABLES = ("occurrences", "decisions", "picks", "collection_items", "view_rotation", "asset_vectors", "previews")


def _rows(conn, assets: list[int]) -> dict[str, list[tuple]]:  # noqa: ANN001
    marks = ",".join("?" * len(assets))
    out = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} WHERE asset_id IN ({marks}) ORDER BY rowid", assets)]
           for t in _ASSET_TABLES}
    out["subjects"] = [tuple(r) for r in conn.execute("SELECT * FROM subjects ORDER BY id")]
    return out


def _seed_people(w) -> list[int]:  # noqa: ANN001
    conn = w.project.conn
    assets = [r[0] for r in conn.execute("SELECT id FROM assets WHERE status = 'ok' ORDER BY id")]
    with w.project.transaction():
        for sid, owned in ((1, assets[:4]), (2, assets[4:5])):
            conn.execute("INSERT INTO subjects (id, created_at) VALUES (?, 'n')", (sid,))
            for a in owned:
                conn.execute("""INSERT INTO occurrences (asset_id, person_box, prominence, is_main, subject_id,
                                assignment, analysis_version, created_at) VALUES (?, '[0,0,1,1]', 1, 1, ?, 'auto', 1, 'n')""",
                             (a, sid))
    w._fill_people()
    return assets


def _pick(text: str):  # noqa: ANN202
    from PySide6.QtGui import QAction

    def run(menu, _pos):  # noqa: ANN001, ANN202
        return next(a for a in menu.findChildren(QAction) if a.text().startswith(text))
    return run


def test_panel_people_action_changes_only_the_current_photo(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """RV9-03 on a real session database: the Chủ thể tab's people menu acts on the photo shown in the panel only;
    every row of the marked photos (and the subjects table) is identical before and after."""
    from app.ui.asset_model import Filter

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    assets = _seed_people(w)
    w.model.set_filter(Filter.SUBJECT, subject_id=1)
    assert sorted(r.id for r in w.model.records()) == assets[:4]
    w.select_row(0)
    current = w.current_record().id
    for row in (1, 2):
        w.grid.selectionModel().select(w.model.index(row), w.grid.selectionModel().SelectionFlag.Select)
    marked = sorted(r.id for r in w.selected_records() if r.id != current)
    assert len(marked) == 2 and current not in marked
    conn = w.project.conn
    before = _rows(conn, marked)

    monkeypatch.setattr(w, "_run_menu", _pick("Không phải"))
    w.detail.people_menu_requested.emit(w.mapToGlobal(w.rect().center()))
    occ = conn.execute("SELECT subject_id, excluded_subject_id, assignment FROM occurrences WHERE asset_id = ?",
                       (current,)).fetchone()
    assert tuple(occ) == (None, 1, "manual")
    assert _rows(conn, marked) == before

    monkeypatch.setattr(w, "_run_menu", _pick("Chủ thể 2"))  # "Gán cho chủ thể…" → Chủ thể 2
    other = next(a for a in assets[:4] if a not in marked and a != current)
    w.model.set_filter(Filter.SUBJECT, subject_id=1)
    w.select_row([r.id for r in w.model.records()].index(other))
    for a in marked:
        w.grid.selectionModel().select(w.model.index([r.id for r in w.model.records()].index(a)),
                                       w.grid.selectionModel().SelectionFlag.Select)
    w.detail.people_menu_requested.emit(w.mapToGlobal(w.rect().center()))
    assert conn.execute("SELECT subject_id FROM occurrences WHERE asset_id = ?", (other,)).fetchone()[0] == 2
    assert _rows(conn, marked) == before


# ------------------------------------------------------------------ RV2-04
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_raw_jpeg_pair_import_keep_export(qtbot, env: dict, public_nef: Path, tmp_path: Path) -> None:  # noqa: F811
    """RV2-04 with a real NEF and its JPEG: one card in the grid, Chọn with P, the bar's size equals the export plan,
    the export copies both files byte for byte, and "Xoay xem" changes nothing in the files or the export."""
    import shutil

    from PySide6.QtCore import Qt

    from app.export.copy_export import Selection, plan_export, run_export, select_assets
    from app.export.formats import ExportFormat
    from app.storage.stats import counts
    from tests.integration.test_import_job import _photo

    shoot = tmp_path / "pair"
    shoot.mkdir()
    shutil.copy2(public_nef, shoot / "ISS.NEF")
    _photo(shoot / "ISS.JPG", 1, taken="2012:03:04 17:20:59")  # the NEF's capture time: a confirmed pair
    sources = {p.name: (_sha(p), p.stat().st_mtime_ns) for p in shoot.iterdir()}
    w = _window(qtbot, env)
    _import(qtbot, w, shoot)
    assert w.model.rowCount() == 1  # the pair is one photo
    w.select_row(0)
    qtbot.keyClick(w, Qt.Key.Key_P)
    assert w.current_record().flag == "keep"
    conn = w.project.conn
    w.rotate_view()
    assert conn.execute("SELECT count(*) FROM view_rotation").fetchone()[0] >= 1
    plan = plan_export(w.project, select_assets(w.project, Selection.KEEP), tmp_path / "out")
    assert sorted(i.dest_relative for i in plan.items) == ["ISS.JPG", "ISS.NEF"]
    assert counts(conn, ExportFormat.RAW_JPEG).keep_bytes == plan.total_bytes == sum((shoot / n).stat().st_size for n in sources)
    result = run_export(plan)
    assert sorted(result.copied) == ["ISS.JPG", "ISS.NEF"]
    for name, (digest, mtime) in sources.items():
        assert _sha(tmp_path / "out" / name) == digest  # byte-identical copies
        assert (_sha(shoot / name), (shoot / name).stat().st_mtime_ns) == (digest, mtime)  # sources untouched


# ------------------------------------------------------------------ HD cache lifetime (Task 13 approval note)
def test_hd_cache_and_backups_go_with_the_session(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """"↺ Làm lại" and the 30-day clean-up delete the session folder, its HD thumbnails and its pre-upgrade backup;
    the photos are untouched."""
    import time

    from app.storage.sessions import purge_old_sessions
    from app.ui import asset_model

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.model.set_device_pixel_ratio(2.0)
    w.set_grid_cell(340)
    for _ in range(3):
        w.grid.viewport().repaint()
        w.model.wait_for_thumbnails(30000)
    hd = w.project.cache_dir / asset_model.HD_DIR
    made = sorted(p.name for p in hd.glob("*.jpg"))
    assert made, "no HD thumbnails were made"
    (hd / "stale_from_before.jpg").write_bytes(b"x")
    photos = {p.name: _sha(p) for p in env["photos"].iterdir()}

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w.reset_current_folder()  # forgets the session, then imports again
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=30000)
    assert not (hd / "stale_from_before.jpg").exists()

    folder = w.project.folder
    (folder / "project.snorlu.db.v6.bak").write_bytes(b"backup")  # as an upgrade would leave it
    w.close()
    gone = purge_old_sessions(env["photos"].parent / "sessions", now=time.time() + 400 * 86400)
    assert folder in gone and not folder.exists()
    assert {p.name: _sha(p) for p in env["photos"].iterdir()} == photos


# ------------------------------------------------------------------ RV14-04: disk full, unsupported RAW
def test_full_disk_while_writing_an_hd_thumbnail_leaves_no_partial_file(tmp_path: Path, monkeypatch) -> None:
    """The HD file cannot be written (disk full): no half-written file is left taking space, and the card keeps its
    import thumbnail (the task still delivers an image)."""
    from PIL import Image

    from app.ui import asset_model
    from tests.integration.test_import_job import _photo

    source = _photo(tmp_path / "big.jpg", 3, size=(3000, 2000))
    thumb = _photo(tmp_path / "thumb.jpg", 3, size=(400, 266))
    hd_dir = tmp_path / "hd"

    def full(self, fp, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        Path(fp).write_bytes(b"\xff\xd8 half a file")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Image.Image, "save", full)
    assert asset_model.hd_thumbnail(source, hd_dir, 1) is None
    assert list(hd_dir.iterdir()) == []

    got = []

    class Signals:
        class loaded:  # noqa: N801
            @staticmethod
            def emit(*args) -> None:  # noqa: ANN002
                got.append(args)

    asset_model._ThumbTask(1, thumb, Signals, 680, 1, source, hd_dir).run()
    assert got and not got[0][1].isNull()  # the import thumbnail


def test_unsupported_and_broken_raw_files_are_reported_not_fatal(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    """Broken RAW files (a fake NEF; locally also stripped samples of rare formats) import without stopping the
    others, and large HD cards on a 200 % screen never fail on them."""
    import shutil

    from app.ui import asset_model

    shoot = tmp_path / "mixed"
    shutil.copytree(env["photos"], shoot)
    (shoot / "BROKEN.NEF").write_bytes(b"II*\x00" + b"\x00" * 4000)
    (shoot / "EMPTY.CR3").write_bytes(b"")
    stripped = Path(__file__).resolve().parents[2] / "test_photos" / "stripped"
    for p in sorted(stripped.iterdir()) if stripped.is_dir() else []:
        shutil.copy2(p, shoot / f"S_{p.name}")
    w = _window(qtbot, env)
    _import(qtbot, w, shoot)
    conn = w.project.conn
    status = dict(conn.execute("SELECT relative_path, status FROM assets"))
    assert status["BROKEN.NEF"] != "ok" and status.get("EMPTY.CR3", "skipped") != "ok"
    assert sum(1 for s in status.values() if s == "ok") >= 6  # the good photos all came in
    w.model.set_device_pixel_ratio(2.0)
    w.set_grid_cell(340)
    for _ in range(3):
        w.grid.viewport().repaint()
        assert w.model.wait_for_thumbnails(30000)
    hd = w.project.cache_dir / asset_model.HD_DIR
    assert not list(hd.glob("*.part"))
    print("\nstatus counts:", {s: list(status.values()).count(s) for s in set(status.values())})


# ------------------------------------------------------------------ RV14-04: closing / switching during an export
def test_close_during_export_asks_first_and_no_keeps_copying(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    """Closing stops a running export after its current file; the user is asked first. No: the window stays and the
    copy goes on. Yes: it stops after the current file and the window closes."""
    from tests.gui.test_shutdown_callbacks import _held_export

    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    gate, dialog = _held_export(qtbot, w, tmp_path / "out", monkeypatch)
    asked: list[str] = []
    answer = [QMessageBox.StandardButton.No]
    monkeypatch.setattr(QMessageBox, "question", lambda _p, _t, text, *a, **k: asked.append(text) or answer[0])

    assert w.close() is False and w.isVisible()
    assert len(asked) == 1 and "đang xuất ảnh" in asked[0].lower()
    thread = dialog.copy_thread
    assert thread.isRunning() and not thread._cancel.is_set()

    answer[0] = QMessageBox.StandardButton.Yes
    assert w.close() is False  # waits for the file being copied
    assert thread._cancel.is_set()
    gate.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=10000)


def test_switch_during_export_asks_first(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    from tests.gui.test_shutdown_callbacks import _held_export

    other = tmp_path / "Buổi khác"
    _photo(other / "IMG_0001.jpg", 91)
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    project = w.project
    gate, dialog = _held_export(qtbot, w, tmp_path / "out", monkeypatch)
    asked: list[str] = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda _p, _t, text, *a, **k: asked.append(text) or QMessageBox.StandardButton.No)
    assert w.start_import(other) is None and w.project is project
    assert len(asked) == 1 and dialog.copy_thread.isRunning() and not dialog.copy_thread._cancel.is_set()
    gate.set()
    qtbot.waitUntil(lambda: not dialog.copy_thread.isRunning(), timeout=10000)
