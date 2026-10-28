"""Top bar: the workflow as five steps (✓ done, ◐ partly done, the next one highlighted), then search,
thumbnail size and ⚙. Each step button runs the window's existing action, so shortcuts, enabling rules and
tooltips stay in one place (the QAction)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QSlider, QToolButton, QWidget

from app.storage.workflow import STEPS, StepState
from app.ui.score_style import COLORS

STEP_LABELS = {"import": ("📂", "Nhập ảnh"), "people": ("🧠", "Nhận diện chủ thể"), "quality": ("📊", "Phân tích AI"),
               "pick": ("⭐", "Chọn ảnh"), "export": ("⤴", "Xuất ảnh")}
assert tuple(STEP_LABELS) == STEPS
CELL_MIN, CELL_MAX, CELL_DEFAULT = 140, 340, 220  # grid card size (logical px)


class TopBar(QWidget):
    step_clicked = Signal(str)

    def __init__(self, search: QLineEdit, options_button: QToolButton, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.search, self.options_button = search, options_button
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(4)
        self.buttons: dict[str, QToolButton] = {}
        self._actions: dict[str, QAction] = {}
        for key in STEPS:
            b = QToolButton()
            b.setObjectName("step")
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.clicked.connect(lambda _c=False, k=key: self.step_clicked.emit(k))
            row.addWidget(b)
            self.buttons[key] = b
        row.addStretch(1)
        search.setMaximumWidth(260)
        row.addWidget(search)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(CELL_MIN, CELL_MAX)
        self.size_slider.setValue(CELL_DEFAULT)
        self.size_slider.setFixedWidth(110)
        self.size_slider.setToolTip("Cỡ ảnh trong lưới")
        row.addWidget(self.size_slider)
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
        for key in STEPS:
            self._sync(key)

    def _sync(self, key: str) -> None:
        icon, name = STEP_LABELS[key]
        state = self._states.get(key, StepState(False, None))
        mark = "✓ " if state.done else "◐ " if state.partial else ""
        extra = f" {state.partial}" if state.partial and not self._compact else ""
        b = self.buttons[key]
        b.setText(f"{mark}{icon}" if self._compact else f"{mark}{icon} {name}{extra}")
        action = self._actions.get(key)
        tip = action.toolTip() if action is not None else name
        if key == "import":
            tip += "\nTrạng thái theo lần nhập gần nhất."
        if state.partial:
            tip += f"\nĐang dở: {state.partial}"
        b.setToolTip(f"{name}: {tip}" if self._compact else tip)
        b.setEnabled(action.isEnabled() if action is not None else True)
        is_next = key == self.next_step
        b.setStyleSheet(f"QToolButton#step {{ border: 1px solid {COLORS['accent']}; border-radius: 6px; "
                        f"font-weight: bold; }}" if is_next else "")
