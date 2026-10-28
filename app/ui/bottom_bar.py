"""Bottom bar: how many photos are Chọn / Loại / undecided, what an export would copy, the batch marking,
job progress and status messages, then the culling actions.

Counts are PHOTOS (a RAW+JPEG pair is one photo); the size is the FILES an export of the kept photos would copy
(app.storage.stats.counts, the same file selection as the export itself), estimated from the import.
The bar only shows and asks; the window does the work.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QSizePolicy, QToolButton, QWidget

from app.storage.stats import Counts
from app.ui import theme
from app.ui.score_style import COLORS

SIZE_TIP = ("Số ảnh: một cặp RAW+JPEG tính là 1 ảnh.\n"
            "Dung lượng: các file sẽ được chép khi xuất ảnh đã Chọn (RAW và — nếu bật \"Kèm JPEG\" — file JPEG kèm).\n"
            "Đây là con số ước tính lấy lúc nhập ảnh: khi xuất có thể ít hơn nếu file đã bị xoá khỏi ổ hoặc đã có sẵn ở "
            "thư mục đích, và có thể nhiều hơn nếu một file JPEG được Chọn riêng từ trước khi ghép cặp.")


def size_text(n: int) -> str:
    """Vietnamese decimal comma: 2,5 GB / 41,2 MB."""
    value, unit = (n / 1e9, "GB") if n >= 1e9 else (n / 1e6, "MB")
    return (f"{value:.1f}".replace(".", ",") if value else "0") + f" {unit}"


class BottomBar(QWidget):
    keep = Signal()
    reject = Signal()
    clear = Signal()
    rating = Signal(int)
    rotate = Signal()
    exif = Signal()
    export = Signal()
    export_client = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(8)
        self.kept = QLabel("Đã chọn 0 ảnh")
        self.kept.setStyleSheet(f"color: {COLORS['good']}; font-weight: bold;")
        self.kept.setToolTip(SIZE_TIP)
        self.rejected = QLabel("Đã loại 0")
        self.rejected.setStyleSheet(f"color: {COLORS['poor']};")
        self.undecided = QLabel("Chưa chọn 0")
        self.undecided.setStyleSheet(f"color: {theme.MUTED};")
        self.marking = QLabel()
        self.marking.setStyleSheet(f"color: {COLORS['accent']};")
        self.marking.setHidden(True)
        self.status = QLabel("Sẵn sàng")
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # long text is cut
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.pause_button = QPushButton("Tạm dừng")
        self.pause_button.setVisible(False)
        for w in (self.kept, self.rejected, self.undecided, self.marking):
            row.addWidget(w)
        row.addWidget(self.status, 1)
        row.addWidget(self.progress_bar)
        row.addWidget(self.pause_button)

        def button(text: str, tip: str, signal: Signal) -> QPushButton:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(signal)
            row.addWidget(b)
            return b

        self.keep_button = button("✓ Chọn", "Chọn (P hoặc K)", self.keep)
        self.keep_button.setStyleSheet(f"color: {COLORS['good']};")
        self.reject_button = button("✕ Loại", "Loại (X)", self.reject)
        self.reject_button.setStyleSheet(f"color: {COLORS['poor']};")
        self.clear_button = button("Bỏ chọn", "Bỏ Chọn / Loại (U)", self.clear)
        self.star_buttons: list[QPushButton] = []
        for n in range(1, 6):
            b = QPushButton("★")
            b.setFlat(True)
            b.setFixedWidth(22)
            b.setToolTip(f"{n} sao (phím {n})")
            b.setStyleSheet(f"color: {theme.STAR};")
            b.clicked.connect(lambda _c=False, n=n: self.rating.emit(n))
            row.addWidget(b)
            self.star_buttons.append(b)
        self.rotate_button = button("⟳ Xoay xem", "Xoay ảnh 90° để xem (file gốc không đổi)", self.rotate)
        self.exif_button = button("Xem EXIF", "Mở thông số EXIF của ảnh", self.exif)
        self.more_button = QToolButton()
        self.more_button.setText("⋯")
        self.more_button.setToolTip("Thêm thao tác")
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more = QMenu(self)
        for n in range(1, 6):
            more.addAction(QAction("★" * n, self, triggered=lambda _c=False, n=n: self.rating.emit(n)))
        more.addAction(QAction("⟳ Xoay xem", self, triggered=self.rotate))
        more.addAction(QAction("Xem EXIF", self, triggered=self.exif))
        self.more_button.setMenu(more)
        row.addWidget(self.more_button)
        self.export_button = QToolButton()
        self.export_button.setText("⤴ Xuất bản sao")
        self.export_button.setToolTip("Sao chép ảnh đã Chọn sang thư mục khác (Ctrl+E); ảnh gốc không đổi")
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.export_button.setStyleSheet(f"QToolButton {{ background: {COLORS['accent']}; color: #ffffff; "
                                         f"font-weight: bold; padding: 5px 12px; }}")
        self.export_button.clicked.connect(self.export)
        menu = QMenu(self)
        menu.addAction(QAction("Xuất theo danh sách khách…", self, triggered=self.export_client))
        self.export_button.setMenu(menu)
        row.addWidget(self.export_button)
        self._counts: Counts | None = None
        self._include_pairs = True
        self._compact = False
        self.set_compact(False)

    # ------------------------------------------------------------------ API
    def set_counts(self, c: Counts, include_pairs: bool, marked: int) -> None:
        self._counts, self._include_pairs = c, include_pairs
        self.marking.setText(f"Đang đánh dấu {marked} ảnh — phím tắt áp dụng cho cả {marked}")
        self.marking.setHidden(marked < 2)
        self._render()

    def set_compact(self, on: bool) -> None:
        """Narrow windows: short counts; ★, Xoay xem and EXIF move into "⋯"; Chọn / Loại / Xuất always stay."""
        self._compact = on
        for b in (*self.star_buttons, self.rotate_button, self.exif_button, self.clear_button):
            b.setVisible(not on)
        self.more_button.setVisible(on)
        self.rejected.setVisible(not on)
        self.undecided.setVisible(not on)
        self._render()

    def message(self, text: str) -> None:
        self.status.setText(text)

    def progress(self, done: int, total: int, pausable: bool) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.pause_button.setVisible(pausable)

    def progress_done(self) -> None:
        self.progress_bar.setVisible(False)
        self.pause_button.setVisible(False)

    def _render(self) -> None:
        c = self._counts
        if c is None:
            return
        if self._compact:
            self.kept.setText(f"✓{c.keep} ✗{c.reject} ·{c.undecided}")
            return
        pairs = ", gồm JPEG kèm" if self._include_pairs else ""
        self.kept.setText(f"Đã chọn {c.keep} ảnh ({size_text(c.keep_bytes)}{pairs})")
        self.rejected.setText(f"Đã loại {c.reject}")
        self.undecided.setText(f"Chưa chọn {c.undecided}")

