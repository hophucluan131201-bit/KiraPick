"""UX-1 (tester feedback 2026-11-13: "too complex for someone opening it the first time"): the first screen says what
KiraPick does in three steps; one word per meaning (P = Giữ, "chọn" = selecting cards, ⭐ = AI gợi ý); the reset is
not called "Làm lại" (= Redo), sits last in ⚙ and defaults to No; an empty people list says what to do next;
functions whose models are off are not shown; a keyboard focus is visible; the search hint is not cut."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app.ui import main_window as mw
from app.ui import theme
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


def test_first_screen_explains_the_app_in_three_steps(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.center.currentIndex() == 0 and w.empty_hint.isVisible()
    text = w.empty_hint.text()
    for step in ("Nhập ảnh", "Lọc", "Xuất", "P</b> giữ", "X</b> loại", "không bao giờ bị sửa"):
        assert step in text, step


def test_one_word_per_meaning(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    assert w.bottom_bar.keep_button.text() == "✓ Giữ" and w.detail.keep_button.text() == "✓ Giữ"
    assert w.bottom_bar.clear_button.text() == "Bỏ dấu" and w.detail.clear_button.text() == "Bỏ dấu"
    assert w.bottom_bar.kept.text().startswith("Đã giữ ") and w.bottom_bar.undecided.text().startswith("Chưa xét ")
    assert w.act_select.text() == "⭐ AI gợi ý" and w.top_bar.buttons["pick"].text().endswith("AI gợi ý")
    labels = [w.filters.item(i).text() for i in range(w.filters.count())]
    assert "Chưa xét" in labels and "Giữ ✓" in labels


def test_reset_is_named_for_what_it_does_last_in_the_menu_and_defaults_to_no(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    actions = [a for a in w.options_button.menu().actions() if not a.isSeparator()]
    assert actions[-1] is w.act_reset and "Làm lại" not in w.act_reset.text()
    seen = {}

    def question(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        seen["default"] = args[4] if len(args) > 4 else kwargs.get("defaultButton")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", question)
    w.reset_current_folder()
    assert seen["default"] == QMessageBox.StandardButton.No
    assert w.project is not None  # answered No: nothing forgotten, the folder stays open


def test_empty_people_list_says_what_to_do_next(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    assert w.people.count() == 0 and w.people_hint.isVisible() and w.people_hint.wordWrap()
    assert "🧠 Nhận diện chủ thể" in w.people_hint.text()


def test_functions_whose_models_are_off_are_hidden(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    registry = w._registry_or_default()
    if registry.status("clip_l14_image").state.name == "READY":  # pragma: no cover - CLIP is not allowed in this build
        return
    card = w.detail.score_card
    assert card.rows["aesthetic"].name.isHidden() and card.taste_row.isHidden()
    assert not w.act_taste_weight.isVisible()


def test_keyboard_focus_is_drawn_and_search_hint_fits(qtbot, env: dict) -> None:  # noqa: F811
    from PySide6.QtWidgets import QApplication

    assert "QPushButton:focus" in QApplication.instance().styleSheet() or "QPushButton:focus" in _theme_qss()
    w = _window(qtbot, env)
    hint = w.search.placeholderText()
    assert w.search.minimumWidth() >= w.search.fontMetrics().horizontalAdvance(hint) + 12


def _theme_qss() -> str:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    before = app.styleSheet()
    theme.apply_dark_theme(app)
    qss = app.styleSheet()
    app.setStyleSheet(before)
    return qss
