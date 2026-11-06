"""The mode picker shown at every normal start (docs/design/che-do-lam-viec.md).

Two cards: "Chụp cá nhân" opens the existing culling window unchanged; "Media sự kiện" opens the Media flow (a
"Beta, đang phát triển" page for now). Choosing only navigates: nothing is imported, analysed or downloaded.
Keyboard: Tab / Shift+Tab between the cards, Enter / Space opens the focused one, 1 / 2 open a card directly.
One activation per showing: a double click or a held key never opens two windows.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.branding import APP_NAME, icon_path, mode_image_path
from app.ui import theme

PERSONAL, EVENT = "personal", "event"
CARDS = (
    (PERSONAL, "Chụp cá nhân", "Gom ảnh theo chủ thể hoặc tạo hình.", ""),
    (EVENT, "Media sự kiện", "Duyệt ảnh theo diễn biến chương trình.", "Beta"),
)
SIDE_BY_SIDE_MIN_W = 760  # narrower: the cards stack
IMAGES_MIN_H = 420  # lower window: the cards keep only their name and description
STACKED_IMAGES_MIN_H = 760  # stacked cards need twice the height for their pictures
FOCUS_BORDER = 3
PICTURE_RATIO = 0.48  # height / width of the illustrations (as in the mockup)


class _Picture(QWidget):
    """The card's illustration, scaled to cover its area (cropped, never stretched), with rounded top corners."""

    def __init__(self, path: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap(path) if path else QPixmap()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(60)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(400, 200)

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()
        clip = QPainterPath()
        clip.addRoundedRect(rect.adjusted(0, 0, 0, 12), 10, 10)  # rounded on top only (the bottom is clipped)
        painter.setClipPath(clip)
        if self._pixmap.isNull():
            painter.fillRect(rect, theme.RAISED)
            return
        scaled = self._pixmap.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation)
        source = QRect((scaled.width() - rect.width()) // 2, (scaled.height() - rect.height()) // 2,
                       rect.width(), rect.height())
        painter.drawPixmap(rect, scaled, source)


