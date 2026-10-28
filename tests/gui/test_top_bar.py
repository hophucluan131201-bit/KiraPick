"""Top bar: the five workflow steps with ✓ / ◐ and the suggested next step; ⚙ menu; sidebar additions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from app.storage import decisions, exports
from app.ui.top_bar import STEP_LABELS
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


def _state(w, key: str) -> str:  # noqa: ANN001
    return w.top_bar.buttons[key].text()


def test_steps_show_done_partial_and_next(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.top_bar.next_step == "import"
    _import(qtbot, w, env["photos"])
    assert _state(w, "import").startswith("✓") and w.top_bar.next_step == "people"
    assert "lần nhập gần nhất" in w.top_bar.buttons["import"].toolTip()
    w.select_row(0)
    w.set_flag("keep")
    assert _state(w, "pick").startswith("✓")  # one Chọn completes "Chọn ảnh" (D5)
    assert list(STEP_LABELS) == ["import", "people", "quality", "pick", "export"]


def test_export_step_turns_done_when_run_recorded(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.set_flag("keep")
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(tmp_path / "out"))
    dialog.refresh()
    dialog.hide()
    assert not _state(w, "export").startswith("✓")
    thread = dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    thread.wait()
    assert exports.count(w.project.conn) == 1 and _state(w, "export").startswith("✓")


def test_steps_when_every_detection_failed(qtbot, env: dict) -> None:  # noqa: F811
    from app.workers import analyze_job

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    with w.project.transaction() as conn:
        conn.execute("""INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at)
                        SELECT id, 'detect', ?, 'failed', 3, 't' FROM assets WHERE status = 'ok'""",
                     (analyze_job.STAGE_VERSION,))
    w.refresh_steps()
    assert _state(w, "people").startswith("✓") and _state(w, "quality").startswith("✓")
    assert w.top_bar.next_step == "pick"  # nothing stuck at ◐


def test_steps_after_stage_version_change(qtbot, env: dict) -> None:  # noqa: F811
    from app.workers import analyze_job, embed_job

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    with w.project.transaction() as conn:
        for stage, version in (("detect", analyze_job.STAGE_VERSION - 1), ("embed", embed_job.STAGE_VERSION)):
            conn.execute("""INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at)
                            SELECT id, ?, ?, 'done', 1, 't' FROM assets WHERE status = 'ok'""", (stage, version))
    w.refresh_steps()
    assert _state(w, "people").startswith("◐") and w.top_bar.next_step == "people"


def test_step_buttons_run_the_same_actions(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    calls = []
    monkeypatch.setattr(w, "choose_and_import", lambda: calls.append("import"))
    w.act_import.triggered.disconnect()
    w.act_import.triggered.connect(w.choose_and_import)
    w.top_bar.buttons["import"].click()
    assert calls == ["import"]
    assert not w.top_bar.buttons["quality"].isEnabled()  # no session yet: same rule as before


def test_options_menu_has_moved_actions(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    texts = [a.text() for a in w.top_bar.options_button.menu().actions()]
    for wanted in ("↺ Làm lại", "🎓 AI đã học", "⌨ Phím tắt"):
        assert any(t.startswith(wanted) for t in texts), wanted
    assert w.act_gpu in w.top_bar.options_button.menu().actions()
    from PySide6.QtWidgets import QToolBar

    assert not w.findChildren(QToolBar)  # no old toolbar left
    assert w.top_bar.sizeHint().width() <= 1880  # the whole bar fits a 1080p screen at 100 %


def test_shortcuts_still_work_without_the_toolbar(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    opened = []
    monkeypatch.setattr(w, "open_export_dialog", lambda *a, **k: opened.append("export"))
    w.act_export.triggered.disconnect()
    w.act_export.triggered.connect(lambda: w.open_export_dialog())
    w.grid.setFocus()
    qtbot.keyClick(w, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
    assert opened == ["export"]


def test_people_filter_and_merge_button(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    with w.project.transaction() as conn:
        ids = [r[0] for r in conn.execute("SELECT id FROM assets WHERE status = 'ok' ORDER BY id")]
        for i, a in enumerate(ids[:3]):
            sid = conn.execute("INSERT INTO subjects (created_at) VALUES ('t')").lastrowid
            conn.execute("INSERT INTO occurrences (asset_id, prominence, is_main, analysis_version, created_at,"
                         " subject_id, assignment) VALUES (?, 1, 1, 1, 't', ?, 'auto')", (a, sid))
    w._fill_people()
    names = [w.people.item(i).text() for i in range(w.people.count())]
    w.people_filter.setText("2")
    visible = [w.people.item(i).text() for i in range(w.people.count()) if not w.people.item(i).isHidden()]
    assert visible and all("2" in t for t in visible) and len(visible) < len(names)
    w.people_filter.clear()
    assert all(not w.people.item(i).isHidden() for i in range(w.people.count()))
    assert w.merge_button.defaultAction() is w.act_merge and not w.act_merge.isEnabled()
    w.people.item(0).setCheckState(Qt.CheckState.Checked)
    w.people.item(1).setCheckState(Qt.CheckState.Checked)
    assert w.act_merge.isEnabled()


def test_client_list_entry_in_quick_filters(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.client_list_button.defaultAction() is w.act_client_list
    assert w.sections["filters"].isAncestorOf(w.client_list_button)
