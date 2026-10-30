"""Compare mode, part 2 task 6: the AI line (I) from the real measurements only, the arrangement choice kept in the
settings (a small-window fallback never overwrites it); review notes RV-P2-B2A-01 (grid scroll kept) and
RV-P2-B2A-02 (the panel showing a photo outside the compared set)."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest

from app.quality.rank import Ranked
from app.quality.score import Score
from app.ui import main_window as mw
from app.ui.compare_view import compare_ai_text
from app.ui.score_style import EYES_CLOSED
from tests.gui.test_compare_tile import _record
from tests.gui.test_compare_window import _mark, _opened
from tests.gui.test_main_window import _import, _key, _photo, _window, env  # noqa: F401 - fixture


def _scored(path: Path, *, eyes: float = 90.0, taste: float | None = 85.2, weak: list[str] | None = None):  # noqa: ANN202
    score = Score(total=78.4, parts={"eyes": eyes, "focus": 80.0}, confidence=1.0,
                  weaknesses=["mắt hơi mềm"] if weak is None else weak)
    return _record(path, score=score, ranked=Ranked(78.4, taste, 81.0))


def test_ai_text_values(tmp_path: Path) -> None:
    p = tmp_path / "a.jpg"
    assert compare_ai_text(_scored(p)) == "K 78 · G 85 · Mắt hơi mềm"
    assert compare_ai_text(_scored(p, taste=None)) == "K 78 · Mắt hơi mềm"  # taste not ready: no G
    assert compare_ai_text(_scored(p, weak=[])) == "K 78 · G 85"
    assert compare_ai_text(_scored(p, eyes=EYES_CLOSED)).startswith("⚠ K 78")
    unscored = compare_ai_text(_record(p))
    assert unscored == "chưa phân tích" and not re.search(r"\d", unscored)
    nothing = _record(p, score=Score(total=None, parts={}, confidence=0.0), ranked=Ranked(None, None, None))
    assert compare_ai_text(nothing) == "chưa chấm được" and not re.search(r"\d", compare_ai_text(nothing))


def test_i_toggles_all_tiles_and_persists(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    tiles = [w.compare.tile(i) for i in ids]
    assert not any(t.ai_label.isVisible() for t in tiles)  # hidden by default
    _key(qtbot, w, Qt.Key.Key_I)
    assert all(t.ai_label.isVisible() for t in tiles)
    assert [t.ai_label.text() for t in tiles] == [compare_ai_text(r) for r in w.compare.records()]
    assert w.settings.value("compare/show_ai", False, bool) is True
    w.leave_compare()
    w2 = _window(qtbot, env)  # a new window: the choice is remembered
    _import(qtbot, w2, env["photos"])
    w2.select_row(0)
    _mark(w2, [0, 1], current=0)
    _key(qtbot, w2, Qt.Key.Key_C)
    assert all(w2.compare.tile(r.id).ai_label.isVisible() for r in w2.compare.records())
    _key(qtbot, w2, Qt.Key.Key_I)
    assert not any(w2.compare.tile(r.id).ai_label.isVisible() for r in w2.compare.records())
    assert w2.settings.value("compare/show_ai", True, bool) is False


def test_ai_line_follows_a_reload(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    _key(qtbot, w, Qt.Key.Key_I)
    real = w.model.records_by_id

    def scored(asset_ids):  # noqa: ANN001, ANN202 - as if the analysis had measured them
        return {i: replace(r, score=Score(total=66.0, parts={"eyes": 90.0, "focus": 80.0}, confidence=1.0),
                           ranked=Ranked(66.0, None, 66.0)) for i, r in real(asset_ids).items()}

    monkeypatch.setattr(w.model, "records_by_id", scored)
    w.reload_preserving_view()
    assert w.compare.tile(ids[0]).ai_label.text() == "K 66"


def test_i_ignored_while_typing(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    w.search.setFocus()
    QTest.keyClick(w.search, Qt.Key.Key_I)
    assert w.search.text() == "i"
    assert not any(w.compare.tile(i).ai_label.isVisible() for i in ids)


def test_arrangement_menu_persists_and_fallback_keeps_the_choice(qtbot, env: dict) -> None:  # noqa: F811
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    menu = w.compare.arrange_button.menu()
    assert [a.text() for a in menu.actions()] == ["Tự động", "Một hàng", "Lưới 2×2"]
    next(a for a in menu.actions() if a.text() == "Một hàng").trigger()
    assert w.settings.value("compare/arrangement") == "row"
    assert (w.compare.arrangement.rows, w.compare.arrangement.cols) == (1, 3)
    assert w.compare.arrange_button.text() == "Xếp: Một hàng"
    w.leave_compare()
    w2 = _window(qtbot, env, size=(580, 400))  # TINY: one row of four is too small (photos ~138 px < 160)
    _import(qtbot, w2, env["photos"])
    w2.select_row(0)
    _mark(w2, [0, 1, 2, 3], current=0)
    _key(qtbot, w2, Qt.Key.Key_C)
    qtbot.wait(200)
    assert w2.compare.mode == "row" and w2.compare.arrangement.fallback
    assert w2.compare.arrange_button.text() == "Xếp: Tự động (cửa sổ nhỏ)"
    assert w2.settings.value("compare/arrangement") == "row"  # the saved choice is not overwritten
    w2.resize(1600, 1000)
    qtbot.wait(400)
    assert not w2.compare.arrangement.fallback and (w2.compare.arrangement.rows, w2.compare.arrangement.cols) == (1, 4)
    assert w2.compare.arrange_button.text() == "Xếp: Một hàng"


def test_bad_saved_arrangement_falls_back_to_auto(qtbot, env: dict) -> None:  # noqa: F811
    QSettings(env["ini"], QSettings.Format.IniFormat).setValue("compare/arrangement", "spiral")
    w, _ids = _opened(qtbot, env, [0, 1], current=0)
    assert w.compare.mode == "auto"


def test_grid_scroll_kept_when_compare_opens_and_closes(qtbot, tmp_path: Path, monkeypatch) -> None:
    """RV-P2-B2A-01: a session large enough to scroll; the scroll position is the same after Esc, also when the
    current photo is scrolled out of view."""
    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    photos = tmp_path / "many"
    for i in range(80):
        _photo(photos / f"IMG_{i:04d}.jpg", i, size=(300, 200), taken=f"2026:10:25 16:{i // 60:02d}:{i % 60:02d}")
    w = _window(qtbot, {"ini": str(tmp_path / "s.ini")})
    _import(qtbot, w, photos)
    bar = w.grid.verticalScrollBar()
    assert bar.maximum() > 0
    for current, value in ((40, None), (2, bar.maximum())):  # current visible; current far out of view
        w.select_row(current)
        _mark(w, [current, current + 1], current=current)
        if value is not None:
            bar.setValue(value)
        before = bar.value()
        _key(qtbot, w, Qt.Key.Key_C)
        assert w.in_compare()
        _key(qtbot, w, Qt.Key.Key_Escape)
        assert bar.value() == before


def test_panel_on_a_photo_outside_the_compared_set_says_so(qtbot, env: dict) -> None:  # noqa: F811
    """RV-P2-B2A-02: Ảnh tương tự shows a photo outside the set in the panel: the status says where the keys go."""
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    other = w.model.record(w.model.index(4)).id
    w.detail.neighbour_clicked.emit(other)
    assert w.detail.shown_id == other
    assert w.status.text() == ("Bảng chi tiết đang hiện ảnh ngoài nhóm so sánh — phím tắt vẫn áp dụng cho ảnh có "
                               "viền xanh; rê chuột lên một ảnh để quay lại.")


def test_an_action_rereads_decisions_only(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """P / X / stars / ⟳ in Compare (task 8 perf): the compared records get their decisions and Xoay xem re-read,
    the session is not scored again (records_by_id took ~200 ms per press at 10,000 photos); the AI line stays."""
    from app.storage import decisions
    from app.ui.asset_model import Filter
    from tests.gui.test_compare_actions import _hover

    w, ids = _opened(qtbot, env, [0, 1], current=0)
    _key(qtbot, w, Qt.Key.Key_I)
    real = w.model.records_by_id
    monkeypatch.setattr(w.model, "records_by_id", lambda asset_ids: {
        i: replace(r, score=Score(total=66.0, parts={"eyes": 90.0}, confidence=1.0), ranked=Ranked(66.0, None, 66.0))
        for i, r in real(asset_ids).items()})
    w.reload_preserving_view()
    with w.project.transaction() as conn:
        decisions.set_flag(conn, ids[0], "keep")
    w.model.set_filter(Filter.KEEP)  # photo 2 is not in the grid's list any more: re-read anyway
    w.reload_preserving_view()
    calls = []
    monkeypatch.setattr(w.model, "records_by_id", lambda asset_ids: calls.append(asset_ids) or real(asset_ids))
    _hover(w, ids[1])
    _key(qtbot, w, Qt.Key.Key_X)
    _key(qtbot, w, Qt.Key.Key_3)
    w.rotate_view()
    assert calls == []
    tile = w.compare.tile(ids[1])
    rec = next(r for r in w.compare.records() if r.id == ids[1])
    assert rec.flag == "reject" and rec.rating == 3 and rec.rotation == 1
    assert "Loại" in tile.header.toolTip() and tile.ai_label.text() == "K 66"
    assert next(r for r in w.compare.records() if r.id == ids[0]).flag == "keep"  # the other photo untouched


def test_an_action_on_a_photo_gone_leaves_compare(qtbot, env: dict) -> None:  # noqa: F811
    from tests.gui.test_compare_actions import _hover

    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    _hover(w, ids[1])
    with w.project.transaction() as conn:
        conn.execute("DELETE FROM assets WHERE id = ?", (ids[1],))
    w._refresh_compare([ids[1]])
    assert not w.in_compare()
    assert w.status.text() == "Một ảnh đang so sánh không còn trong danh sách — đã về lưới."
