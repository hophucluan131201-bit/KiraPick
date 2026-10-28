"""Grid cards: the tick box changes Chọn only (never the current photo or the marking); one score; one chip."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt

from app.quality.rank import Ranked
from app.quality.score import score
from app.storage import decisions
from app.ui.asset_model import AssetRecord, Filter
from app.ui.grid import card_texts
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


def _ready(qtbot, env):  # noqa: ANN001, ANN202
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.grid.setFocus()
    qtbot.wait(50)
    return w


def _click_tick(qtbot, w, row: int, shift: bool = False) -> None:  # noqa: ANN001
    idx = w.model.index(row)
    rect = w.grid.itemDelegate().tick_rect(w.grid.visualRect(idx))
    mods = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    qtbot.mouseClick(w.grid.viewport(), Qt.MouseButton.LeftButton, mods, rect.center())


def _flags(w) -> list[str | None]:  # noqa: ANN001
    conn = w.project.conn
    return [decisions.get(conn, r.id).flag for r in w.model.records()]


def _marked(w) -> list[int]:  # noqa: ANN001
    return sorted(i.row() for i in w.grid.selectionModel().selectedIndexes())


def test_tick_toggles_keep_without_touching_selection(qtbot, env: dict) -> None:  # noqa: F811
    w = _ready(qtbot, env)
    sel = w.grid.selectionModel()
    sel.select(w.model.index(0), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sel.select(w.model.index(1), QItemSelectionModel.SelectionFlag.Select)
    sel.setCurrentIndex(w.model.index(2), QItemSelectionModel.SelectionFlag.NoUpdate)
    before_marked, before_current = _marked(w), w.grid.currentIndex().row()
    _click_tick(qtbot, w, 4)
    assert _flags(w)[4] == "keep" and w.model.records()[4].flag == "keep"
    assert _marked(w) == before_marked and w.grid.currentIndex().row() == before_current == 2
    _click_tick(qtbot, w, 4)  # again: back to undecided
    assert _flags(w)[4] is None


def test_tick_on_a_rejected_photo_keeps_it(qtbot, env: dict) -> None:  # noqa: F811
    w = _ready(qtbot, env)
    decisions.set_flag(w.project.conn, w.model.records()[3].id, "reject")
    w.model.refresh_record(w.model.records()[3].id)
    _click_tick(qtbot, w, 3)
    assert _flags(w)[3] == "keep"


def test_shift_tick_ticks_range(qtbot, env: dict) -> None:  # noqa: F811
    w = _ready(qtbot, env)
    _click_tick(qtbot, w, 1)
    _click_tick(qtbot, w, 4, shift=True)
    assert _flags(w)[:6] == [None, "keep", "keep", "keep", "keep", None]


def test_shift_tick_without_anchor_ticks_one(qtbot, env: dict) -> None:  # noqa: F811
    w = _ready(qtbot, env)
    _click_tick(qtbot, w, 1)
    w.model.set_filter(Filter.ALL)  # any filter / sort / search change resets the anchor
    w._after_filter()
    _click_tick(qtbot, w, 3, shift=True)
    assert _flags(w)[:5] == [None, "keep", None, "keep", None]


def test_tick_teaches_taste_like_the_key(qtbot, env: dict) -> None:  # noqa: F811
    w = _ready(qtbot, env)
    calls = []
    w._learn_taste = lambda targets: calls.append([r.id for r in targets])  # noqa: SLF001
    _click_tick(qtbot, w, 2)
    assert calls == [[w.model.records()[2].id]]


def _rec(value: float | None, **kw) -> AssetRecord:  # noqa: ANN003
    r = AssetRecord(1, 1, Path("/x/1.jpg"), "1.jpg", "jpg", "ok", None, None, None, 1, 1, None, None, **kw)
    if value is not None:
        r.score = score({"eye_sharp": 0.6, "blink": 0.05})
        r.ranked = Ranked(value, None, value)
    return r


def test_badge_shows_ranking_value_and_chip() -> None:
    assert card_texts(_rec(74.5)) == ("75", None)
    assert card_texts(_rec(None)) == ("—", None)
    assert card_texts(_rec(74.5, flag="keep"))[1] == "✅ Chọn"
    assert card_texts(_rec(74.5, pick_rank=1))[1] == "⭐ Đề xuất"
    blurred = _rec(20.0)
    blurred.score = score({"eye_sharp": 0.05, "blink": 0.05})
    assert card_texts(blurred) == ("⚠ 20", "⚠ Xem lại")
