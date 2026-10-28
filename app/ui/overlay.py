"""Docked or floating without reparenting: a panel that is a child of one host widget for its whole life.

Docked, the panel covers an empty "slot" widget that sits in a layout or splitter (so the splitter still sizes it,
and the user can drag its handle); floating, it slides over one side of the host above a dimming scrim (a drawer for
the sidebar, a sheet for the details). Moving between the two never calls ``setParent`` — state such as scroll
positions, open sections, the current tab or a text field's cursor stays exactly as it was.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

SCRIM = QColor(0, 0, 0, 110)


class Scrim(QWidget):
    """Darkens the host behind a floating panel; a click on it closes the panel."""

    clicked = Signal()

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self.setObjectName("scrim")
        self.hide()

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt override
        QPainter(self).fillRect(self.rect(), SCRIM)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        self.clicked.emit()
        event.accept()  # type: ignore[attr-defined]


class Placement(QObject):
    """Keeps ``panel`` (a child of ``host``) over ``slot`` when docked, or as a sheet on ``side`` of the host."""

    closed = Signal()  # a floating panel was closed by the user (scrim click, or Escape via the window)

    def __init__(self, host: QWidget, panel: QWidget, slot: QWidget, *, side: Qt.Edge,
                 sheet_width: Callable[[int], int], scrim: Scrim | None = None) -> None:
        super().__init__(host)
        if panel.parentWidget() is not host:
            raise ValueError("the panel must be a child of the host")
        self.host, self.panel, self.slot, self.side, self.sheet_width = host, panel, slot, side, sheet_width
        self.docked = True
        self.is_open = False  # floating only: shown over the host
        self._return_focus: QWidget | None = None
        self.scrim = scrim or Scrim(host)  # may be shared by several placements of one host
        self.scrim.clicked.connect(self.close)
        for w in (host, slot):
            w.installEventFilter(self)

    # ------------------------------------------------------------------ API
    def dock(self) -> None:
        self.docked, self.is_open = True, False
        self.sync()

    def float(self) -> None:
        self.docked = False
        self.sync()

    def open(self) -> None:
        """Floating: show the panel over the host; focus moves into it and comes back on close."""
        if self.docked:
            return
        self.is_open = True
        focus = QApplication.focusWidget()
        self._return_focus = focus if focus is not None and not self.panel.isAncestorOf(focus) else None
        self.sync()
        self.panel.setFocus(Qt.FocusReason.PopupFocusReason)

    def close(self) -> None:
        if self.docked or not self.is_open:
            return
        self.is_open = False
        self.sync()
        if self._return_focus is not None:
            self._return_focus.setFocus(Qt.FocusReason.PopupFocusReason)
        self._return_focus = None
        self.closed.emit()

    def sync(self) -> None:
        if self.docked:
            shown = self.slot.isVisibleTo(self.host)
            if shown:
                self.panel.setGeometry(QRect(self.slot.mapTo(self.host, QPoint(0, 0)), self.slot.size()))
                self.panel.stackUnder(self.scrim)  # above the splitter, below anything floating
            self.panel.setVisible(shown)
            return
        if not self.is_open:
            self.panel.hide()
            if not any(p.is_open for p in self.host.findChildren(Placement)):
                self.scrim.hide()
            return
        area = self.host.rect()
        width = min(area.width(), max(self.panel.minimumWidth(), self.sheet_width(area.width())))
        x = area.right() - width + 1 if self.side == Qt.Edge.RightEdge else 0
        self.scrim.setGeometry(area)
        self.scrim.show()
        self.scrim.raise_()
        self.panel.setGeometry(QRect(x, 0, width, area.height()))
        self.panel.show()
        self.panel.raise_()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide):
            self.sync()
        return False
