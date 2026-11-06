"""The mode picker (docs/design/che-do-lam-viec.md): NAV-01/02/03, UI-01 (sizes), MED-01; PER-01 for the switch."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.storage import decisions
from app.ui import main_window as mw
from app.ui.app_shell import AppShell
from app.ui.media_home import MediaHome
from app.ui.mode_picker import EVENT, PERSONAL, ModePicker
from tests.gui.test_main_window import _import, env  # noqa: F401 - fixture


@pytest.fixture
def picker(qtbot) -> ModePicker:  # noqa: ANN001
    from app.ui.theme import apply_dark_theme

    apply_dark_theme(QApplication.instance())
    p = ModePicker()
    qtbot.addWidget(p)
    p.resize(1280, 760)
    p.show()
    qtbot.waitExposed(p)
    return p


def _record(p: ModePicker) -> list[str]:
    got: list[str] = []
    p.chosen.connect(got.append)
    return got


# --- NAV-02: mouse and keyboard, one activation ------------------------------------------------------------------
def test_cards_text_and_default_focus(picker) -> None:  # noqa: ANN001
    assert picker.heading.text() == "Chọn chế độ làm việc"
    assert picker.cards[PERSONAL].title.text() == "Chụp cá nhân"
    assert picker.cards[PERSONAL].text.text() == "Gom ảnh theo chủ thể hoặc tạo hình."
    assert picker.cards[EVENT].title.text() == "Media sự kiện"
    assert picker.cards[EVENT].text.text() == "Duyệt ảnh theo diễn biến chương trình."
    assert picker.cards[EVENT].badge.text() == "Beta" and not picker.cards[PERSONAL].badge.isVisibleTo(picker)
    assert picker.cards[PERSONAL].hasFocus()


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space])
def test_keyboard_tab_then_activate(qtbot, picker, key) -> None:  # noqa: ANN001
    got = _record(picker)
    qtbot.keyClick(picker.cards[PERSONAL], Qt.Key.Key_Tab)
    assert picker.cards[EVENT].hasFocus()
    qtbot.keyClick(picker.cards[EVENT], Qt.Key.Key_Backtab)
    assert picker.cards[PERSONAL].hasFocus()
    qtbot.keyClick(picker.cards[PERSONAL], Qt.Key.Key_Tab)
    qtbot.keyClick(picker.cards[EVENT], key)
    qtbot.keyClick(picker.cards[EVENT], key)  # a second press does nothing more
    assert got == [EVENT]


def test_arrow_keys_move_between_cards(qtbot, picker) -> None:  # noqa: ANN001
    qtbot.keyClick(picker.cards[PERSONAL], Qt.Key.Key_Right)
    assert picker.cards[EVENT].hasFocus()
    qtbot.keyClick(picker.cards[EVENT], Qt.Key.Key_Left)
    assert picker.cards[PERSONAL].hasFocus()


@pytest.mark.parametrize(("key", "mode"), [(Qt.Key.Key_1, PERSONAL), (Qt.Key.Key_2, EVENT)])
def test_number_keys(qtbot, picker, key, mode) -> None:  # noqa: ANN001
    got = _record(picker)
    qtbot.keyClick(picker, key)
    assert got == [mode]


def test_click_and_double_click_open_once(qtbot, picker) -> None:  # noqa: ANN001
    got = _record(picker)
    card = picker.cards[PERSONAL]
    middle = card.rect().center()
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton, pos=middle)
    qtbot.mouseDClick(card, Qt.MouseButton.LeftButton, pos=middle)
    qtbot.mouseClick(picker.cards[EVENT], Qt.MouseButton.LeftButton, pos=picker.cards[EVENT].rect().center())
    assert got == [PERSONAL]
    picker.reset()  # shown again after leaving a mode: a new choice is possible
    qtbot.mouseClick(picker.cards[EVENT].text, Qt.MouseButton.LeftButton)  # a click on the words counts too
    assert got == [PERSONAL, EVENT]


def test_hidden_picker_ignores_keys(qtbot, picker) -> None:  # noqa: ANN001
    got = _record(picker)
    picker.hide()
    picker._choose(PERSONAL)
    assert got == []


# --- UI-01: every size down to the smallest window ---------------------------------------------------------------
def _fits(label: QLabel) -> bool:
    return label.isVisible() and label.width() >= min(label.sizeHint().width(), label.width() + 1) - 1


@pytest.mark.parametrize(("size", "side_by_side", "pictures"), [
    ((1920, 1080), True, True), ((1280, 720), True, True), ((900, 400), True, False),
    ((700, 900), False, True), ((700, 500), False, False), ((560, 300), False, False),
])
def test_sizes(qtbot, picker, size, side_by_side, pictures) -> None:  # noqa: ANN001
    picker.resize(*size)
    qtbot.wait(20)
    assert picker.size().width() >= 560 and picker.size().height() >= 300
    first, second = picker.cards[PERSONAL], picker.cards[EVENT]
    if side_by_side:
        assert first.geometry().right() < second.geometry().left()
        assert abs(first.geometry().top() - second.geometry().top()) <= 1
    else:
        assert first.geometry().bottom() < second.geometry().top()
    for card in (first, second):
        assert card.picture.isVisible() is pictures
        assert card.isVisible() and card.height() >= 50 and card.width() >= 200
        assert picker.rect().contains(card.geometry())  # nothing outside the window
        for label in (card.title, card.text):
            assert label.isVisible() and label.width() >= 40
            assert card.rect().contains(label.geometry().translated(label.parentWidget().mapTo(card, QPoint(0, 0))))
    assert picker.heading.isVisible()


def test_card_titles_never_cut(qtbot, picker) -> None:  # noqa: ANN001
    for size in ((1920, 1080), (560, 300)):
        picker.resize(*size)
        qtbot.wait(20)
        for card in picker.cards.values():
            assert card.title.width() >= card.title.sizeHint().width() - 1


# --- the shell: NAV-01, NAV-03, MED-01 ---------------------------------------------------------------------------
@pytest.fixture
def shell(qtbot, env, monkeypatch):  # noqa: ANN001, ANN201, F811
    from app.ui.theme import apply_dark_theme

    apply_dark_theme(QApplication.instance())
    settings = QSettings(env["ini"], QSettings.Format.IniFormat)
    made: list[mw.MainWindow] = []

    def factory(s: QSettings) -> mw.MainWindow:
        w = mw.MainWindow(settings=s)
        w._maximize_on_show = False
        w.resize(1600, 1000)
        made.append(w)
        return w

    s = AppShell(settings, personal_factory=factory)
    s.made = made
    qtbot.addWidget(s.picker)
    QApplication.instance().setQuitOnLastWindowClosed(False)  # tests only: nothing may end the test process
    closed: list[int] = []
    QApplication.instance().lastWindowClosed.connect(lambda: closed.append(1))
    s.closed = closed
    s.start()
    qtbot.waitExposed(s.picker)
    yield s
    import shiboken6

    for w in made:
        if shiboken6.isValid(w) and not w.isHidden():
            w._shutdown_ready = False
            w.close()


def test_every_start_shows_the_picker(qtbot, shell, env) -> None:  # noqa: ANN001, F811
    assert shell.picker.isVisible() and shell.main is None and shell.media is None
    qtbot.keyClick(shell.picker, Qt.Key.Key_2)
    assert shell.media is not None and shell.media.isVisible() and not shell.picker.isVisible()
    # a second start (the app opened again): the picker again, nothing was remembered
    again = AppShell(QSettings(env["ini"], QSettings.Format.IniFormat))
    qtbot.addWidget(again.picker)
    again.start()
    assert again.picker.isVisible() and again.main is None and again.media is None
    assert not any("mode" in k for k in QSettings(env["ini"], QSettings.Format.IniFormat).allKeys())


def test_personal_opens_the_culling_window(qtbot, shell) -> None:  # noqa: ANN001
    qtbot.keyClick(shell.picker.cards[PERSONAL], Qt.Key.Key_Return)
    assert len(shell.made) == 1 and shell.main is shell.made[0]
    w = shell.made[0]
    qtbot.waitExposed(w)
    assert not shell.picker.isVisible()
    assert w.act_switch_mode.isVisible() and w.project is None  # nothing imported or analysed by choosing
    assert w.analyze_thread is None and w.import_thread is None


def test_switch_mode_without_a_folder(qtbot, shell) -> None:  # noqa: ANN001
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)
    w = shell.made[0]
    qtbot.waitExposed(w)
    asked = []
    w._ask_leave_mode = lambda: asked.append(1) or True
    assert w.request_mode_change()
    qtbot.waitUntil(lambda: shell.picker.isVisible() and not w.isVisible(), timeout=10000)
    assert asked == [] and shell.main is None and shell.closed == []  # never "last window closed"
    assert shell.picker.focusWidget() is shell.picker.cards[PERSONAL]
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)  # a new choice works
    assert len(shell.made) == 2


def test_switch_mode_stay_keeps_the_session(qtbot, shell, env) -> None:  # noqa: ANN001, F811
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)
    w = shell.made[0]
    _import(qtbot, w, env["photos"])
    w.select_row(1)
    w.grid.setFocus()
    project = w.project
    w._ask_leave_mode = lambda: False
    assert not w.request_mode_change()
    assert w.isVisible() and w.project is project and w.current_record() is not None
    assert not shell.picker.isVisible() and not w._switching_mode


def test_switch_mode_leave_releases_then_reopens_with_data(qtbot, shell, env) -> None:  # noqa: ANN001, F811
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)
    w = shell.made[0]
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    asset = w.current_record().id
    w.set_flag("keep")
    w._ask_leave_mode = lambda: True
    assert w.request_mode_change()
    qtbot.waitUntil(lambda: shell.picker.isVisible() and not w.isVisible(), timeout=15000)
    assert w.project is None and shell.closed == []
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)
    again = shell.made[1]
    _import(qtbot, again, env["photos"])
    assert decisions.get(again.project.conn, asset).flag == "keep"  # PER-01: what was saved is still there


def test_switch_mode_while_an_export_runs_can_be_refused(qtbot, shell) -> None:  # noqa: ANN001
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)
    w = shell.made[0]
    w._export_may_stop = lambda doing: (doing == "đổi chế độ") and False  # "Không": keep copying
    assert w.request_mode_change()  # no folder: no question, the export question decides
    assert w.isVisible() and not shell.picker.isVisible() and not w._switching_mode


def test_leave_text_mentions_a_running_analysis(qtbot, shell) -> None:  # noqa: ANN001
    qtbot.keyClick(shell.picker, Qt.Key.Key_1)
    w = shell.made[0]
    assert "P / X / sao / ❤" in w.mode_change_text() and "Phân tích" not in w.mode_change_text()
    w.analyze_thread = object()
    try:
        assert "Phân tích đang chạy sẽ dừng" in w.mode_change_text()
    finally:
        w.analyze_thread = None


def test_switch_mode_is_hidden_outside_the_shell(qtbot, env) -> None:  # noqa: ANN001, F811
    w = mw.MainWindow(settings=QSettings(env["ini"], QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    assert not w.act_switch_mode.isVisible()


@pytest.mark.parametrize("how", ["button", "escape"])
def test_media_page_and_back(qtbot, shell, how) -> None:  # noqa: ANN001
    qtbot.keyClick(shell.picker, Qt.Key.Key_2)
    page = shell.media
    assert isinstance(page, MediaHome)
    qtbot.waitExposed(page)
    assert "đang được phát triển" in page.status.text() and page.focusWidget() is page.back_button
    if how == "button":
        qtbot.mouseClick(page.back_button, Qt.MouseButton.LeftButton)
    else:
        qtbot.keyClick(page, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: shell.picker.isVisible(), timeout=5000)
    assert shell.media is None and not page.isVisible() and shell.closed == []
    assert shell.made == []  # Media never opened the culling window


def test_special_entry_points_never_show_the_picker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import app.main as app_main

    def boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("the picker must not be built")

    monkeypatch.setattr("app.ui.app_shell.AppShell", boom)
    code = app_main.main(["KiraPick.exe", "--diagnose-grouping"])  # no arguments: an error code, no window
    assert code != 0


def test_switching_modes_many_times_opens_only_verified_weights(qtbot, shell, env) -> None:  # noqa: ANN001, F811
    """U6 (LIC-1 S12): personal (with a people analysis when the weights are present) -> picker -> Media -> picker,
    three times in one run: nothing outside the allow-list is ever opened, nothing bypasses the check."""
    from app.ai.models import ModelRegistry
    from app.ai.policy import LOAD_LOG

    LOAD_LOG.clear()
    can_analyse = ModelRegistry().can_detect()
    for i in range(3):
        qtbot.keyClick(shell.picker, Qt.Key.Key_1)
        w = shell.made[i]
        qtbot.waitExposed(w)
        if can_analyse and i == 0:
            _import(qtbot, w, env["photos"])
            w.start_analysis("people")
            qtbot.waitUntil(lambda: w.analyze_thread is None, timeout=60000)
            # the analysis runs in a child process: what it opened is recorded in the session (schema v8)
            child = [r[0] for r in w.project.conn.execute("SELECT DISTINCT model_id FROM analysis_run_models")]
            assert child and all(ModelRegistry().policy.verified(m) for m in child), child
        w._ask_leave_mode = lambda: True
        assert w.request_mode_change()
        qtbot.waitUntil(lambda: shell.picker.isVisible(), timeout=15000)
        qtbot.keyClick(shell.picker, Qt.Key.Key_2)
        media = shell.media
        assert media is not None and media.isVisible()
        qtbot.keyClick(media, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: shell.picker.isVisible(), timeout=15000)
    report = LOAD_LOG.report()
    registry = ModelRegistry()
    assert all(registry.policy.verified(m) for m in report["opened"]), report["opened"]
    assert not any(k.startswith("?") for k in report["skipped"])
    LOAD_LOG.clear()
