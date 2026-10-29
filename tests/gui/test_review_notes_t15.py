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
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


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
