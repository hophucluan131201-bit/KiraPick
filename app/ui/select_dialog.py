"""'⭐ Chọn ảnh': let the AI pick N good, varied photos; the user then reviews them."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.quality.score import NOT_MEASURED


class SelectDialog(QDialog):
    def __init__(self, parent: QWidget | None, *, people: int, in_view: int, view_name: str, scored: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chọn ảnh đẹp")
        layout = QVBoxLayout(self)
        intro = QLabel(
            "AI chọn những ảnh điểm kỹ thuật cao nhất (nét ở mắt, mặt rõ, đủ sáng, bố cục) và tránh "
            "chọn các ảnh gần giống nhau (cùng dáng, cùng loạt chụp liên tiếp). Ảnh được chọn xếp lên "
            "đầu, có nhãn “AI”; bạn xem lại và bấm K (giữ) / X (loại) như bình thường.\n"
            f"Chưa chấm được: {', '.join(NOT_MEASURED)} — hãy nhìn kỹ những điểm này."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        if scored == 0:
            warn = QLabel("⚠ Chưa có ảnh nào được chấm điểm. Hãy bấm 🧠 Phân tích ảnh trước.")
            warn.setWordWrap(True)
            layout.addWidget(warn)
        self.per_person = QRadioButton(f"Mỗi người N ảnh ({people} người)")
        self.in_view = QRadioButton(f"N ảnh trong {view_name} ({in_view} ảnh)")
        group = QButtonGroup(self)
        for b in (self.per_person, self.in_view):
            group.addButton(b)
            layout.addWidget(b)
        self.per_person.setEnabled(people > 0)
        (self.in_view if view_name.startswith("ảnh của") or people == 0 else self.per_person).setChecked(True)
        self.count = QSpinBox()
        self.count.setRange(1, 999)
        self.count.setValue(10)
        self.count.setPrefix("N = ")
        layout.addWidget(self.count)
        self.mark_keep = QCheckBox("Đánh dấu Giữ ✓ cho ảnh được chọn (ảnh bạn đã đánh dấu thì giữ nguyên)")
        self.mark_keep.setChecked(True)
        layout.addWidget(self.mark_keep)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Chọn ảnh")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(scored > 0)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
