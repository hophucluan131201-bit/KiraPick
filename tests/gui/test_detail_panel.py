"""Detail panel: preview, Chọn/Loại/Bỏ chọn, and the tabs Phân tích AI / Thông tin ảnh / Ảnh tương tự / Chủ thể."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint

from app.learning.taste import TasteStatus
from app.quality.rank import Ranked
from app.quality.score import score
from app.storage import decisions
from app.ui.asset_model import AssetRecord
from app.ui.detail_panel import TABS, DetailPanel
from app.ui.grid import card_texts
from app.ui.score_style import COLORS, display_band
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture

NO_TASTE = TasteStatus(False, "Chưa đủ dữ liệu: 3/60 lựa chọn")


def _rec(i: int = 1, value: float | None = 74.5, values: dict | None = None, **kw) -> AssetRecord:  # noqa: ANN003
    r = AssetRecord(i, 1, Path(f"/x/{i}.jpg"), f"{i}.jpg", "jpg", "ok", None, None, None, 1, 1, None, None, **kw)
    if value is not None:
        r.score = score(values or {"eye_sharp": 0.6, "blink": 0.05, "face_quality": 0.6, "face_clip": 0.0,
                                   "face_luma": 60, "area": 0.3})
        r.ranked = Ranked(r.score.total, None, value)
    return r


def test_tabs_are_named_as_in_the_spec(qtbot) -> None:  # noqa: ANN001
    panel = DetailPanel()
    qtbot.addWidget(panel)
    assert TABS == ("Phân tích AI", "Thông tin ảnh", "Ảnh tương tự", "Chủ thể")
    assert [panel.tabs.tabText(i) for i in range(panel.tabs.count())] == list(TABS)


def test_ring_equals_grid_badge(qtbot) -> None:  # noqa: ANN001
    panel = DetailPanel()
    qtbot.addWidget(panel)
    rec = _rec()
    panel.show_record(rec, taste=NO_TASTE, people=None, neighbours=[])
    assert panel.score_card.value_text == card_texts(rec)[0] == "75"
    assert panel.score_card.ring_color == COLORS[display_band(rec.ranked)]
    assert "Kỹ thuật" not in panel.score_card.subtitle.text()  # taste not ready: only one number, no split
    rec.ranked = Ranked(70.0, 90.0, 80.0)
    panel.show_record(rec, taste=TasteStatus(True, "ok"), people=None, neighbours=[])
    assert panel.score_card.subtitle.text() == "Kỹ thuật 70 · Hợp gu 90"
    panel.show_record(_rec(value=None), taste=NO_TASTE, people=None, neighbours=[])
    assert panel.score_card.value_text == "—"


def test_unmeasured_criterion_is_not_a_zero_bar(qtbot) -> None:  # noqa: ANN001
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show_record(_rec(values={"body_sharp": 0.6}), taste=NO_TASTE, people=None, neighbours=[])
    rows = panel.score_card.rows
    assert rows["focus"].bar.isVisibleTo(panel) and rows["focus"].value.text() != "—"
    assert not rows["eyes"].bar.isVisibleTo(panel) and "chưa đo được" in rows["eyes"].value.text()
    assert "chưa đủ dữ liệu" in panel.score_card.taste_row.text().lower()


def test_suggestion_and_review_are_named_in_the_panel(qtbot) -> None:  # noqa: ANN001
    """Review RV7-03: the filmstrip hides chips; the panel always says them."""
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show_record(_rec(pick_rank=1), taste=NO_TASTE, people=None, neighbours=[])
    assert panel.score_card.suggestion.text() == "⭐ Đề xuất giữ"
    blurred = _rec(value=20.0, values={"eye_sharp": 0.05, "blink": 0.05})
    panel.show_record(blurred, taste=NO_TASTE, people=None, neighbours=[])
    assert panel.score_card.suggestion.text() == "⚠ Xem lại"


def test_buttons_change_the_current_photo(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    rec = w.current_record()
    w.detail.keep_button.click()
    assert decisions.get(w.project.conn, rec.id).flag == "keep"
    w.detail.reject_button.click()
    assert decisions.get(w.project.conn, rec.id).flag == "reject"
    w.detail.clear_button.click()
    assert decisions.get(w.project.conn, rec.id).flag is None
    w.detail.star_buttons[3].click()
    assert decisions.get(w.project.conn, rec.id).rating == 4


def test_exif_hidden_until_opened(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    assert w.detail.exif_section.collapsed
    w.detail.open_exif()
    assert w.detail.tabs.tabText(w.detail.tabs.currentIndex()) == "Thông tin ảnh"
    assert not w.detail.exif_section.collapsed
    w.select_row(1)
    assert w.detail.exif_section.collapsed  # closed again for the next photo


def test_neighbour_click_changes_current_photo(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])  # photos 1 s apart, nobody recognised yet: the burst is any photo ±3 s
    w.select_row(0)
    burst = w.detail.burst
    assert "±3 giây" in w.detail.burst_header.text() and "không so sánh dáng" in w.detail.burst_header.text()
    assert burst.count() == 3
    target = burst.item(1).data(0x0100)
    w.detail.neighbour_clicked.emit(target)
    assert w.current_record().id == target


def test_histogram_arrives_off_thread(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    hist = w.detail.score_card.histogram
    qtbot.waitUntil(lambda: hist.data is not None, timeout=5000)
    assert hist.data.bins.max() == 1.0 and "theo ảnh xem trước" in w.detail.score_card.histogram_label.text()


def test_late_histogram_of_previous_photo_is_ignored(qtbot) -> None:  # noqa: ANN001
    from app.quality.histogram import histogram
    import numpy as np

    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show_record(_rec(1), taste=NO_TASTE, people=None, neighbours=[])
    old = panel.score_card.histogram.token
    panel.show_record(_rec(2), taste=NO_TASTE, people=None, neighbours=[])
    panel.score_card.histogram.deliver(old, histogram(np.zeros((4, 4, 3), np.uint8)))
    assert panel.score_card.histogram.data is None  # the result for photo 1 arrived after photo 2 was shown


def test_people_tab_opens_the_same_actions_as_the_grid_menu(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    calls = []
    w._people_menu_at = lambda pos, assets: calls.append(assets)  # noqa: SLF001
    w.detail.people_button.click()
    assert len(calls) == 1


def _choose_new_subject(monkeypatch, w) -> None:  # noqa: ANN001
    """Make the people menu pick "➕ Tạo chủ thể mới…" instead of waiting for a click."""
    monkeypatch.setattr(w, "_run_menu", lambda menu, _pos: next(
        a for a in menu.actions() if a.text().startswith("➕")))


def test_people_button_acts_on_the_current_photo_only(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """Review CR9-01: photos 1-2 are marked in the grid, photo 4 is shown in the panel."""
    from PySide6.QtCore import QItemSelectionModel

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    sel = w.grid.selectionModel()
    sel.select(w.model.index(1), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sel.select(w.model.index(2), QItemSelectionModel.SelectionFlag.Select)
    sel.setCurrentIndex(w.model.index(4), QItemSelectionModel.SelectionFlag.NoUpdate)
    current = w.current_record().id
    calls = []
    monkeypatch.setattr(w, "create_subject_from", lambda assets, frm=None: calls.append(list(assets)))
    _choose_new_subject(monkeypatch, w)
    w.detail.people_button.click()
    assert calls == [[current]]
    w._grid_context_menu(QPoint(5, 5))  # the grid's own menu still acts on every marked photo
    marked = sorted(w.model.records()[i].id for i in (1, 2))
    assert sorted(calls[1]) == marked


def test_exif_stays_open_while_the_photo_is_the_same(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR9-02: Chọn / sao / ♥ refresh the panel but must not fold EXIF; another photo does."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.detail.open_exif()
    w.detail.keep_button.click()
    w.detail.star_buttons[2].click()
    w.detail.favorite_button.click()
    assert not w.detail.exif_section.collapsed
    assert w.detail.tabs.tabText(w.detail.tabs.currentIndex()) == "Thông tin ảnh"  # the tab is kept too
    w.select_row(1)
    assert w.detail.exif_section.collapsed


def test_histogram_cache_does_not_leak_across_sessions(qtbot, tmp_path) -> None:  # noqa: ANN001
    """Review CR9-04: asset ids restart at 1 in every session; the cache must not reuse another session's curve."""
    from PIL import Image

    from app.ui.score_card import HistogramWidget

    black, white = tmp_path / "a" / "thumb.jpg", tmp_path / "b" / "thumb.jpg"
    for path, value in ((black, 0), (white, 255)):
        path.parent.mkdir()
        Image.new("RGB", (40, 30), (value,) * 3).save(path)
    hist = HistogramWidget()
    qtbot.addWidget(hist)
    hist.request(1, black)
    hist.wait()
    qtbot.waitUntil(lambda: hist.data is not None)
    assert hist.data.shadows > 0.9
    hist.request(1, white)  # same asset id, another session's thumbnail
    hist.wait()
    qtbot.waitUntil(lambda: hist.data is not None)
    assert hist.data.highlights > 0.9
