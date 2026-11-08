"""⤴ Xuất ảnh of an event (MED-EXP, plan Mốc 1 M11): P photos copied into sub-folders by moment / shot size.

Nothing is copied before the user sees what will happen (photos, files, folders, problems) and presses "Sao chép".
The copy runs in a worker thread (app.ui.jobs.ExportThread): verified copies, no overwrite, a record in the event's
folder. Originals are never moved or changed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.export.copy_export import ExportError, ExportPlan
from app.export.formats import ExportFormat
from app.media import export as mx
from app.media.event import MediaEvent
from app.ui.jobs import ExportThread

LAYOUTS = [("Theo khoảnh khắc", mx.BY_MOMENT), ("Theo cỡ cảnh", mx.BY_SHOT), ("Một thư mục", mx.SINGLE)]
FORMATS = [("RAW + JPEG (mọi tệp của ảnh)", ExportFormat.RAW_JPEG), ("Chỉ RAW", ExportFormat.RAW),
           ("Chỉ JPEG", ExportFormat.JPEG)]


class MediaExportDialog(QDialog):
    def __init__(self, event: MediaEvent, parent: QWidget | None = None, *, marked: list[int] | None = None,
                 collection_id: int | None = None) -> None:
        """``marked``: the photos ticked in the grid; ``collection_id``: preselect that client list (as 3.0.0)."""
        super().__init__(parent)
        self.setWindowTitle("⤴ Xuất ảnh")
        self.media_event = event
        self.plan: ExportPlan | None = None
        self.thread: ExportThread | None = None
        self.result = None
        # Which photos, as in the 3.0.0 export: P, the ticked photos, or a client's list (📋 Khách chọn)
        self.which_box = QComboBox()
        self.which_box.addItem("Ảnh đã chọn (P)", None)
        if marked:
            self.which_box.addItem(f"Ảnh đang đánh dấu ({len(marked)})", list(marked))
        for cid, name in event.conn.execute("SELECT id, name FROM collections ORDER BY id DESC").fetchall():
            ids = [r[0] for r in event.conn.execute(
                "SELECT asset_id FROM collection_items WHERE collection_id = ? ORDER BY asset_id", (cid,))]
            self.which_box.addItem(f"Danh sách khách: {name} ({len(ids)})", ids)
            if cid == collection_id:
                self.which_box.setCurrentIndex(self.which_box.count() - 1)
        self.layout_box = QComboBox()
        for text, value in LAYOUTS:
            self.layout_box.addItem(text, value)
        self.format_box = QComboBox()
        for text, value in FORMATS:
            self.format_box.addItem(text, value)
        self.dest = QLineEdit()
        self.dest.setPlaceholderText("Thư mục nhận ảnh")
        browse = QPushButton("Chọn…")
        browse.clicked.connect(self._browse)
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.dest, 1)
        dest_row.addWidget(browse)
        form = QFormLayout()
        form.addRow("Ảnh", self.which_box)
        form.addRow("Chia thư mục", self.layout_box)
        form.addRow("Định dạng", self.format_box)
        form.addRow("Lưu vào", dest_row)
        self.summary = QLabel("Chọn thư mục nhận ảnh rồi bấm Xem trước.")
        self.summary.setWordWrap(True)
        self.preview_button = QPushButton("Xem trước")
        self.copy_button = QPushButton("Sao chép")
        self.copy_button.setEnabled(False)
        self.close_button = QPushButton("Đóng")
        self.preview_button.clicked.connect(self.preview)
        self.copy_button.clicked.connect(self.start_copy)
        self.close_button.clicked.connect(self._close)
        for w in (self.which_box, self.layout_box, self.format_box):
            w.currentIndexChanged.connect(self._invalidate)
        self.dest.textChanged.connect(self._invalidate)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for b in (self.preview_button, self.copy_button, self.close_button):
            buttons.addWidget(b)
        box = QVBoxLayout(self)
        box.addWidget(QLabel("Ảnh được SAO CHÉP: ảnh gốc không bị di chuyển hay sửa; tệp đã có ở nơi nhận không bị ghi "
                             "đè. Ảnh chưa phân tích (⏳) vẫn xuất theo P/X; ảnh P chưa có khoảnh khắc vào thư mục "
                             f"\"{mx.NO_MOMENT}\"."))
        box.addLayout(form)
        box.addWidget(self.summary)
        box.addLayout(buttons)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục nhận ảnh")
        if folder:
            self.dest.setText(folder)

    def _invalidate(self) -> None:
        self.plan = None
        self.copy_button.setEnabled(False)

    def preview(self) -> ExportPlan | None:
        text = self.dest.text().strip()
        if not text:
            self.summary.setText("Chưa chọn thư mục nhận ảnh.")
            return None
        try:
            self.plan = mx.plan(self.media_event, Path(text), self.layout_box.currentData(),
                                ExportFormat(self.format_box.currentData()), asset_ids=self.which_box.currentData())
        except ExportError as exc:
            self.summary.setText(f"Không xuất được vào thư mục này: {exc}")
            return None
        ops = self.plan.operations
        folders = sorted({op.folder or "(thư mục nhận)" for op in ops})
        what = "ảnh P" if self.which_box.currentData() is None else "ảnh"
        lines = [f"{len(self.plan.photos)} {what} → {len(ops)} tệp, {len(folders)} thư mục: "
                 + ", ".join(folders[:8]) + (" …" if len(folders) > 8 else "")]
        present = sum(1 for op in ops if op.maybe_present)
        if present:
            lines.append(f"{present} tệp có thể đã có ở nơi nhận: sẽ so nội dung, không ghi đè.")
        if self.plan.issues:
            lines.append(f"{len(self.plan.issues)} vấn đề (ví dụ: {self.plan.issues[0].detail}).")
        if not ops:
            lines.append("Không có tệp nào để sao chép (đã đánh P / đánh dấu ảnh nào chưa?).")
        self.summary.setText("\n".join(lines))
        self.copy_button.setEnabled(bool(ops))
        return self.plan

    def start_copy(self) -> ExportThread | None:
        if self.plan is None or not self.plan.operations:
            return None
        record = self.media_event.folder / mx.RECORD_DIR
        record.mkdir(parents=True, exist_ok=True)
        self.thread = ExportThread(self.plan, self.plan.options, record_dir=record)
        self.thread.progress.connect(lambda done, total: self.summary.setText(f"Đang sao chép {done}/{total}…"))
        self.thread.succeeded.connect(self._done)
        self.thread.failed.connect(lambda msg: self._done(None, msg))
        for w in (self.copy_button, self.preview_button, self.which_box, self.layout_box, self.format_box, self.dest):
            w.setEnabled(False)
        self.close_button.setText("Dừng")
        self.thread.start()
        return self.thread

    def _done(self, result, error: str | None = None) -> None:  # noqa: ANN001
        if self.thread is not None:
            self.thread.wait()
        self.thread = None
        self.result = result
        self.close_button.setText("Đóng")
        self.preview_button.setEnabled(True)
        if error:
            self.summary.setText(f"Lỗi khi sao chép: {error}")
            return
        from app.media import trial

        trial.record(self.media_event.event_id, "export", len(self.plan.photos) if self.plan is not None else 0)
        text = f"Đã sao chép {len(result.copied)} tệp."
        if result.already_present:
            text += f" {len(result.already_present)} tệp đã có sẵn (giống hệt), không chép lại."
        if result.renamed:
            text += f" {len(result.renamed)} tệp được đặt tên khác để không đè."
        if result.failed:
            text += f" {len(result.failed)} tệp lỗi."
        if result.cancelled:
            text += " Đã dừng giữa chừng."
        self.summary.setText(text)

    def _close(self) -> None:
        if self.thread is not None:
            self.thread.cancel()
            return
        self.accept()
