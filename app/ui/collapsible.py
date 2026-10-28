"""A titled section that folds away; its state is kept in the settings (when given)."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QSizePolicy, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    def __init__(self, title: str, body: QWidget, key: str, settings: QSettings | None,
                 parent: QWidget | None = None, *, extra: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings, self._key, self.body = settings, f"left/{key}_collapsed", body
        self.header = QToolButton()
        self.header.setObjectName("sectionHeader")
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header.setAutoRaise(True)
        self.header.toggled.connect(self.set_collapsed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)
        layout.addWidget(self.header)
        self.extra = extra
        if extra is not None:
            layout.addWidget(extra)
        layout.addWidget(body, 1)
        self.set_collapsed(settings.value(self._key, False, bool) if settings is not None else True)

    @property
    def collapsed(self) -> bool:
        return self.body.isHidden()

    def set_collapsed(self, collapsed: bool) -> None:
        self.header.blockSignals(True)
        self.header.setChecked(collapsed)
        self.header.blockSignals(False)
        self.header.setArrowType(Qt.ArrowType.RightArrow if collapsed else Qt.ArrowType.DownArrow)
        self.body.setVisible(not collapsed)
        if self.extra is not None:
            self.extra.setVisible(not collapsed)
        if self._settings is not None:
            self._settings.setValue(self._key, collapsed)
