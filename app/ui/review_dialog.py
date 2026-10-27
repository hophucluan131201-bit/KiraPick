"""Review queue: is this pair of people the same person? One question at a time."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.identity import actions
from app.identity.cluster import Suggestion, merge_suggestions
from app.learning.teacher import Teacher
from app.storage.project import Project
from app.ui import theme

AVATAR = 180


def _avatar(project: Project, subject_id: int) -> tuple[QPixmap | None, int]:
    rows = actions.subjects_summary(project.conn)
    row = next((r for r in rows if r["id"] == subject_id), None)
    if row is None:
        return None, 0
    pm = QPixmap(str(project.cache_dir / row["avatar"])) if row["avatar"] else None
    return pm, int(row["photos"])


class ReviewDialog(QDialog):
    changed = Signal()

    def __init__(self, project: Project, parent: QWidget | None = None, teacher: Teacher | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cần xem lại: có phải cùng một chủ thể?")
        self.project = project
        self.teacher = teacher
        self.queue: list[Suggestion] = merge_suggestions(project.conn)
        self.index = 0
        self.decisions = 0

        layout = QVBoxLayout(self)
        self.counter = QLabel()
        self.counter.setObjectName("sectionTitle")
        layout.addWidget(self.counter)
        grid = QGridLayout()
        self.pics = [QLabel(), QLabel()]
        self.names = [QLabel(), QLabel()]
        for col in range(2):
            self.pics[col].setFixedSize(AVATAR, AVATAR)
            self.pics[col].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pics[col].setStyleSheet(f"background: {theme.PANEL}; border-radius: 8px;")
            self.names[col].setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(self.pics[col], 0, col)
            grid.addWidget(self.names[col], 1, col)
        layout.addLayout(grid)
        self.similarity = QLabel()
        self.similarity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.similarity.setWordWrap(True)
        layout.addWidget(self.similarity)

        buttons = QHBoxLayout()
        self.same = QPushButton("✓ Cùng một chủ thể")
        self.different = QPushButton("✗ Hai chủ thể khác nhau")
        self.skip = QPushButton("Bỏ qua")
        close = QPushButton("Đóng")
        self.same.clicked.connect(self.answer_same)
        self.different.clicked.connect(self.answer_different)
        self.skip.clicked.connect(self.next)
        close.clicked.connect(self.accept)
        for b in (self.same, self.different, self.skip, close):
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self._show()

    def current(self) -> Suggestion | None:
        while self.index < len(self.queue):
            s = self.queue[self.index]
            alive = {r[0] for r in self.project.conn.execute("SELECT id FROM subjects WHERE id IN (?, ?)", (s.a, s.b))}
            if alive == {s.a, s.b}:
                return s
            self.index += 1  # one of them was merged away meanwhile
        return None

    def _show(self) -> None:
        s = self.current()
        for b in (self.same, self.different, self.skip):
            b.setEnabled(s is not None)
        if s is None:
            self.counter.setText("KHÔNG CÒN GỢI Ý NÀO")
            for col in range(2):
                self.pics[col].clear()
                self.names[col].clear()
            self.similarity.setText("Mọi cặp có thể là cùng một chủ thể đã được xem.")
            return
        self.counter.setText(f"GỢI Ý {self.index + 1}/{len(self.queue)}")
        for col, sid in enumerate((s.a, s.b)):
            pm, photos = _avatar(self.project, sid)
            if pm is not None and not pm.isNull():
                self.pics[col].setPixmap(pm.scaled(AVATAR, AVATAR, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
            else:
                self.pics[col].setText("(không có ảnh mặt)")
            self.names[col].setText(f"<b>{actions.subject_label(self.project.conn, sid)}</b><br>{photos} ảnh")
        reason = f"Độ giống khuôn mặt AI: {s.similarity:.2f}" if s.similarity else "Không so được khuôn mặt"
        if s.look is not None:
            reason += f" · trang phục / dáng người: {s.look:.2f}"
        self.similarity.setText(
            f"{reason} — trang phục khá giống nhau nhưng chưa đủ chắc để tự gộp. "
            "Có thể là cùng một bộ cosplay bị tách ra; bạn quyết định."
        )

    def next(self) -> None:
        self.index += 1
        self._show()

    def answer_same(self) -> None:
        s = self.current()
        if s is None:
            return
        counts = {r["id"]: r["photos"] for r in actions.subjects_summary(self.project.conn)}
        keep, drop = (s.a, s.b) if counts.get(s.a, 0) >= counts.get(s.b, 0) else (s.b, s.a)
        with self.project.transaction() as conn:
            if self.teacher is not None:
                self.teacher.merged(conn, keep, drop)
            actions.merge_subjects(conn, keep, drop)
        self.decisions += 1
        self.changed.emit()
        self.next()

    def answer_different(self) -> None:
        s = self.current()
        if s is None:
            return
        with self.project.transaction() as conn:
            if self.teacher is not None:
                self.teacher.different(conn, s.a, s.b)
            actions.mark_different(conn, s.a, s.b)
        self.decisions += 1
        self.changed.emit()
        self.next()
