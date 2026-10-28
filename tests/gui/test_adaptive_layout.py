"""Task 12: the adaptive layout (app.ui.layout_controller) — modes at real Windows Snap sizes, Tab per mode, drawer,
detail sheet, nothing lost on resize, no widget ever moves to another parent."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, QRunnable, QSize, Qt
from PySide6.QtWidgets import QApplication

from app.ui import asset_model
from app.ui.asset_model import Filter, Sort
from app.ui.detail_panel import TABS
from app.ui.layout_modes import DEBOUNCE_MS, Mode
from tests.gui.test_main_window import _import, _photo, _window, env  # noqa: F401 - fixture


def _at(qtbot, w, size: tuple[int, int]) -> None:  # noqa: ANN001
    w.resize(*size)
    qtbot.wait(DEBOUNCE_MS + 60)


REFERENCE = [((1920, 1000), Mode.WIDE), ((1536, 800), Mode.WIDE), ((1280, 667), Mode.MEDIUM),
             ((960, 1000), Mode.NARROW), ((768, 800), Mode.NARROW), ((1920, 484), Mode.SHORT),
             ((1280, 323), Mode.SHORT), ((2560, 683), Mode.SHORT), ((2560, 664), Mode.SHORT),
             ((3840, 1024), Mode.WIDE), ((580, 400), Mode.TINY),
             ((640, 667), Mode.NARROW), ((1536, 387), Mode.SHORT)]  # Snap: left half / top half at 150 % / 125 %


def test_modes_at_reference_sizes(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    for size, mode in REFERENCE:
        _at(qtbot, w, size)
        assert (w.width(), w.height()) == size
        assert w.layout_controller.mode is mode, size


def test_minimum_window_size(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.minimumSize() == QSize(560, 300)


def test_widget_parents_never_change(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    widgets = (w.sidebar, w.detail, w.grid, w.viewer, w.filters, w.people, w.detail.tabs, w.detail.preview,
               w.top_bar, w.bottom_bar, w.strip, w.rail)
    parents = [x.parent() for x in widgets]
    for size, _mode in REFERENCE:
        _at(qtbot, w, size)
        w.layout_controller.toggle_detail()
        w.layout_controller.open_drawer("people")
        w.layout_controller.close_drawer()
        assert [x.parent() for x in widgets] == parents, size
    assert w.sidebar.parent() is w.body and w.detail.parent() is w.body


def test_detail_visible_by_default_per_mode(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    for size, visible in (((1920, 1000), True), ((1280, 667), True), ((960, 1000), True), ((768, 800), False),
                          ((1920, 484), False), ((580, 400), False)):
        _at(qtbot, w, size)
        assert w.detail.isVisible() is visible, size


def test_resize_keeps_tab_choice(qtbot, env: dict) -> None:  # noqa: F811
    """Review RV6-05: a resize within the same mode never overwrites the Tab choice; it is kept per mode."""
    w = _window(qtbot, env)
    w.layout_controller.toggle_detail()  # WIDE: hide
    assert not w.detail.isVisible()
    _at(qtbot, w, (1700, 950))  # still WIDE
    assert w.layout_controller.mode is Mode.WIDE and not w.detail.isVisible()
    _at(qtbot, w, (960, 1000))  # NARROW has its own choice (default: shown)
    assert w.detail.isVisible()
    _at(qtbot, w, (1600, 1000))
    assert not w.detail.isVisible()


def test_short_tab_switches_focus(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(1)
    _at(qtbot, w, (1920, 484))
    lc = w.layout_controller
    assert lc.mode is Mode.SHORT
    assert w.strip.isVisible() and not w.detail.isVisible()  # Grid Focus
    assert w.strip.text().startswith(w.current_record().name)
    assert w.splitter.orientation() == Qt.Orientation.Vertical and w.grid.isWrapping()
    lc.toggle_detail()  # Detail Focus
    assert w.detail.isVisible() and not w.strip.isVisible() and not w.grid.isWrapping()
    assert w.detail.geometry().top() > w.grid_area.geometry().top()  # details below the grid
    assert w.settings.value("layout/short_focus") == "detail"
    lc.toggle_detail()
    assert w.strip.isVisible() and not w.detail.isVisible() and w.grid.isWrapping()
    assert w.settings.value("layout/short_focus") == "grid"


def test_narrow_tab_hides_detail_and_grid_keeps_two_columns(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _at(qtbot, w, (960, 1000))
    cell = w.grid.itemDelegate().sizeHint(None, w.model.index(0)).width()
    assert w.detail.isVisible() and w.grid.viewport().width() >= 2 * cell
    w.layout_controller.toggle_detail()
    assert not w.detail.isVisible() and w.grid.viewport().width() >= 3 * cell
    assert str(w.settings.value("layout/narrow_detail_visible")).lower() in ("false", "0")


def test_drawer_closes_on_escape_and_returns_focus(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    _at(qtbot, w, (960, 1000))
    w.activateWindow()
    w.grid.setFocus()
    lc = w.layout_controller
    lc.open_drawer("filters")
    assert w.sidebar.isVisible() and lc.scrim.isVisible() and lc.side.is_open
    assert w.sidebar.geometry().left() == 0 and not w.sections["filters"].collapsed
    qtbot.keyClick(QApplication.focusWidget() or w.sidebar, Qt.Key.Key_Escape)
    assert not lc.side.is_open and not w.sidebar.isVisible() and not lc.scrim.isVisible()
    assert QApplication.focusWidget() is w.grid


def test_detail_sheet_in_tiny_and_narrow_below_900(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    lc = w.layout_controller
    for size in ((768, 800), (580, 400)):
        _at(qtbot, w, size)
        assert lc.docked is False and not w.detail.isVisible() and w.splitter.sizes()[2] == 0
        lc.toggle_detail()  # opens the sheet over the photos
        assert w.detail.isVisible() and lc.scrim.isVisible()
        assert w.detail.geometry().right() == w.body.width() - 1 and w.detail.width() < w.body.width()
        lc.scrim.clicked.emit()  # a click beside the sheet closes it
        assert not w.detail.isVisible()
        _at(qtbot, w, (size[0] + 10, size[1]))  # and it stays closed after a resize
        assert not w.detail.isVisible()
    _at(qtbot, w, (960, 1000))
    assert lc.docked is True and w.detail.isVisible() and w.splitter.sizes()[2] > 0


def test_dpr_change_reevaluates_mode(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    asked: list[int] = []
    real = asset_model._ThumbTask

    class Recording(real):  # type: ignore[misc, valid-type]
        def __init__(self, asset_id, path, signals, target=asset_model.THUMB_DISPLAY) -> None:  # noqa: ANN001
            asked.append(target)
            super().__init__(asset_id, path, signals, target)

    monkeypatch.setattr(asset_model, "_ThumbTask", Recording)
    evaluated: list[bool] = []
    monkeypatch.setattr(w.layout_controller, "evaluate", lambda: evaluated.append(True))

    class Screen:
        def devicePixelRatio(self) -> float:  # noqa: N802 - Qt name
            return 2.0

    w.layout_controller.on_screen_changed(Screen())
    assert evaluated and w.model.device_pixel_ratio == 2.0
    rec = w.model.record(w.model.index(0))
    assert w.model.pixmap(rec) is None  # cached thumbnails were dropped: decoded again for the new screen
    assert asked == [2 * asset_model.THUMB_DISPLAY]


def test_3840x1024_wide_shows_grid_and_detail(qtbot, env: dict) -> None:  # noqa: F811
    """Review RV6-03."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    _at(qtbot, w, (3840, 1024))
    assert w.layout_controller.mode is Mode.WIDE
    cell = w.grid.itemDelegate().sizeHint(None, w.model.index(0)).width()
    assert w.grid.viewport().width() >= 4 * cell
    assert w.detail.isVisible() and w.detail.preview.height() >= 80
    bar = w.detail.tabs.tabBar()
    assert [bar.tabText(i) for i in range(bar.count())] == list(TABS)  # full titles, nothing clipped


