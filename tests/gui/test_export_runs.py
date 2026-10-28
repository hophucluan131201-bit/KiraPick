"""A finished export is recorded for the workflow step; the "Kèm JPEG" choice is remembered."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt

from app.storage import exports
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _export(qtbot, w, dest: Path):  # noqa: ANN001, ANN202
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(dest))
    dialog.refresh()
    dialog.hide()  # no final message box in tests
    thread = dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    thread.wait()
    return dialog


def test_export_dialog_records_a_run(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    before = {p.name: _sha(p) for p in env["photos"].glob("*.jpg")}
    for row in (0, 1):
        w.select_row(row)
        _key(qtbot, w, Qt.Key.Key_K)
    assert exports.count(w.project.conn) == 0
    _export(qtbot, w, tmp_path / "out")
    row = w.project.conn.execute("SELECT photos, files FROM export_runs").fetchone()
    assert tuple(row) == (2, 2)
    assert {p.name: _sha(p) for p in env["photos"].glob("*.jpg")} == before  # originals untouched
    _export(qtbot, w, tmp_path / "out")  # everything already there: nothing copied, no new run
    assert exports.count(w.project.conn) == 1


def test_include_pairs_choice_is_remembered(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    assert dialog.include_pairs.isChecked()  # default on
    dialog.include_pairs.setChecked(False)
    dialog.close()
    assert w.settings.value("export/include_pairs", True, bool) is False
    again = w.open_export_dialog()
    qtbot.addWidget(again)
    assert not again.include_pairs.isChecked()
