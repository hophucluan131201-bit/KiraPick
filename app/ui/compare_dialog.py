"""🎓 "Thích tấm nào hơn?": two similar photos of one subject; the answer teaches the taste model.

Never pops up by itself: the owner opens it from 🎓 AI đã học. ← / → choose, Space skips, Esc closes.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.learning.pairs import next_pair


class CompareDialog(QDialog):
    def __init__(self, parent: QWidget, subjects: dict[int, int], clips: dict, ranked: dict[int, float],
                 pixmap: Callable[[int], QPixmap | None], answer: Callable[[int, int], None]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thích tấm nào hơn?")
        self.resize(1100, 640)
        self.subjects, self.clips, self.ranked = subjects, clips, ranked
        self._pixmap, self._answer = pixmap, answer
        self.asked: set[frozenset[int]] = set()
        self.answered = 0
        self.pair: tuple[int, int] | None = None
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.left, self.right = QLabel(), QLabel()
        for label in (self.left, self.right):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumSize(320, 320)
        row = QHBoxLayout()
        row.addWidget(self.left, 1)
        row.addWidget(self.right, 1)
        buttons = QHBoxLayout()
        self.b_left = QPushButton("← Thích tấm trái")
        self.b_skip = QPushButton("Bỏ qua (Space)")
        self.b_right = QPushButton("Thích tấm phải →")
        for b in (self.b_left, self.b_skip, self.b_right):
            buttons.addWidget(b)
        self.b_left.clicked.connect(lambda: self.choose(0))
        self.b_right.clicked.connect(lambda: self.choose(1))
        self.b_skip.clicked.connect(self.skip)
        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addLayout(row, 1)
        layout.addLayout(buttons)
        for key, fn in ((Qt.Key.Key_Left, lambda: self.choose(0)), (Qt.Key.Key_Right, lambda: self.choose(1)),
                        (Qt.Key.Key_Space, self.skip)):
            QShortcut(QKeySequence(key), self, activated=fn)
        self.next()

    def next(self) -> None:
        self.pair = next_pair(self.subjects, self.clips, self.ranked, self.asked)
        if self.pair is None:
            self.info.setText(f"Đã hết cặp ảnh giống nhau để hỏi (bạn đã trả lời {self.answered} cặp). "
                              "Mỗi câu trả lời giúp app hiểu gu của bạn hơn.")
            self.left.clear()
            self.right.clear()
            for b in (self.b_left, self.b_right, self.b_skip):
                b.setEnabled(False)
            return
        self.info.setText("Hai ảnh gần giống nhau của cùng chủ thể. Bạn thích tấm nào hơn? "
                          f"(đã trả lời {self.answered} cặp)")
        for label, asset_id in ((self.left, self.pair[0]), (self.right, self.pair[1])):
            pm = self._pixmap(asset_id)
            if pm is not None and not pm.isNull():
                label.setPixmap(pm.scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
            else:
                label.setText("(chưa có ảnh xem trước)")

    def choose(self, side: int) -> None:
        if self.pair is None:
            return
        winner, loser = self.pair if side == 0 else (self.pair[1], self.pair[0])
        self._answer(winner, loser)
        self.answered += 1
        self.skip()

    def skip(self) -> None:
        if self.pair is not None:
            self.asked.add(frozenset(self.pair))
        self.next()