@pytest.mark.parametrize("size", [(1920, 1000), (1280, 667), (960, 1000), (1920, 484), (2560, 683)])
def test_detail_tabs_fit(qtbot, env: dict, size: tuple[int, int]) -> None:  # noqa: F811
    """Task 9 UX note: tab titles fit without scroll arrows wherever the panel is shown; the preview never covers
    the stars, buttons or tabs."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    _at(qtbot, w, size)
    if not w.detail.isVisible():
        w.layout_controller.toggle_detail()
        qtbot.wait(50)  # the panel is laid out on the next event pass
    d = w.detail
    assert d.tabs.tabBar().sizeHint().width() <= d.tabs.width(), [d.tabs.tabText(i) for i in range(4)]
    preview_bottom = d.preview.mapTo(d, d.preview.rect().bottomLeft()).y()
    for below in (d.star_buttons[0], d.keep_button):
        assert below.mapTo(d, below.rect().topLeft()).y() >= preview_bottom
    if d.tabs.geometry().left() < d.top.geometry().right():  # tabs below the preview (not beside it)
        assert d.tabs.geometry().top() >= d.top.geometry().bottom()


def test_detail_tab_kept_on_refresh_and_mode_change(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    w.detail.tabs.setCurrentIndex(2)
    w.set_flag("keep")  # a refresh of the same photo
    assert w.detail.tabs.currentIndex() == 2
    for size in ((960, 1000), (1920, 484), (580, 400), (1600, 1000)):
        _at(qtbot, w, size)
        assert w.detail.tabs.currentIndex() == 2, size


def test_state_survives_a_full_mode_cycle(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    for row in range(w.model.rowCount()):
        w.select_row(row)
        w.set_flag("keep")
    keep_row = next(i for i in range(w.filters.count())
                    if (w.filters.item(i).data(Qt.ItemDataRole.UserRole) or (None,))[0] is Filter.KEEP)
    w.filters.setCurrentRow(keep_row)
    w.sort.setCurrentIndex(w.sort.findData(Sort.SCORE.value))
    w.search.setText("DSC")
    qtbot.wait(300)
    w.select_row(3)
    sel = w.grid.selectionModel()
    for row in (1, 2):
        sel.select(w.model.index(row), QItemSelectionModel.SelectionFlag.Select)
    w.detail.tabs.setCurrentIndex(1)
    w.detail.open_exif()
    w.bottom_bar.progress(3, 10, True)  # a job "running"
    w.show_loupe(True)
    w.viewer.set_zoom(2.0)

    def state() -> tuple:
        return (w.current_record().id, sorted(r.id for r in w.selected_records()), w.model.current_filter,
                w.sort.currentData(), w.search.text(), w.model.rowCount(), w.center.currentIndex(), w.viewer.zoom,
                w.detail.tabs.currentIndex(), w.detail.exif_section.collapsed, w.bottom_bar.progress_bar.value(),
                w.bottom_bar.progress_bar.isVisibleTo(w), [d.flag for d in (w.model.record(w.model.index(i))
                                                                            for i in range(w.model.rowCount()))])

    before = state()
    for size in ((960, 1000), (1920, 484), (580, 400), (1600, 1000)):  # WIDE → NARROW → SHORT → TINY → WIDE
        _at(qtbot, w, size)
    assert state() == before


def test_scroll_position_survives_mode_changes(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    many = tmp_path / "Nhiều ảnh"
    for i in range(40):
        _photo(many / f"IMG_{i:04d}.jpg", 100 + i, taken=f"2026:10:25 17:00:{i:02d}")
    w = _window(qtbot, env)
    _import(qtbot, w, many)
    w.select_row(30)
    w.grid.scrollTo(w.model.index(30), w.grid.ScrollHint.PositionAtTop)
    top = w.grid.indexAt(w.grid.viewport().rect().topLeft() + w.grid.viewport().rect().center() * 0).row()
    for size in ((960, 1000), (1920, 484), (580, 400), (1600, 1000)):
        _at(qtbot, w, size)
        current = w.grid.visualRect(w.grid.currentIndex())
        assert w.grid.viewport().rect().intersects(current), size  # the current photo stays in view
    assert abs(w.grid.indexAt(w.grid.viewport().rect().topLeft()).row() - top) < 8  # same part of the grid


def test_top_bar_while_a_job_runs(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """Review RV10-02: during an import the step buttons follow their actions: no second job can start."""
    import time

    from app.workers.import_job import ImportJob

    real = ImportJob._ingest_one
    monkeypatch.setattr(ImportJob, "_ingest_one", lambda self, a, p: (time.sleep(0.15), real(self, a, p))[1])
    w = _window(qtbot, env)
    started: list[object] = []
    monkeypatch.setattr(w, "start_analysis", lambda *a, **k: started.append(a))
    w.start_import(env["photos"])
    assert w.import_thread is not None
    for key in ("import", "people", "quality", "pick"):
        assert not w.top_bar.buttons[key].isEnabled(), key
        w.top_bar.buttons[key].click()
    assert started == [] and w.import_thread is not None
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)
    assert w.top_bar.buttons["import"].isEnabled() and w.top_bar.buttons["people"].isEnabled() is w.act_analyze.isEnabled()


class _Hold(QRunnable):
    def __init__(self, gate: threading.Event) -> None:
        super().__init__()
        self.gate = gate

        self.started = threading.Event()

    def run(self) -> None:
        self.started.set()
        self.gate.wait(30)


def test_mode_change_while_workers_run(qtbot, env: dict) -> None:  # noqa: F811
    """Layout changes never touch the worker / shutdown machinery: the gate stays open, workers keep running, and the
    window still closes cleanly afterwards."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    gate = threading.Event()
    hold = _Hold(gate)
    w.viewer._pool.start(hold)
    assert hold.started.wait(10)  # running, not just queued
    project = w.project
    for size, _mode in REFERENCE:
        _at(qtbot, w, size)
        assert w._gate.open and w.project is project and not w.viewer.wait_idle(0)
    gate.set()
    assert w.viewer.wait_idle(5000)
    assert w.close() is True
