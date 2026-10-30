"""Compare mode, part 2 task 5 (CR-P2-01): every culling action in Compare changes the active photo only.
The other compared photos' rows in decisions, view_rotation and occurrences are identical before and after; the
grid's current photo and the marking never change; nothing advances."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.storage import decisions
from app.ui.compare_view import PANEL_DELAY_MS
from tests.gui.test_compare_window import _mark
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture
from tests.gui.pointer import move_os_cursor, move_pointer

_TABLES = ("decisions", "view_rotation", "occurrences")
REFUSED = "Bảng chi tiết chưa kịp đổi sang ảnh đang chọn — bấm lại."


def _rows(conn, asset_id: int) -> dict[str, list[tuple]]:  # noqa: ANN001
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} WHERE asset_id = ? ORDER BY rowid", (asset_id,))]
            for t in _TABLES}


def _state(conn, asset_id: int) -> tuple:  # noqa: ANN001
    d = decisions.get(conn, asset_id)
    turns = conn.execute("SELECT quarter_turns FROM view_rotation WHERE asset_id = ?", (asset_id,)).fetchone()
    focus = conn.execute("SELECT focus FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (asset_id,)).fetchone()
    return d.flag, d.rating, d.favorite, focus[0] if focus else None, turns[0] if turns else 0


def _hover(w, asset_id: int) -> None:  # noqa: ANN001
    """The real pointer onto that tile's viewer (review RV-P2-B1-01)."""
    viewport = w.compare.tile(asset_id).viewer.viewport()
    move_pointer(w.compare.back_button, w.compare.back_button.rect().center())  # from outside the tiles: a real
    move_pointer(viewport, viewport.rect().center())  # move even when the last test left the pointer here
    assert w.compare.active_id == asset_id


def _setup(qtbot, env: dict):  # noqa: ANN001, ANN202, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.act_auto_advance.setChecked(True)  # would advance outside Compare: must not in Compare
    w.select_row(0)
    ids = _mark(w, [0, 1, 3], current=0)
    with w.project.transaction() as conn:  # the active photo starts with something every action can change
        decisions.set_flag(conn, ids[1], "keep")
        decisions.set_rating(conn, ids[1], 2)
    w.reload_preserving_view()
    _key(qtbot, w, Qt.Key.Key_C)
    assert w.in_compare()
    return w, ids


def _menu_action(w, text: str) -> QAction:  # noqa: ANN001
    return next(a for a in w.bottom_bar.more_button.menu().actions() if a.text() == text)


# action name → (how to trigger, the active photo's expected state (flag, rating, favorite, focus, turns))
ACTIONS = {
    "P": (lambda w: QTest.keyClick(w, Qt.Key.Key_P), ("keep", 2, False, None, 0)),
    "K": (lambda w: QTest.keyClick(w, Qt.Key.Key_K), ("keep", 2, False, None, 0)),
    "X": (lambda w: QTest.keyClick(w, Qt.Key.Key_X), ("reject", 2, False, None, 0)),
    "U": (lambda w: QTest.keyClick(w, Qt.Key.Key_U), (None, 2, False, None, 0)),
    **{str(n): ((lambda w, n=n: QTest.keyClick(w, getattr(Qt.Key, f"Key_{n}"))), ("keep", n, False, None, 0))
       for n in range(0, 6)},
    "F": (lambda w: QTest.keyClick(w, Qt.Key.Key_F), ("keep", 2, True, None, 0)),
    "Q": (lambda w: QTest.keyClick(w, Qt.Key.Key_Q), ("keep", 2, False, "sharp", 0)),
    "W": (lambda w: QTest.keyClick(w, Qt.Key.Key_W), ("keep", 2, False, "soft", 0)),
    "R": (lambda w: QTest.keyClick(w, Qt.Key.Key_R), ("keep", 2, False, "missed", 0)),
    "detail keep": (lambda w: w.detail.keep_button.click(), ("keep", 2, False, None, 0)),
    "detail reject": (lambda w: w.detail.reject_button.click(), ("reject", 2, False, None, 0)),
    "detail clear": (lambda w: w.detail.clear_button.click(), (None, 2, False, None, 0)),
    "detail 4 stars": (lambda w: w.detail.star_buttons[3].click(), ("keep", 4, False, None, 0)),
    "detail favorite": (lambda w: w.detail.favorite_button.click(), ("keep", 2, True, None, 0)),
    "bar keep": (lambda w: w.bottom_bar.keep_button.click(), ("keep", 2, False, None, 0)),
    "bar reject": (lambda w: w.bottom_bar.reject_button.click(), ("reject", 2, False, None, 0)),
    "bar clear": (lambda w: w.bottom_bar.clear_button.click(), (None, 2, False, None, 0)),
    "bar 3 stars": (lambda w: w.bottom_bar.star_buttons[2].click(), ("keep", 3, False, None, 0)),
    "bar rotate": (lambda w: w.bottom_bar.rotate_button.click(), ("keep", 2, False, None, 1)),
    "menu clear": (lambda w: _menu_action(w, "Bỏ chọn").trigger(), (None, 2, False, None, 0)),
    "menu rotate": (lambda w: _menu_action(w, "⟳ Xoay xem").trigger(), ("keep", 2, False, None, 1)),
    "menu 5 stars": (lambda w: _menu_action(w, "★★★★★").trigger(), ("keep", 5, False, None, 0)),
}


