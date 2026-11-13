"""Top bar: the workflow as five steps (✓ done, ◐ partly done, the next one filled in the accent colour), then
search, thumbnail size, Chỉnh sửa and Tuỳ chọn. Each step button runs the window's existing action, so shortcuts, enabling rules and
tooltips stay in one place (the QAction)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QSlider, QToolButton, QWidget

from app.storage.workflow import STEPS, StepState
from app.ui import icons, theme

# (Lucide icon, name); app.ui.icons
STEP_LABELS = {"import": ("folder-input", "Nhập ảnh"), "people": ("scan-face", "Nhận diện chủ thể"),
               "quality": ("gauge", "Phân tích AI"), "pick": ("sparkles", "AI gợi ý"), "export": ("folder-output", "Xuất ảnh")}
NEXT_STYLE = (f"QToolButton#step {{ background: {theme.ACCENT}; color: #ffffff; border: 1px solid {theme.ACCENT}; "
              f"border-radius: 6px; font-weight: bold; padding: 5px 12px; }} "
              f"QToolButton#step:hover {{ background: #6aa1ff; }} "
              f"QToolButton#step:focus {{ border: 2px solid #ffffff; }}")
assert tuple(STEP_LABELS) == STEPS
CELL_MIN, CELL_MAX, CELL_DEFAULT = 140, 340, 220  # grid card size (logical px)


class TopBar(QWidget):
    step_clicked = Signal(str)

    def __init__(self, search: QLineEdit, options_button: QToolButton, parent: QWidget | None = None,
                 edit_button: QToolButton | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.search, self.options_button, self.edit_button = search, options_button, edit_button
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(4)
        self.buttons: dict[str, QToolButton] = {}
        self._actions: dict[str, QAction] = {}
        self.step_labels = dict(STEP_LABELS)
        for key in STEPS:
            b = QToolButton()
            b.setObjectName("step")
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.clicked.connect(lambda _c=False, k=key: self.step_clicked.emit(k))
            row.addWidget(b)
            self.buttons[key] = b
        row.addStretch(1)
        search.setMaximumWidth(260)
        search.setMinimumWidth(180)  # the hint "Tìm tên file (Ctrl+F)" fits (UX-1: it was cut at 125 px)
        row.addWidget(search)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(CELL_MIN, CELL_MAX)
        self.size_slider.setValue(CELL_DEFAULT)
        self.size_slider.setFixedWidth(110)
        self.size_slider.setToolTip("Cỡ ảnh trong lưới")
        row.addWidget(self.size_slider)
        if edit_button is not None:  # "Chỉnh sửa" menu (Hoàn tác …)
            row.addWidget(edit_button)
        row.addWidget(options_button)
        self.next_step: str | None = "import"
        self._states: dict[str, StepState] = {k: StepState(False, None) for k in STEPS}
        self._compact = False
        self.set_compact(False)

    def bind(self, key: str, action: QAction) -> None:
        """The step runs this action and follows its enabled state and tooltip."""
        self._actions[key] = action
        self.step_clicked.connect(lambda k, key=key, a=action: a.trigger() if k == key and a.isEnabled() else None)
        action.changed.connect(lambda key=key: self._sync(key))
        self._sync(key)

    def set_states(self, states: dict[str, StepState]) -> None:
        """✓ / ◐ marks; whether a step can run (e.g. not while a job runs) comes from its bound QAction."""
        self._states = dict(states)
        self.next_step = next((k for k in STEPS if not states[k].done), None)
        for key in STEPS:
            self._sync(key)

    def set_compact(self, on: bool) -> None:
        """Narrow or low windows: icons only (names in tooltips) and a lower bar."""
        self._compact = on
        self.setFixedHeight(36 if on else 48)
        for b in (self.edit_button, self.options_button):  # Chỉnh sửa / Tuỳ chọn: the icon only, the name in the tooltip
            if b is not None:
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if on
                                     else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                b.setAccessibleName(b.text())
        for key in STEPS:
            self._sync(key)

    def _sync(self, key: str) -> None:
        icon, name = self.step_labels[key]
        state = self._states.get(key, StepState(False, None))
        mark = "✓ " if state.done else "◐ " if state.partial else ""
        extra = f" {state.partial}" if state.partial and not self._compact else ""
        b = self.buttons[key]
        is_next = key == self.next_step
        b.setIcon(icons.icon(icon, "#ffffff" if is_next else None))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if self._compact and not mark
                             else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setText(mark.strip() if self._compact else f"{mark}{name}{extra}")
        b.setAccessibleName(name)
        action = self._actions.get(key)
        tip = action.toolTip() if action is not None else name
        if key == "import":
            tip += "\nTrạng thái theo lần nhập gần nhất."
        if state.partial:
            tip += f"\nĐang dở: {state.partial}"
        b.setToolTip(f"{name}: {tip}" if self._compact else tip)
        b.setEnabled(action.isEnabled() if action is not None else True)
        # the next step is filled in the accent colour with a white icon (UX-2); with the keyboard focus a white
        # border shows on it (UX-1)
        b.setStyleSheet(NEXT_STYLE if is_next else "")
