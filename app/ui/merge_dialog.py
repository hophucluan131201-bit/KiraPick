"""Gộp chủ thể (LOOK merge): choose the subject to keep, see the photos, the warnings, then merge — undoable."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.identity import actions

PREVIEW_PER_SUBJECT = 8
THUMB = 64


@dataclass(frozen=True, slots=True)
class MergeChoice:
    keep: int
    others: list[int]
    name: str | None  # None = keep the current name
    unmark_conflicts: bool


def _co_photos(conn: sqlite3.Connection, ids: list[int]) -> int:
    """Photos in which two or more of these subjects appear (one person is kept per photo after merging)."""
    marks = ",".join("?" * len(ids))
    return conn.execute(f"""SELECT COUNT(*) FROM (SELECT asset_id FROM occurrences WHERE subject_id IN ({marks})
                            GROUP BY asset_id HAVING COUNT(DISTINCT subject_id) > 1)""", ids).fetchone()[0]


class MergeDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, cache_dir: Path, ids: list[int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gộp chủ thể")
        self.conn, self.ids = conn, list(ids)
        summary = {r["id"]: r for r in actions.subjects_summary(conn)}
        self.photos = {i: (summary[i]["photos"] if i in summary else 0) for i in self.ids}
        self.names = {i: (summary[i]["display_name"] if i in summary else None) for i in self.ids}
        default = max(self.ids, key=lambda i: (self.names[i] is not None, self.photos[i]))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Gộp {len(self.ids)} chủ thể thành một</b> — cùng một người, cùng bộ đồ."))
        layout.addWidget(QLabel("Giữ lại:"))
        self.group = QButtonGroup(self)
        self.radios: dict[int, QRadioButton] = {}
        for i in self.ids:
            r = QRadioButton(f"{actions.subject_label(conn, i)} — {self.photos[i]} ảnh")
            self.group.addButton(r)
            self.radios[i] = r
            layout.addWidget(r)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Tên sau khi gộp (để trống = giữ số)")
        row = QHBoxLayout()
        row.addWidget(QLabel("Tên:"))
        row.addWidget(self.name, 1)
        layout.addLayout(row)
        layout.addWidget(self._preview(cache_dir))
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        layout.addWidget(self.warnings)
        self.conflicts = [(a, b) for a, b in combinations(self.ids, 2) if actions.are_different(conn, a, b)]
        self.unmark = QCheckBox("Bỏ dấu “khác nhau” giữa các chủ thể này rồi gộp")
        self.unmark.setVisible(bool(self.conflicts))
        self.unmark.toggled.connect(self._update)
        layout.addWidget(self.unmark)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setText(f"Gộp {sum(self.photos.values())} ảnh")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Huỷ")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.radios[default].setChecked(True)
        self.group.buttonToggled.connect(lambda *_: self._on_target())
        self._on_target()

    # ------------------------------------------------------------ preview
    def _preview(self, cache_dir: Path) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        for i in self.ids:
            row = QHBoxLayout()
            row.addWidget(QLabel(actions.subject_label(self.conn, i)))
            crops = [r[0] for r in self.conn.execute(
                """SELECT crop_file FROM occurrences WHERE subject_id = ? AND crop_file IS NOT NULL
                   ORDER BY face_score DESC, id LIMIT ?""", (i, PREVIEW_PER_SUBJECT))]
            for crop in crops:
                pic = QLabel()
                pix = QPixmap(str(cache_dir / crop))
                if not pix.isNull():
                    pic.setPixmap(pix.scaled(THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
                    row.addWidget(pic)
            more = self.photos[i] - len(crops)
            if more > 0:
                row.addWidget(QLabel(f"+{more}"))
            row.addStretch(1)
            col.addLayout(row)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(box)
        area.setMinimumHeight(min(80 * len(self.ids), 320))
        return area

    # ------------------------------------------------------------ state
    @property
    def keep(self) -> int:
        return next(i for i, r in self.radios.items() if r.isChecked())

    def _on_target(self) -> None:
        keep = self.keep
        name = self.names[keep] or next((self.names[i] for i in self.ids if self.names[i]), None) or ""
        self.name.setText(name)
        self._update()

    def _update(self) -> None:
        keep = self.keep
        others = [i for i in self.ids if i != keep]
        lines = []
        co = _co_photos(self.conn, self.ids)
        if co:
            lines.append(f"⚠ {co} ảnh có từ hai chủ thể này trở lên: sau khi gộp, mỗi ảnh chỉ giữ người nổi bật hơn.")
        if self.conflicts:
            pairs = ", ".join(f"{actions.subject_label(self.conn, a)} – {actions.subject_label(self.conn, b)}"
                              for a, b in self.conflicts)
            lines.append(f"⛔ Bạn đã đánh dấu là người khác nhau: {pairs}. Muốn gộp, hãy tick ô bên dưới.")
        marks = ",".join("?" * len(others))
        if others and self.conn.execute(f"SELECT 1 FROM picks WHERE subject_id IN ({marks}) LIMIT 1",
                                        others).fetchone():
            lines.append("ⓘ Kết quả ⭐ Chọn ảnh cũ sẽ được đánh dấu “cần chọn lại”.")
        lines.append("✓ Chọn/Loại, sao và yêu thích của các ảnh không thay đổi. Có thể hoàn tác (Ctrl+Z).")
        self.warnings.setText("\n".join(lines))
        self.ok.setEnabled(not self.conflicts or self.unmark.isChecked())

    def summary_text(self) -> str:
        """Everything the dialog tells the user (for tests and accessibility)."""
        return "\n".join([self.ok.text(), *(r.text() for r in self.radios.values()), self.warnings.text()])

    def choice(self) -> MergeChoice:
        keep = self.keep
        typed = self.name.text().strip()
        current = self.names[keep] or ""
        return MergeChoice(keep, [i for i in self.ids if i != keep], typed if typed != current else None,
                           self.unmark.isChecked())