@pytest.mark.parametrize("name", list(ACTIONS))
def test_action_hits_active_only(qtbot, env: dict, name: str) -> None:  # noqa: F811
    w, ids = _setup(qtbot, env)
    trigger, expected = ACTIONS[name]
    _hover(w, ids[1])
    qtbot.wait(PANEL_DELAY_MS + 80)  # the panel shows the active photo (panel buttons are allowed)
    conn = w.project.conn
    others = {i: _rows(conn, i) for i in (ids[0], ids[2])}
    current, marked = w.current_record().id, sorted(r.id for r in w.selected_records())
    trigger(w)
    QApplication.processEvents()
    assert _state(conn, ids[1]) == expected, name
    assert {i: _rows(conn, i) for i in (ids[0], ids[2])} == others, name
    assert w.in_compare() and w.compare.active_id == ids[1]
    assert w.current_record().id == current and sorted(r.id for r in w.selected_records()) == marked
    tile = w.compare.tile(ids[1])
    assert tile.viewer._rotation == expected[4]  # the tile follows Xoay xem
    if expected[0] == "keep":
        assert "Chọn" in tile.header.toolTip()
    if expected[0] == "reject":
        assert "Loại" in tile.header.toolTip()


@pytest.mark.parametrize(("key", "flag"), [(Qt.Key.Key_X, "reject"), (Qt.Key.Key_P, "keep")])
def test_rapid_hover_then_key_before_the_panel_follows(qtbot, env: dict, key, flag: str) -> None:  # noqa: ANN001, F811
    """Batch 2 must / CR-P2-FINAL-01: hover A → B → C and press X or P at once (before 150 ms): only C changes; A and B
    keep byte-identical rows in decisions, view_rotation and occurrences."""
    w, ids = _setup(qtbot, env)
    conn = w.project.conn
    with w.project.transaction() as c:  # C starts with another state, so P and X both change it
        decisions.set_flag(c, ids[2], "reject" if flag == "keep" else "keep")
    before = {i: _rows(conn, i) for i in ids}
    for asset_id in (ids[0], ids[1], ids[2]):
        _hover(w, asset_id)
    _key(qtbot, w, key)
    assert decisions.get(conn, ids[2]).flag == flag
    assert {i: _rows(conn, i) for i in ids[:2]} == {i: before[i] for i in ids[:2]}


