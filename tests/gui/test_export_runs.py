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


def test_format_choice_is_remembered(qtbot, env: dict) -> None:  # noqa: F811
    from app.export.formats import ExportFormat

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    assert dialog.format_buttons[ExportFormat.RAW_JPEG].isChecked()  # default RAW + JPEG
    assert not hasattr(dialog, "include_pairs") and not hasattr(dialog, "keep_folders")  # old boxes gone (Q1)
    dialog.format_buttons[ExportFormat.RAW].setChecked(True)
    dialog.close()
    assert w.settings.value("export/format") == "raw"
    again = w.open_export_dialog()
    qtbot.addWidget(again)
    assert again.format_buttons[ExportFormat.RAW].isChecked() and again.export_format is ExportFormat.RAW


def test_old_include_pairs_setting_migrates_to_raw_jpeg(tmp_path) -> None:  # noqa: ANN001
    """CR-P3-D03: true or false → RAW + JPEG; false is a behaviour change, flagged for a one-time notice."""
    from PySide6.QtCore import QSettings

    from app.export.formats import ExportFormat
    from app.ui.export_dialog import MIGRATION_NOTICE_KEY, export_format

    for old, notice in ((True, False), (False, True)):
        s = QSettings(str(tmp_path / f"s{old}.ini"), QSettings.Format.IniFormat)
        s.setValue("export/include_pairs", old)
        assert export_format(s) is ExportFormat.RAW_JPEG
        assert not s.contains("export/include_pairs")
        assert s.value(MIGRATION_NOTICE_KEY, False, bool) is notice
        s.setValue("export/format", "jpeg")
        assert export_format(s) is ExportFormat.JPEG  # migrated once, later choices kept
