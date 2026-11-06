"""Media sự kiện: the start of the Media flow. Until its own specification is approved this page only says so and
leads back to the mode picker (MED-01). Nothing is imported, analysed or written here."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app import __version__
from app.branding import APP_NAME
from app.ui import theme

STATUS_TEXT = ("Chế độ Media sự kiện đang được phát triển (Beta). Khi hoàn thiện, bạn sẽ duyệt ảnh theo từng khoảnh "
               "khắc của chương trình: check-in, sân khấu, trao giải… và chọn ảnh bàn giao cho từng phần.\n\n"
               "Bản này chưa nhập hay phân tích ảnh ở chế độ Media. Để lọc ảnh ngay, quay lại và chọn "
               "\"Chụp cá nhân\".")


class MediaHome(QWidget):
    back = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Media sự kiện")
        self.setMinimumSize(560, 300)
        self.setAutoFillBackground(True)
        title = QLabel("Media sự kiện")
        font = QFont(title.font())
        font.setPointSizeF(font.pointSizeF() * 2.0)
        font.setBold(True)
        title.setFont(font)
        badge = QLabel("Beta · đang phát triển")
        badge.setStyleSheet(f"color: {theme.BG}; background: {theme.STAR}; border-radius: 4px; padding: 2px 8px;"
                            " font-weight: bold;")
        heading = QHBoxLayout()
        heading.addWidget(title)
        heading.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        heading.addStretch(1)
        self.status = QLabel(STATUS_TEXT)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.TEXT};")
        self.back_button = QPushButton("⟵ Quay lại chọn chế độ")
        self.back_button.setDefault(True)
        self.back_button.setAutoDefault(True)
        self.back_button.clicked.connect(self._back)
        version = QLabel(f"KiraPick {__version__}")
        version.setStyleSheet(f"color: {theme.MUTED};")
        box = QVBoxLayout(self)
        box.setContentsMargins(40, 28, 40, 16)
        box.setSpacing(16)
        box.addLayout(heading)
        box.addWidget(self.status)
        row = QHBoxLayout()
        row.addWidget(self.back_button)
        row.addStretch(1)
        box.addLayout(row)
        box.addStretch(1)
        box.addWidget(version, 0, Qt.AlignmentFlag.AlignRight)
        self._left = False

    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._left = False
        self.back_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key.Key_Escape and not event.isAutoRepeat():
            self._back()
            event.accept()
            return
        super().keyPressEvent(event)

    def _back(self) -> None:
        if self._left or not self.isVisible():
            return
        self._left = True
        self.back.emit()
