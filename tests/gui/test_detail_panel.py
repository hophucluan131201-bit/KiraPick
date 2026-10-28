"""Detail panel: preview, Chọn/Loại/Bỏ chọn, and the tabs Phân tích AI / Thông tin ảnh / Ảnh tương tự / Chủ thể."""

from __future__ import annotations

from pathlib import Path

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
    w._people_menu_at = lambda pos: calls.append(pos)  # noqa: SLF001
    w.detail.people_button.click()
    assert len(calls) == 1