def test_keys_after_leaving_tiles_hit_last_hovered(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _setup(qtbot, env)
    _hover(w, ids[2])
    move_pointer(w.detail, w.detail.rect().center())  # the pointer on the detail panel
    _key(qtbot, w, Qt.Key.Key_X)
    assert decisions.get(w.project.conn, ids[2]).flag == "reject"
    assert decisions.get(w.project.conn, ids[0]).flag is None


def test_panel_button_refused_while_panel_lags(qtbot, env: dict) -> None:  # noqa: F811
    """Batch 2 must: the panel still shows A while B is active → the panel's button changes nothing."""
    w, ids = _setup(qtbot, env)
    _hover(w, ids[0])
    qtbot.wait(PANEL_DELAY_MS + 80)
    assert w.detail.shown_id == ids[0]
    w.compare._on_hovered(ids[2])  # B active, the panel has not followed yet (no leave, no wait)
    conn = w.project.conn
    before = {i: _rows(conn, i) for i in ids}
    for button in (w.detail.reject_button, w.detail.keep_button, w.detail.star_buttons[4], w.detail.favorite_button):
        button.click()
        assert w.status.text() == REFUSED
    assert {i: _rows(conn, i) for i in ids} == before


def test_people_menu_acts_on_panel_photo(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    from tests.gui.test_review_notes_t15 import _pick, _seed_people

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    assets = _seed_people(w)  # subject 1: assets[:4], subject 2: assets[4]
    w.select_row(0)
    ids = _mark(w, [0, 1, 2], current=0)
    _key(qtbot, w, Qt.Key.Key_C)
    _hover(w, ids[1])
    qtbot.wait(PANEL_DELAY_MS + 80)
    conn = w.project.conn
    others = {i: _rows(conn, i) for i in (ids[0], ids[2])}
    monkeypatch.setattr(w, "_run_menu", _pick("Chủ thể 2"))
    w.detail.people_menu_requested.emit(w.mapToGlobal(w.rect().center()))
    assert conn.execute("SELECT subject_id FROM occurrences WHERE asset_id = ?", (ids[1],)).fetchone()[0] == 2
    assert {i: _rows(conn, i) for i in (ids[0], ids[2])} == others
    assert assets


def test_people_menu_refused_while_panel_lags(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    from tests.gui.test_review_notes_t15 import _pick, _seed_people

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _seed_people(w)
    w.select_row(0)
    ids = _mark(w, [0, 1, 2], current=0)
    _key(qtbot, w, Qt.Key.Key_C)
    w.compare._on_hovered(ids[2])  # panel still on ids[0]
    conn = w.project.conn
    before = {i: _rows(conn, i) for i in ids}
    monkeypatch.setattr(w, "_run_menu", _pick("Chủ thể 2"))
    w.detail.people_menu_requested.emit(w.mapToGlobal(w.rect().center()))
    assert w.status.text() == REFUSED and {i: _rows(conn, i) for i in ids} == before


def test_e_z_plus_act_on_active_tile(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _setup(qtbot, env)
    with w.project.transaction() as conn:
        conn.execute("""INSERT INTO occurrences (asset_id, person_box, face_box, prominence, is_main, analysis_version,
                        created_at) VALUES (?, '[0.05,0.05,0.3,0.8]', '[0.1,0.1,0.1,0.15]', 1, 1, 1, 'n')""", (ids[1],))
    _hover(w, ids[1])
    for key in (Qt.Key.Key_Z, Qt.Key.Key_Plus, Qt.Key.Key_E):
        _key(qtbot, w, key)
        assert w.compare.tile(ids[1]).viewer.zoom is not None
        assert w.compare.tile(ids[0]).viewer.zoom is None and w.compare.tile(ids[2]).viewer.zoom is None
        assert w.in_compare() and w.center.currentIndex() != 2  # never the loupe


def test_neighbour_click_in_compare(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _setup(qtbot, env)
    other = w.model.record(w.model.index(4)).id
    current, records, active = w.current_record().id, [r.id for r in w.compare.records()], w.compare.active_id
    w.detail.neighbour_clicked.emit(other)
    assert w.detail.shown_id == other
    assert w.current_record().id == current and [r.id for r in w.compare.records()] == records
    assert w.compare.active_id == active


def test_marking_note_not_shown_in_compare(qtbot, env: dict) -> None:  # noqa: F811
    """"phím tắt áp dụng cho cả N" would be wrong in Compare: there they apply to the active photo only."""
    w, _ids = _setup(qtbot, env)
    w._update_counts()
    assert w.bottom_bar.marking.isHidden()


def test_outside_compare_unchanged(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    ids = _mark(w, [0, 2], current=0)
    _key(qtbot, w, Qt.Key.Key_X)  # the grid: every marked photo (part 1)
    assert all(decisions.get(w.project.conn, i).flag == "reject" for i in ids)


def test_os_cursor_sweep_then_x_hits_the_photo_under_it(qtbot, env: dict) -> None:  # noqa: F811
    """CR-P2-FINAL-01: the operating-system cursor (QCursor.setPos, not QTest) sweeps A → B → C, then X: C only."""
    w, ids = _setup(qtbot, env)
    qtbot.waitExposed(w)
    conn = w.project.conn
    before = {i: _rows(conn, i) for i in ids}
    assert move_os_cursor(w.compare.back_button)
    for asset_id in (ids[0], ids[1], ids[2]):
        assert move_os_cursor(w.compare.tile(asset_id).viewer.viewport()), asset_id
        assert w.compare.active_id == asset_id
    _key(qtbot, w, Qt.Key.Key_X)
    assert decisions.get(conn, ids[2]).flag == "reject"
    assert {i: _rows(conn, i) for i in ids[:2]} == {i: before[i] for i in ids[:2]}
