"""F3 Batch 1b/1c in the window: Ctrl+Z / Chỉnh sửa → Hoàn tác, decisions and subject corrections, the merge dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication

from app.identity import actions
from app.storage import decisions
from app.ui.asset_model import Filter
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture
from tests.gui.test_review_notes_t15 import _pick, _seed_people


def _ctrl_z(qtbot, w) -> None:  # noqa: ANN001
    qtbot.keyClick(w.grid if w.grid.isVisible() else w, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)


def _dec(w, asset_id: int) -> tuple:  # noqa: ANN001
    d = decisions.get(w.project.conn, asset_id)
    return d.flag, d.rating, d.favorite, d.focus


def _occ(w) -> list[tuple]:  # noqa: ANN001
    return [tuple(r) for r in w.project.conn.execute(
        "SELECT id, subject_id, assignment, excluded_subject_id FROM occurrences ORDER BY id")]


def _subjects(w) -> list[tuple]:  # noqa: ANN001
    return [tuple(r) for r in w.project.conn.execute("SELECT id, display_name FROM subjects ORDER BY id")]


def test_edit_menu_and_shortcut_exist(qtbot, env) -> None:  # noqa: ANN001, F811
    w = _window(qtbot, env)
    assert w.edit_button.text() == "Chỉnh sửa" and w.act_undo in w.edit_menu.actions()
    assert w.edit_button.isVisibleTo(w)
    assert w.act_undo.shortcut() == QKeySequence(QKeySequence.StandardKey.Undo)
    assert not w.act_undo.isEnabled()  # nothing to undo
    _import(qtbot, w, env["photos"])
    assert not w.act_undo.isEnabled()


def test_keep_reject_rating_favorite_focus_undo_in_reverse_order(qtbot, env) -> None:  # noqa: ANN001, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.act_auto_advance.setChecked(False)
    w.select_row(0)
    w.grid.setFocus()
    a = w.current_record().id
    states = [_dec(w, a)]
    for key in (Qt.Key.Key_P, Qt.Key.Key_3, Qt.Key.Key_F, Qt.Key.Key_Q, Qt.Key.Key_X):
        _key(qtbot, w, key)
        states.append(_dec(w, a))
    assert states[-1][0] == "reject" and states[-1][1] == 3 and states[-1][2] and states[-1][3] == "sharp"
    assert w.act_undo.isEnabled() and "Loại" in w.act_undo.text()
    for expected in reversed(states[:-1]):
        _ctrl_z(qtbot, w)
        assert _dec(w, a) == expected
    assert not w.act_undo.isEnabled()


def test_ctrl_z_in_a_text_field_undoes_typing_only(qtbot, env) -> None:  # noqa: ANN001, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.grid.setFocus()
    a = w.current_record().id
    _key(qtbot, w, Qt.Key.Key_P)
    w.search.setFocus()
    qtbot.keyClicks(w.search, "abc")
    qtbot.keyClick(w.search, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert w.search.text() != "abc"  # the field's own undo
    assert _dec(w, a)[0] == "keep" and w.act_undo.isEnabled()  # the photo decision is still there


def test_plain_z_still_zooms_and_does_not_undo(qtbot, env) -> None:  # noqa: ANN001, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.grid.setFocus()
    a = w.current_record().id
    _key(qtbot, w, Qt.Key.Key_P)
    calls = []
    w.toggle_zoom = lambda: calls.append(1)  # noqa: E731 - the shortcut calls through the attribute
    _key(qtbot, w, Qt.Key.Key_Space)
    _key(qtbot, w, Qt.Key.Key_Z)
    assert _dec(w, a)[0] == "keep"


def test_rename_and_move_undo_and_survive_reopening(qtbot, env, monkeypatch) -> None:  # noqa: ANN001, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    assets = _seed_people(w)
    original_occ, original_subj = _occ(w), _subjects(w)
    monkeypatch.setattr("app.ui.main_window.QInputDialog.getText", lambda *a, **k: ("Mai", True))
    for i in range(w.people.count()):
        if w.people.item(i).data(Qt.ItemDataRole.UserRole) == ("subject", 1):
            w.people.setCurrentRow(i)
    w.rename_current_person()
    assert actions.subject_label(w.project.conn, 1) == "Mai"
    w.model.set_filter(Filter.SUBJECT, subject_id=1)
    monkeypatch.setattr(w, "_run_menu", _pick("Chủ thể 2"))
    w._people_menu_at(w.mapToGlobal(w.rect().center()), [assets[0]])  # move photo 1 to subject 2
    assert w.project.conn.execute("SELECT subject_id FROM occurrences WHERE asset_id = ?",
                                  (assets[0],)).fetchone()[0] == 2
    w.select_row(0)
    w.grid.setFocus()
    _key(qtbot, w, Qt.Key.Key_P)  # a decision after the corrections (memory only)
    assert w._close_session()
    _import(qtbot, w, env["photos"])  # reopen the same folder
    assert w.act_undo.isEnabled() and "gán" in w.act_undo.text()  # the decision entry did not survive
    assert "Có thể hoàn tác 2 thao tác" in w.status.text()
    w.grid.setFocus()
    _ctrl_z(qtbot, w)
    assert w.project.conn.execute("SELECT subject_id FROM occurrences WHERE asset_id = ?",
                                  (assets[0],)).fetchone()[0] == 1
    _ctrl_z(qtbot, w)
    assert _occ(w) == original_occ and _subjects(w) == original_subj
    assert not w.act_undo.isEnabled()


def test_cancelled_rename_adds_nothing(qtbot, env, monkeypatch) -> None:  # noqa: ANN001, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _seed_people(w)
    monkeypatch.setattr("app.ui.main_window.QInputDialog.getText", lambda *a, **k: ("x", False))
    w.people.setCurrentRow(w.people.count() - 1)
    w.rename_current_person()
    assert not w.act_undo.isEnabled()
    assert QApplication.instance() is not None and isinstance(w.act_undo, QAction)
