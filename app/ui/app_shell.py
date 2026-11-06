"""Which window is on screen: the mode picker, the culling window (Chụp cá nhân) or the Media page.

Every normal start shows the picker (nothing is remembered). "Chụp cá nhân" opens the existing MainWindow unchanged;
"⇄ Đổi chế độ" in its ⚙ menu closes it the way quitting does (workers stopped, the session released) and shows the
picker again. The picker is shown BEFORE the window it replaces hides, so the application never sees "last window
closed" while switching; closing the picker, the culling window or the Media page with × quits as before.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QSettings, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from app.branding import SETTINGS_IDS
from app.ui.media_home import MediaHome
from app.ui.mode_picker import EVENT, PERSONAL, ModePicker

log = logging.getLogger(__name__)


def _personal_window(settings: QSettings) -> QWidget:
    from app.ui.main_window import MainWindow

    return MainWindow(settings)


class AppShell(QObject):
    def __init__(self, settings: QSettings | None = None,
                 personal_factory: Callable[[QSettings], QWidget] = _personal_window) -> None:
        super().__init__()
        self.settings = settings or QSettings(*SETTINGS_IDS)
        self._personal_factory = personal_factory
        self.picker = ModePicker()
        self.picker.chosen.connect(self._open)
        self.main: QWidget | None = None
        self.media: MediaHome | None = None

    # ------------------------------------------------------------------ start
    def start(self) -> None:
        saved = self.settings.value("geometry")  # the culling window's size: the picker opens where it was
        maximized = False
        if saved is None or not self.picker.restoreGeometry(saved):
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.picker.resize(min(1280, area.width()), min(780, area.height()))
        else:
            maximized = self.picker.isMaximized()
        self.picker.reset()
        if maximized:
            self.picker.showMaximized()
        else:
            self.picker.show()

    # ------------------------------------------------------------------ choose
    def _open(self, mode: str) -> None:
        log.info("mode chosen: %s", mode)
        if mode == PERSONAL:
            window = self._personal_factory(self.settings)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            enable = getattr(window, "enable_mode_switch", None)
            if enable is not None:
                enable()
            signal = getattr(window, "mode_change_ready", None)
            if signal is not None:
                signal.connect(self._back_from_personal)
            self.main = window
            window.show()
        elif mode == EVENT:
            page = MediaHome()
            page.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            page.back.connect(self._back_from_media)
            self._take_place(page, self.picker)
            self.media = page
            page.show()
        else:  # pragma: no cover - only the two cards exist
            return
        self.picker.hide()

    @staticmethod
    def _take_place(widget: QWidget, of: QWidget) -> None:
        if of.isMaximized():
            widget.setWindowState(widget.windowState() | Qt.WindowState.WindowMaximized)
        else:
            widget.setGeometry(of.geometry())

    # ------------------------------------------------------------------ back
    def _show_picker_from(self, widget: QWidget) -> None:
        self._take_place(self.picker, widget)
        self.picker.reset()
        self.picker.show()
        self.picker.raise_()
        self.picker.activateWindow()

    def _back_from_personal(self) -> None:
        """From MainWindow.closeEvent, once its session is released (the window hides right after)."""
        if self.main is None:
            return
        log.info("mode change: back to the picker")
        self._show_picker_from(self.main)
        self.main = None

    def _back_from_media(self) -> None:
        if self.media is None:
            return
        page, self.media = self.media, None
        self._show_picker_from(page)
        page.close()
