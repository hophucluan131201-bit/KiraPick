"""Bottom bar: Chọn / Loại / Chưa chọn counts (photos), the estimated export size (files), marking, actions."""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, Qt

from app.storage import decisions, view
from app.storage.stats import Counts
from app.ui.bottom_bar import BottomBar, size_text
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture

GB = 1_000_000_000


def test_counts_and_size_text(qtbot) -> None:  # noqa: ANN001
    bar = BottomBar()
    qtbot.addWidget(bar)
    bar.set_counts(Counts(total=10, keep=2, reject=3, undecided=4, errors=1, keep_bytes=int(2.46 * GB)),
                   include_pairs=True, marked=0)
    assert bar.kept.text() == "Đã chọn 2 ảnh (2,5 GB, gồm JPEG kèm)"
    assert bar.rejected.text() == "Đã loại 3" and bar.undecided.text() == "Chưa chọn 4"
    bar.set_counts(Counts(10, 2, 3, 4, 1, int(0.0412 * GB)), include_pairs=False, marked=0)
    assert bar.kept.text() == "Đã chọn 2 ảnh (41,2 MB)"
    assert size_text(0) == "0 MB" and size_text(int(1.26 * GB)) == "1,3 GB"


def test_size_tooltip_explains_estimate(qtbot) -> None:  # noqa: ANN001
    """Review RV3-01: photos vs files vs an estimate."""
    bar = BottomBar()
    qtbot.addWidget(bar)
    bar.set_counts(Counts(10, 2, 3, 4, 1, GB), include_pairs=True, marked=0)
    tip = bar.kept.toolTip()
    assert "1 ảnh" in tip and "file" in tip and "ước tính" in tip and "đã có sẵn" in tip and "trước khi ghép cặp" in tip


def test_marking_text_only_for_two_or_more(qtbot) -> None:  # noqa: ANN001
    bar = BottomBar()
    qtbot.addWidget(bar)
    c = Counts(10, 0, 0, 10, 0, 0)
    bar.set_counts(c, include_pairs=True, marked=1)
    assert bar.marking.isHidden()
    bar.set_counts(c, include_pairs=True, marked=5)
    assert not bar.marking.isHidden() and bar.marking.text().startswith("Đang đánh dấu 5 ảnh")


def test_compact_keeps_keep_reject_export_visible(qtbot) -> None:  # noqa: ANN001
    bar = BottomBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_counts(Counts(10, 150, 42, 862, 0, GB), include_pairs=True, marked=0)
    bar.set_compact(True)
    assert bar.kept.text() == "✓150 ✗42 ·862"
    for b in (bar.keep_button, bar.reject_button, bar.export_button, bar.more_button):
        assert b.isVisibleTo(bar)
    for b in (*bar.star_buttons, bar.rotate_button, bar.exif_button):
        assert not b.isVisibleTo(bar)
    texts = [a.text() for a in bar.more_button.menu().actions()]
    assert any("Xoay xem" in t for t in texts) and any("EXIF" in t for t in texts) and any("★" in t for t in texts)
    bar.set_compact(False)
    assert bar.rotate_button.isVisibleTo(bar) and not bar.more_button.isVisibleTo(bar)


def test_buttons_act_like_keys(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    a = w.current_record().id
    w.bottom_bar.keep_button.click()
    w.select_row(1)
    _key(qtbot, w, Qt.Key.Key_K)
    conn = w.project.conn
    assert decisions.get(conn, a).flag == decisions.get(conn, w.current_record().id).flag == "keep"
    w.select_row(0)
    w.bottom_bar.reject_button.click()
    assert decisions.get(conn, a).flag == "reject"
    w.bottom_bar.clear_button.click()
    assert decisions.get(conn, a).flag is None
    w.bottom_bar.star_buttons[4].click()
    assert decisions.get(conn, a).rating == 5
    w.bottom_bar.rotate_button.click()
    assert view.rotation(conn, a) == 1
    w.bottom_bar.exif_button.click()
    assert not w.detail.exif_section.collapsed


def test_bar_counts_follow_decisions_and_marking(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    _key(qtbot, w, Qt.Key.Key_K)
    assert w.bottom_bar.kept.text().startswith("Đã chọn 1 ảnh")
    sel = w.grid.selectionModel()
    sel.select(w.model.index(1), QItemSelectionModel.SelectionFlag.Select)
    sel.select(w.model.index(2), QItemSelectionModel.SelectionFlag.Select)
    qtbot.waitUntil(lambda: not w.bottom_bar.marking.isHidden(), timeout=1000)
    assert w.bottom_bar.marking.text().startswith("Đang đánh dấu 3 ảnh")
    assert w.status is w.bottom_bar.status  # old status messages land in the bar


def test_size_follows_include_pairs_toggle(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR3-05: switching "Kèm JPEG" in the export dialog updates the bar at once."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    _key(qtbot, w, Qt.Key.Key_K)
    assert "gồm JPEG kèm" in w.bottom_bar.kept.text()
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.include_pairs.setChecked(False)
    assert "gồm JPEG kèm" not in w.bottom_bar.kept.text()
    dialog.include_pairs.setChecked(True)
    assert "gồm JPEG kèm" in w.bottom_bar.kept.text()


def test_export_menu_offers_the_client_list(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    texts = [a.text() for a in w.bottom_bar.export_button.menu().actions()]
    assert any("danh sách khách" in t for t in texts)
