"""Compare mode, part 2 task 4: the Compare page inside the main window — C / G / Esc / ⧉ So sánh, the grid state
kept, the detail panel on the panel photo, reloads (review RV-P2-B1-01, RV-P2-B1-03)."""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt
from PySide6.QtWidgets import QApplication

from app.storage import decisions
from app.ui import main_window as mw
from app.ui.asset_model import Filter
from app.ui.compare_layout import start_error
from app.ui.compare_view import PANEL_DELAY_MS
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture
from tests.gui.pointer import move_pointer, park_pointer  # noqa: F401 - autouse fixture


def _mark(w, rows: list[int], current: int | None = None) -> list[int]:  # noqa: ANN001
    """Ctrl+click-like marking of these grid rows; returns their asset ids in grid order."""
    sel = w.grid.selectionModel()
    sel.clearSelection()
    for r in rows:
        sel.select(w.model.index(r), QItemSelectionModel.SelectionFlag.Select)
    if current is not None:
        sel.setCurrentIndex(w.model.index(current), QItemSelectionModel.SelectionFlag.NoUpdate)
    return [w.model.record(w.model.index(r)).id for r in sorted(rows)]


def _opened(qtbot, env: dict, rows: list[int], current: int | None = None):  # noqa: ANN001, ANN202, F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(current if current is not None else rows[0])
    ids = _mark(w, rows, current)
    _key(qtbot, w, Qt.Key.Key_C)
    return w, ids


def test_c_with_wrong_counts(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    for rows, n in (([], 0), ([0], 1), ([0, 1, 2, 3, 4], 5)):
        w.select_row(0)
        _mark(w, rows)
        page = w.center.currentIndex()
        _key(qtbot, w, Qt.Key.Key_C)
        assert w.center.currentIndex() == page and not w.in_compare()
        assert w.status.text() == start_error(n)


def test_c_with_two_and_four(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [3, 1], current=3)
    assert w.in_compare() and w.center.currentIndex() == mw.COMPARE_PAGE
    assert [r.id for r in w.compare.records()] == ids  # grid order
    assert w.compare.active_id == w.current_record().id  # the current photo, compared
    w.leave_compare()
    _mark(w, [0, 1, 2, 4], current=5)  # current photo not compared → tile 1
    _key(qtbot, w, Qt.Key.Key_C)
    assert len(w.compare.records()) == 4 and w.compare.active_id == w.compare.records()[0].id


def test_leave_restores_everything(qtbot, env: dict) -> None:  # noqa: F811
    for leave in ("escape", "g", "button"):
        w, ids = _opened(qtbot, env, [1, 2, 4], current=2)
        current = w.current_record().id
        marked = sorted(r.id for r in w.selected_records())
        scroll = w.grid.verticalScrollBar().value()
        flt = w.model.current_filter
        w.compare.tile(ids[2]).viewer.set_zoom(1.0)
        if leave == "escape":
            _key(qtbot, w, Qt.Key.Key_Escape)
        elif leave == "g":
            _key(qtbot, w, Qt.Key.Key_G)
        else:
            w.compare.back_button.click()
        assert not w.in_compare() and w.center.currentIndex() == 1
        assert w.current_record().id == current and sorted(r.id for r in w.selected_records()) == marked
        assert w.grid.verticalScrollBar().value() == scroll and w.model.current_filter is flt
        assert not any(t.isVisible() for t in w.compare.tiles)
        w.close()


def test_arrows_space_enter_noop_in_compare(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1, 2], current=1)
    current, active = w.current_record().id, w.compare.active_id
    for key in (Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Space, Qt.Key.Key_Return):
        _key(qtbot, w, key)
        assert w.in_compare() and w.current_record().id == current and w.compare.active_id == active


