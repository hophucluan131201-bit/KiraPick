"""Bottom bar: Chọn / Loại / Chưa chọn counts (photos), the estimated export size (files), marking, actions."""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, Qt

from app.storage import decisions, view
from app.export.formats import ExportFormat
from app.storage.stats import Counts
from app.ui.bottom_bar import BottomBar, size_text
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture

GB = 1_000_000_000


def test_counts_and_size_text(qtbot) -> None:  # noqa: ANN001
    bar = BottomBar()
    qtbot.addWidget(bar)
    bar.set_counts(Counts(total=10, keep=2, reject=3, undecided=4, errors=1, keep_bytes=int(2.46 * GB)),
                   fmt=ExportFormat.RAW_JPEG, marked=0)
    assert bar.kept.text() == "Đã chọn 2 ảnh (2,5 GB, gồm JPEG kèm)"
    assert bar.rejected.text() == "Đã loại 3" and bar.undecided.text() == "Chưa chọn 4"
    bar.set_counts(Counts(10, 2, 3, 4, 1, int(0.0412 * GB)), fmt=ExportFormat.RAW, marked=0)
    assert bar.kept.text() == "Đã chọn 2 ảnh (41,2 MB, chỉ RAW)"
    bar.set_counts(Counts(10, 2, 3, 4, 1, int(0.0412 * GB)), fmt=ExportFormat.JPEG, marked=0)
    assert bar.kept.text() == "Đã chọn 2 ảnh (41,2 MB, chỉ JPEG)"
    assert size_text(0) == "0 MB" and size_text(int(1.26 * GB)) == "1,3 GB"


def test_size_tooltip_explains_estimate(qtbot) -> None:  # noqa: ANN001
    """Review RV3-01: photos vs files vs an estimate."""
    bar = BottomBar()
    qtbot.addWidget(bar)
    bar.set_counts(Counts(10, 2, 3, 4, 1, GB), fmt=ExportFormat.RAW_JPEG, marked=0)
    tip = bar.kept.toolTip()
    assert "1 ảnh" in tip and "file" in tip and "ước tính" in tip and "đã có sẵn" in tip and "trước khi ghép cặp" in tip


def test_marking_text_only_for_two_or_more(qtbot) -> None:  # noqa: ANN001
    bar = BottomBar()
    qtbot.addWidget(bar)
    c = Counts(10, 0, 0, 10, 0, 0)
    bar.set_counts(c, fmt=ExportFormat.RAW_JPEG, marked=1)
    assert bar.marking.isHidden()
    bar.set_counts(c, fmt=ExportFormat.RAW_JPEG, marked=5)
    assert not bar.marking.isHidden() and bar.marking.text().startswith("Đang đánh dấu 5 ảnh")


def test_compact_keeps_keep_reject_export_visible(qtbot) -> None:  # noqa: ANN001
    bar = BottomBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_counts(Counts(10, 150, 42, 862, 0, GB), fmt=ExportFormat.RAW_JPEG, marked=0)
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


def test_size_follows_the_format_choice(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR3-05 (Part 3: ② Định dạng replaces "Kèm JPEG"): the export dialog's choice updates the bar at once."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    _key(qtbot, w, Qt.Key.Key_K)
    assert "gồm JPEG kèm" in w.bottom_bar.kept.text()
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.format_buttons[ExportFormat.RAW].setChecked(True)
    assert "chỉ RAW" in w.bottom_bar.kept.text()
    dialog.format_buttons[ExportFormat.RAW_JPEG].setChecked(True)
    assert "gồm JPEG kèm" in w.bottom_bar.kept.text()


def test_export_menu_offers_the_client_list(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    texts = [a.text() for a in w.bottom_bar.export_button.menu().actions()]
    assert any("danh sách khách" in t for t in texts)


def test_every_menu_action_emits_its_signal(qtbot) -> None:  # noqa: ANN001
    """Each "⋯" and export-menu entry must reach its signal (a bare signal passed as triggered= never fires)."""
    bar = BottomBar()
    qtbot.addWidget(bar)
    seen: list[str] = []
    for name in ("clear", "rotate", "exif", "export_client"):
        getattr(bar, name).connect(lambda name=name: seen.append(name))
    bar.rating.connect(lambda n: seen.append(f"rating{n}"))
    for action in (*bar.more_button.menu().actions(), *bar.export_button.menu().actions()):
        action.trigger()
    assert seen == [*(f"rating{n}" for n in range(1, 6)), "clear", "rotate", "exif", "export_client"]


def test_compact_menu_has_clear_and_it_works(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR11-01: compact mode hides "Bỏ chọn", so "⋯" must offer it."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.bottom_bar.set_compact(True)
    clear = next(a for a in w.bottom_bar.more_button.menu().actions() if a.text() == "Bỏ chọn")
    conn = w.project.conn
    for row, flag in ((0, "keep"), (1, "reject")):
        w.select_row(row)
        w.set_flag(flag)
        clear.trigger()
        assert decisions.get(conn, w.current_record().id).flag is None


def test_client_export_asks_which_list(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """Review CR11-03: never pick a client list on the user's behalf."""
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from app.selection.client_list import MatchResult, save_collection

    def create_collection(conn, name, ids):  # noqa: ANN001, ANN202
        return save_collection(conn, name, MatchResult(matched={str(i): [i] for i in ids}), source_text="",
                               pattern="test")

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    told = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: told.append(a[2]))
    assert w.open_export_dialog(client_list=True) is None and "Khách chọn" in told[0]  # no list yet
    ids = [r.id for r in w.model.records()]
    with w.project.transaction() as conn:
        first = create_collection(conn, "Khách A", ids[:1])
        second = create_collection(conn, "Khách B", ids[1:3])
    asked = []
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: (asked.append(a[3]) or ("Khách B (2 ảnh)", True)))
    dialog = w.open_export_dialog(client_list=True)
    qtbot.addWidget(dialog)
    assert asked == [["Khách A (1 ảnh)", "Khách B (2 ảnh)"]]
    assert dialog.collection.currentData() == second and first != second
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("", False))  # cancelled: nothing opens
    assert w.open_export_dialog(client_list=True) is None


def test_format_survives_reopening_and_matches_the_bar(qtbot, env: dict) -> None:  # noqa: F811
    """Review CR11-04."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.set_flag("keep")
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.format_buttons[ExportFormat.JPEG].setChecked(True)
    dialog.close()
    again = w.open_export_dialog()
    qtbot.addWidget(again)
    assert again.format_buttons[ExportFormat.JPEG].isChecked() and w.settings.value("export/format") == "jpeg"
    assert "chỉ JPEG" in w.bottom_bar.kept.text()
    w._update_counts()  # a fresh refresh reads the same setting
    assert "chỉ JPEG" in w.bottom_bar.kept.text()
    w.close()

    from app.export.copy_export import Selection, estimated_bytes, select_ids
    from app.ui.bottom_bar import size_text

    w2 = _window(qtbot, env)  # same settings file, new window
    _import(qtbot, w2, env["photos"])  # reopens the same session
    conn = w2.project.conn
    size = estimated_bytes(conn, select_ids(conn, Selection.KEEP), fmt=ExportFormat.JPEG)
    assert w2.bottom_bar.kept.text() == f"Đã chọn 1 ảnh ({size_text(size)}, chỉ JPEG)"
    dialog2 = w2.open_export_dialog()
    qtbot.addWidget(dialog2)
    assert dialog2.format_buttons[ExportFormat.JPEG].isChecked()
