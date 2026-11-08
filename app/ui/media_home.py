"""Media sự kiện: the list of events (create / open / delete); an open event shows in its own window
(app.ui.media_event_window.EventWindow, the Chụp cá nhân 3.0.0 window).

Each event has its own folder and database under %LOCALAPPDATA%\\KiraPick\\media\\ (app.media.event); deleting an
event removes only that folder, never a photo. ⟵ Quay lại chọn chế độ closes the open event first.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.branding import APP_NAME, app_settings
from app.media import event as ev
from app.ui import theme

STATUS_TEXT = ("Mỗi sự kiện có dữ liệu riêng: P/X, nhãn và khoảnh khắc không lẫn với Chụp cá nhân, kể cả khi cùng một "
               "thư mục ảnh. Xoá sự kiện chỉ xoá dữ liệu của KiraPick, không bao giờ xoá ảnh. Nhãn AI là "
               "(thử nghiệm) cho tới khi được chấm trên ảnh thật.")


class MediaHome(QWidget):
    back = Signal()

    def __init__(self, parent: QWidget | None = None, *, root: Path | None = None, analysis_runner=None,  # noqa: ANN001
                 settings=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.root = root
        self._settings = settings
        self.event_window = None
        self._analysis_runner = analysis_runner
        self.setWindowTitle(f"{APP_NAME} — Media sự kiện")
        self.setMinimumSize(720, 480)
        self.setAutoFillBackground(True)
        self.view = None

        title = QLabel("Media sự kiện")
        font = QFont(title.font())
        font.setPointSizeF(font.pointSizeF() * 2.0)
        font.setBold(True)
        title.setFont(font)
        badge = QLabel("Beta")
        badge.setStyleSheet(f"color: {theme.BG}; background: {theme.STAR}; border-radius: 4px; padding: 2px 8px;"
                            " font-weight: bold;")
        heading = QHBoxLayout()
        heading.addWidget(title)
        heading.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        heading.addStretch(1)
        self.status = QLabel(STATUS_TEXT)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.TEXT};")
        self.events = QListWidget()
        self.events.itemDoubleClicked.connect(lambda *_: self.open_selected())
        self.new_button = QPushButton("＋ Sự kiện mới")
        self.open_button = QPushButton("Mở")
        self.delete_button = QPushButton("Xoá sự kiện…")
        self.back_button = QPushButton("⟵ Quay lại chọn chế độ")
        self.new_button.clicked.connect(lambda: self.create())
        self.open_button.clicked.connect(self.open_selected)
        self.delete_button.clicked.connect(lambda: self.delete_selected())
        self.back_button.clicked.connect(self._back)
        row = QHBoxLayout()
        for w in (self.new_button, self.open_button, self.delete_button):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.back_button)
        version = QLabel(f"KiraPick {__version__}")
        version.setStyleSheet(f"color: {theme.MUTED};")

        self.list_page = QWidget()
        box = QVBoxLayout(self.list_page)
        box.setContentsMargins(40, 28, 40, 16)
        box.setSpacing(12)
        box.addLayout(heading)
        box.addWidget(self.status)
        box.addWidget(self.events, 1)
        box.addLayout(row)
        box.addWidget(version, 0, Qt.AlignmentFlag.AlignRight)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.list_page)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.pages)
        self._left = False
        self.reload()

    # ------------------------------------------------------------------ list
    def reload(self) -> None:
        self.events.clear()
        for info in ev.list_events(self.root):
            item = QListWidgetItem(f"{info.name}    ·    tạo {info.created_at[:10]}")
            item.setData(Qt.ItemDataRole.UserRole, info.id)
            self.events.addItem(item)
        if self.events.count():
            self.events.setCurrentRow(0)
        has = self.events.count() > 0
        self.open_button.setEnabled(has)
        self.delete_button.setEnabled(has)

    def selected_id(self) -> str | None:
        item = self.events.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def create(self, name: str | None = None) -> ev.MediaEvent | None:
        if name is None:
            name, ok = QInputDialog.getText(self, "Sự kiện mới", "Tên sự kiện:")
            if not ok:
                return None
        try:
            event = ev.create_event(name, self.root)
        except ev.EventError as exc:
            QMessageBox.warning(self, "Sự kiện mới", str(exc))
            return None
        self.reload()
        self.show_event(event)
        return event

    def open_selected(self) -> None:
        event_id = self.selected_id()
        if event_id is None:
            return
        try:
            event = ev.open_event(event_id, self.root)
        except Exception as exc:  # noqa: BLE001 - a newer / damaged event: say so, keep the list
            QMessageBox.warning(self, "Mở sự kiện", f"Không mở được sự kiện: {exc}")
            return
        self.show_event(event)

    def delete_selected(self, confirm: bool = True) -> bool:
        event_id = self.selected_id()
        if event_id is None:
            return False
        name = self.events.currentItem().text().split("    ·")[0]
        if confirm and QMessageBox.question(
                self, "Xoá sự kiện",
                f"Xoá sự kiện \"{name}\"?\n\nChỉ xoá dữ liệu của KiraPick (P/X, nhãn, khoảnh khắc, ảnh thu nhỏ). "
                "Ảnh gốc trong thư mục của bạn không bị xoá.") != QMessageBox.StandardButton.Yes:
            return False
        ev.delete_event(event_id, self.root)
        self.reload()
        return True

    # ------------------------------------------------------------------ event window
    def show_event(self, event: ev.MediaEvent) -> None:
        """Open the event in its window (the Chụp cá nhân 3.0.0 window on the event); this list comes back when the
        user leaves the event (⟵ Danh sách sự kiện). Closing the event window with × closes the app, as in 3.0.0."""
        from app.ui.media_event_window import EventWindow

        self.close_event()
        settings = self._settings if self._settings is not None else app_settings()
        window = EventWindow(event, settings, analysis_runner=self._analysis_runner)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.mode_change_ready.connect(self._event_left)
        if self.isMaximized():
            window.setWindowState(window.windowState() | Qt.WindowState.WindowMaximized)
        elif self.isVisible():
            window._maximize_on_show = False
            window.setGeometry(self.geometry())
        self.event_window = window
        self.view = window  # (tests and older callers)
        window.show()
        self.hide()

    def _event_left(self) -> None:
        """⟵ Danh sách sự kiện: the event window released the event and is closing; the list shows again."""
        window, self.event_window, self.view = self.event_window, None, None
        if window is not None:
            self.setGeometry(window.geometry())
        self.pages.setCurrentWidget(self.list_page)
        self.setWindowTitle(f"{APP_NAME} — Media sự kiện")
        self.reload()
        self.show()
        self.raise_()
        self.activateWindow()

    def close_event(self) -> None:
        """Close the open event window, if any (its own closeEvent releases the event)."""
        window = getattr(self, "event_window", None)
        if window is not None:
            window._switching_mode = True  # leaving the event, not quitting the app
            window.close()
        self.event_window = self.view = None
        self.pages.setCurrentWidget(self.list_page)
        self.setWindowTitle(f"{APP_NAME} — Media sự kiện")

    # ------------------------------------------------------------------ Qt
    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._left = False
        if self.view is None:
            self.back_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key.Key_Escape and not event.isAutoRepeat() and self.view is None:
            self._back()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        if self.event_window is None:
            self.close_event()
        super().closeEvent(event)

    def _back(self) -> None:
        if self._left or not self.isVisible():
            return
        self._left = True
        self.close_event()
        self.back.emit()
