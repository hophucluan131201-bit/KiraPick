"""Left panel: collapsible sections, compact filters, a people list without horizontal scrolling."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QListWidgetItem

import app.ui.main_window as mw
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


def test_sections_collapse_and_remember(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert set(w.sections) == {"folders", "filters", "people"}
    w.sections["filters"].set_collapsed(True)
    assert not w.filters.isVisible()
    w.close()
    w2 = mw.MainWindow(settings=QSettings(env["ini"], QSettings.Format.IniFormat))
    qtbot.addWidget(w2)
    w2.show()
    assert w2.sections["filters"].collapsed and not w2.filters.isVisible()


def test_folders_hidden_with_one_folder(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    assert not w.sections["folders"].isVisible()


def test_people_list_never_scrolls_sideways(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.people.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert w.people.textElideMode() == Qt.TextElideMode.ElideRight
    assert w.people.iconSize().height() == 56
    item = QListWidgetItem("Một cái tên rất rất dài của chủ thể cosplay mặc áo hồng ngồi phao  ·  12 ảnh")
    w.people.addItem(item)
    assert not w.people.horizontalScrollBar().isVisible()


def test_filters_are_compact_chips_without_their_own_scrollbar(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    assert w.filters.isWrapping() and w.filters.flow() == w.filters.Flow.LeftToRight
    assert w.filters.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_half_screen_window_keeps_the_photos_widest(qtbot, env: dict) -> None:  # noqa: F811
    """Owner, split screen (~950 px): the side panels must not squeeze the photos into one thin column."""
    w = _window(qtbot, env)
    w.resize(960, 900)
    w.fit_panels()
    left, center, right = w.splitter.sizes()
    assert center >= left and center >= right and center >= 380, (left, center, right)