def test_detail_panel_follows_panel_photo(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    current = w.current_record().id
    assert w.detail.shown_id == ids[0]
    w.compare._on_hovered(ids[1])
    assert w.detail.shown_id == ids[0]  # the panel waits 150 ms
    qtbot.wait(PANEL_DELAY_MS + 80)
    assert w.detail.shown_id == ids[1] and w.current_record().id == current
    assert w.view_record().id == ids[1]


def test_real_mouse_over_the_viewers_changes_the_target_at_once(qtbot, env: dict) -> None:  # noqa: F811
    """RV-P2-B1-01: the real pointer moving across the tiles' ImageViewer viewports (child widgets), not an event
    sent to the tile."""
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    QApplication.processEvents()
    move_pointer(w.compare.back_button, w.compare.back_button.rect().center())  # start outside the tiles
    for asset_id in (ids[2], ids[1], ids[0], ids[2]):
        viewport = w.compare.tile(asset_id).viewer.viewport()
        move_pointer(viewport, viewport.rect().center())
        assert w.compare.active_id == asset_id, asset_id  # no wait: the target is the tile under the pointer
        assert w.view_record().id == asset_id


def test_reload_keeps_zoom_pan_and_active(qtbot, env: dict) -> None:  # noqa: F811
    """RV-P2-B1-03: a reload with the same compared set refreshes records only."""
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    w.compare._on_hovered(ids[1])
    v = w.compare.tile(ids[2]).viewer
    v.set_zoom(2.0)
    zoom, centre = v.zoom, v.mapToScene(v.viewport().rect().center())
    token = v._token
    with w.project.transaction() as conn:  # a change made elsewhere (e.g. the analysis), then a reload
        decisions.set_flag(conn, ids[2], "keep")
    w.reload_preserving_view()
    assert w.in_compare() and w.compare.active_id == ids[1]
    assert v.zoom == zoom and v._token == token and v.mapToScene(v.viewport().rect().center()) == centre
    assert "Chọn" in w.compare.tile(ids[2]).header.toolTip()


def test_filtered_out_photo_stays_until_compare_closes(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    with w.project.transaction() as conn:
        decisions.set_flag(conn, ids[0], "keep")
    w.model.set_filter(Filter.KEEP)  # photo 2 no longer in the grid's list
    w.reload_preserving_view()
    assert w.in_compare() and [r.id for r in w.compare.records()] == ids


def test_photo_deleted_from_the_session_leaves_compare(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    with w.project.transaction() as conn:
        conn.execute("DELETE FROM assets WHERE id = ?", (ids[1],))
    w.reload_preserving_view()
    assert not w.in_compare() and w.center.currentIndex() == 1
    assert w.status.text() == "Một ảnh đang so sánh không còn trong danh sách — đã về lưới."


def test_teach_taste_wording() -> None:
    import pathlib

    sources = "".join(p.read_text(encoding="utf-8") for p in pathlib.Path("app/ui").glob("*.py"))
    assert "🎓 Dạy gu…" in sources and "So sánh ảnh…" not in sources


def test_compare_button_in_bottom_bar(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    ids = _mark(w, [0, 1])
    button = w.bottom_bar.compare_button
    assert "C" in button.toolTip() and "2–4" in button.toolTip()
    button.click()
    assert w.in_compare() and [r.id for r in w.compare.records()] == ids
    w.leave_compare()
    w.bottom_bar.set_compact(True)  # narrow windows: the same command in "⋯"
    assert not button.isVisible() or not w.bottom_bar.isVisible()
    texts = [a.text() for a in w.bottom_bar.more_button.menu().actions()]
    assert "⧉ So sánh" in texts


def test_key_hints_in_compare(qtbot, env: dict) -> None:  # noqa: F811
    w, _ids = _opened(qtbot, env, [0, 1], current=0)
    text = w.key_hints.text().replace("&nbsp;", " ")
    assert "Esc" in text and "về lưới" in text and "Rê chuột" in text


def test_compare_needs_a_session(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.show_compare() is False and not w.in_compare()


def test_view_buttons_leave_compare_cleanly(qtbot, env: dict) -> None:  # noqa: F811
    """▦ Lưới ảnh returns to the grid; 🔍 Xem lớn and the panel preview open the loupe of the grid's current photo —
    each closes Compare first (tiles emptied, nothing left loading in the background)."""
    for trigger in ("grid", "loupe", "preview"):
        w, ids = _opened(qtbot, env, [0, 1, 2], current=1)
        current = w.current_record().id
        tokens = {i: w.compare.tile(i).viewer._token for i in ids}
        if trigger == "grid":
            w.act_grid_view.trigger()
            assert w.center.currentIndex() == 1
        elif trigger == "loupe":
            w.act_loupe.trigger()
            assert w.center.currentIndex() == 2 and w.viewer._path == w.current_record().path
        else:
            w.detail.open_loupe.emit()
            assert w.center.currentIndex() == 2
        assert not w.in_compare() and w.current_record().id == current
        assert not any(t.isVisible() for t in w.compare.tiles)
        assert all(t.asset_id is None for t in w.compare.tiles)
        assert all(w.compare.tiles[k].viewer._token != tokens[i] for k, i in enumerate(ids))  # late loads ignored
        w.close()