class ModeCard(QFrame):
    """One clickable, focusable card."""

    activated = Signal(str)

    def __init__(self, mode: str, title: str, text: str, badge: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setObjectName("modeCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        path = mode_image_path(mode)
        self.picture = _Picture(str(path) if path else None, self)
        self.title = QLabel(title)
        font = QFont(self.title.font())
        font.setPointSizeF(font.pointSizeF() * 1.6)
        font.setBold(True)
        self.title.setFont(font)
        self.text = QLabel(text)
        self.text.setWordWrap(True)
        text_font = QFont(self.text.font())
        text_font.setPointSizeF(text_font.pointSizeF() * 1.15)
        self.text.setFont(text_font)
        self.text.setStyleSheet(f"color: {theme.MUTED};")
        self.badge = QLabel(badge)
        self.badge.setVisible(bool(badge))
        self.badge.setStyleSheet(f"color: {theme.BG}; background: {theme.STAR}; border-radius: 4px; padding: 1px 6px;"
                                 " font-weight: bold;")
        self.arrow = QLabel("→")
        arrow_font = QFont(font)
        arrow_font.setBold(False)
        self.arrow.setFont(arrow_font)
        self.arrow.setStyleSheet(f"color: {theme.ACCENT};")
        for label in (self.title, self.text, self.badge, self.arrow):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        heading = QHBoxLayout()
        heading.setSpacing(8)
        heading.addWidget(self.title)
        heading.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        heading.addStretch(1)
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addLayout(heading)
        words.addWidget(self.text)
        footer = QHBoxLayout()
        footer.setContentsMargins(18, 12, 18, 14)
        footer.addLayout(words, 1)
        footer.addWidget(self.arrow, 0, Qt.AlignmentFlag.AlignVCenter)
        box = QVBoxLayout(self)
        box.setContentsMargins(FOCUS_BORDER, FOCUS_BORDER, FOCUS_BORDER, FOCUS_BORDER)
        box.setSpacing(0)
        box.addWidget(self.picture, 1)
        box.addLayout(footer)
        self.setStyleSheet(
            f"QFrame#modeCard {{ background: {theme.PANEL}; border: {FOCUS_BORDER}px solid {theme.RAISED};"
            " border-radius: 12px; }"
            f"QFrame#modeCard:hover {{ border-color: {theme.MUTED}; }}"
            f"QFrame#modeCard:focus {{ border-color: {theme.ACCENT}; }}")

    def show_picture(self, on: bool) -> None:
        self.picture.setVisible(on)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit(self.mode)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not event.isAutoRepeat():
                self.activated.emit(self.mode)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            forward = event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down)
            self.focusNextPrevChild(forward)
            event.accept()
            return
        super().keyPressEvent(event)


class ModePicker(QWidget):
    """The window "Chọn chế độ làm việc"."""

    chosen = Signal(str)  # PERSONAL or EVENT, at most once per showing

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 300)
        self.setAutoFillBackground(True)
        self._done = False
        self.brand_row = QWidget()
        brand = QHBoxLayout(self.brand_row)
        brand.setContentsMargins(0, 0, 0, 0)
        brand.addStretch(1)
        icon = icon_path()
        if icon is not None:
            logo = QLabel()
            logo.setPixmap(QPixmap(str(icon)).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))
            brand.addWidget(logo)
        self.brand = QLabel(APP_NAME)
        brand_font = QFont(self.brand.font())
        brand_font.setPointSizeF(brand_font.pointSizeF() * 1.8)
        brand_font.setBold(True)
        self.brand.setFont(brand_font)
        brand.addWidget(self.brand)
        brand.addStretch(1)
        self.heading = QLabel("Chọn chế độ làm việc")
        heading_font = QFont(self.heading.font())
        heading_font.setPointSizeF(heading_font.pointSizeF() * 2.0)
        heading_font.setBold(True)
        self.heading.setFont(heading_font)
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards = {mode: ModeCard(mode, title, text, badge) for mode, title, text, badge in CARDS}
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.row.setSpacing(28)
        for card in self.cards.values():
            card.activated.connect(self._choose)
            self.row.addWidget(card, 1)
        self.version = QLabel(f"KiraPick {__version__}")
        self.version.setStyleSheet(f"color: {theme.MUTED};")
        self.version.setAlignment(Qt.AlignmentFlag.AlignRight)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 24, 40, 12)
        outer.setSpacing(14)
        outer.addWidget(self.brand_row)
        outer.addWidget(self.heading)
        outer.addStretch(1)
        outer.addLayout(self.row)
        outer.addStretch(1)
        outer.addWidget(self.version)
        QWidget.setTabOrder(self.cards[PERSONAL], self.cards[EVENT])  # both in this window now
        self._fit(self.size())

    # ---------------------------------------------------------------- showing
    def reset(self) -> None:
        """Ready for a new choice (shown again after a mode was left); "Chụp cá nhân" has the focus."""
        self._done = False
        self.cards[PERSONAL].setFocus(Qt.FocusReason.OtherFocusReason)

    def showEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if not self._done:
            self.cards[PERSONAL].setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        """1 / 2 open a card directly (the cards pass every other key up to here)."""
        mode = {Qt.Key.Key_1: PERSONAL, Qt.Key.Key_2: EVENT}.get(Qt.Key(event.key()))
        if mode is not None and not event.isAutoRepeat():
            self._choose(mode)
            event.accept()
            return
        super().keyPressEvent(event)

    def _choose(self, mode: str) -> None:
        if self._done or not self.isVisible():
            return
        self._done = True
        self.chosen.emit(mode)

    # ---------------------------------------------------------------- layout
    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._fit(self.size())

    def _fit(self, size: QSize) -> None:
        side_by_side = size.width() >= SIDE_BY_SIDE_MIN_W
        self.row.setDirection(QBoxLayout.Direction.LeftToRight if side_by_side else QBoxLayout.Direction.TopToBottom)
        pictures = size.height() >= (IMAGES_MIN_H if side_by_side else STACKED_IMAGES_MIN_H)
        margins = 2 * 40
        card_w = (size.width() - margins - (self.row.spacing() if side_by_side else 0)) // (2 if side_by_side else 1)
        overhead = 300 if side_by_side else 2 * 120 + 220  # brand, heading, card footers, version, spacing
        cards_high = 1 if side_by_side else 2
        picture_h = max(60, min(int(card_w * PICTURE_RATIO), (size.height() - overhead) // cards_high))
        for card in self.cards.values():
            card.show_picture(pictures)
            card.picture.setFixedHeight(picture_h)
        compact = size.height() < IMAGES_MIN_H
        self.brand_row.setVisible(not compact)  # low windows keep the heading and the two cards
        self.version.setVisible(not compact)
        self.layout().setContentsMargins(*(24, 10, 24, 6) if compact else (40, 24, 40, 12))
        self.layout().setSpacing(8 if compact else 14)
