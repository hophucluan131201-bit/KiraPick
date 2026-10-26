"""Export dialog: choose what to copy, preview the exact file names, confirm, copy."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.export.copy_export import (
    ExportError,
    ExportPlan,
    ExportResult,
    Selection,
    free_space,
    plan_export,
    select_assets,
)
from app.selection.client_list import list_collections
from app.storage.project import Project
from app.ui import theme
from app.ui.jobs import ExportThread

_PREVIEW_ROWS = 300


def _gb(n: int) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


class ExportDialog(QDialog):
    def __init__(self, project: Project, selected_ids: list[int], parent: QWidget | None = None,
                 default_destination: Path | None = None, collection_id: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Xuất ảnh đã chọn (sao chép)")
        self.resize(820, 620)
        self.project = project
        self.selected_ids = selected_ids
        self.plan: ExportPlan | None = None
        self.result: ExportResult | None = None
        self._thread: ExportThread | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ảnh gốc <b>không bao giờ bị thay đổi</b>: ứng dụng chỉ sao chép sang thư mục bạn chọn."))

        self.mode = QButtonGroup(self)
        self.radios: dict[Selection, QRadioButton] = {}
        row = QHBoxLayout()
        for sel, text in ((Selection.KEEP, "Ảnh đã Giữ (K)"), (Selection.FAVORITE, "Ảnh Yêu thích (F)"),
                          (Selection.RATED, "Ảnh có từ"), (Selection.IDS, "Ảnh đang chọn"),
                          (Selection.COLLECTION, "Danh sách khách:")):
            rb = QRadioButton(text)
            self.mode.addButton(rb)
            self.radios[sel] = rb
            row.addWidget(rb)
            if sel is Selection.RATED:
                self.min_rating = QSpinBox()
                self.min_rating.setRange(1, 5)
                self.min_rating.setValue(3)
                self.min_rating.setSuffix(" sao")
                row.addWidget(self.min_rating)
            if sel is Selection.COLLECTION:
                self.collection = QComboBox()
                for c in list_collections(project.conn):
                    self.collection.addItem(f"{c['name']} ({c['n']} ảnh)", c["id"])
                row.addWidget(self.collection)
        row.addStretch(1)
        layout.addLayout(row)
        self.radios[Selection.KEEP].setChecked(True)

        self.include_pairs = QCheckBox("Kèm file JPEG của cặp RAW+JPEG")
        self.include_pairs.setChecked(True)
        self.keep_folders = QCheckBox("Giữ cấu trúc thư mục con")
        opts = QHBoxLayout()
        opts.addWidget(self.include_pairs)
        opts.addWidget(self.keep_folders)
        opts.addStretch(1)
        layout.addLayout(opts)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Thư mục đích:"))
        self.dest = QLineEdit(str(default_destination) if default_destination else "")
        self.dest.setPlaceholderText("Chọn thư mục để chép ảnh vào…")
        browse = QPushButton("Chọn…")
        browse.clicked.connect(self._browse)
        dest_row.addWidget(self.dest, 1)
        dest_row.addWidget(browse)
        layout.addLayout(dest_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Ảnh gốc", "Sẽ chép thành"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.buttons = QDialogButtonBox()
        self.copy_button = self.buttons.addButton("Sao chép", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton("Đóng", QDialogButtonBox.ButtonRole.RejectRole)
        self.copy_button.clicked.connect(self._confirm_and_copy)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        for rb in self.radios.values():
            rb.toggled.connect(self.refresh)
        for widget in (self.include_pairs, self.keep_folders):
            widget.toggled.connect(self.refresh)
        self.min_rating.valueChanged.connect(self.refresh)
        self.collection.currentIndexChanged.connect(self.refresh)
        if not self.collection.count():
            self.radios[Selection.COLLECTION].setEnabled(False)
            self.collection.setEnabled(False)
        self.dest.editingFinished.connect(self.refresh)
        if not selected_ids:
            self.radios[Selection.IDS].setEnabled(False)
        if collection_id is not None and self.collection.findData(collection_id) >= 0:
            self.collection.setCurrentIndex(self.collection.findData(collection_id))
            self.radios[Selection.COLLECTION].setChecked(True)
        self.refresh()

    def _selection(self) -> Selection:
        return next(sel for sel, rb in self.radios.items() if rb.isChecked())

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục để chép ảnh vào", self.dest.text())
        if folder:
            self.dest.setText(folder)
            self.refresh()

    def refresh(self) -> None:
        self.plan = None
        self.table.setRowCount(0)
        ids = select_assets(self.project, self._selection(), min_rating=self.min_rating.value(), ids=self.selected_ids,
                            collection_id=self.collection.currentData())
        dest_text = self.dest.text().strip()
        if not ids:
            self._set_summary("Không có ảnh nào khớp lựa chọn này.", error=True)
            return
        if not dest_text:
            self._set_summary(f"{len(ids)} ảnh được chọn. Hãy chọn thư mục đích.", error=False, ready=False)
            return
        try:
            plan = plan_export(self.project, ids, Path(dest_text), include_pairs=self.include_pairs.isChecked(),
                               keep_folders=self.keep_folders.isChecked())
        except ExportError as exc:
            self._set_summary(f"Không xuất được: {exc}", error=True)
            return
        self.plan = plan
        for item in plan.items[:_PREVIEW_ROWS]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(item.source.name))
            dest_item = QTableWidgetItem(item.dest_relative)
            if Path(item.dest_relative).stem != item.source.stem:
                dest_item.setForeground(Qt.GlobalColor.yellow)  # renamed to avoid overwriting
                dest_item.setToolTip("Đã có file trùng tên ở đích → đặt tên mới, không ghi đè")
            self.table.setItem(r, 1, dest_item)
        for name in plan.already_present[: max(0, _PREVIEW_ROWS - self.table.rowCount())]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(Path(name).name))
            skip = QTableWidgetItem(f"{name} — đã có sẵn, bỏ qua")
            skip.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(r, 1, skip)
        free = free_space(plan.destination)
        lines = [f"<b>{len(plan.items)} file sẽ chép</b> ({_gb(plan.total_bytes)}) → {plan.destination}",
                 f"Dung lượng trống ở đích: {_gb(free)}"]
        if plan.already_present:
            lines.append(f"{len(plan.already_present)} file đã có sẵn ở đích (giống hệt) → bỏ qua, không tạo bản trùng.")
        if len(plan.items) > _PREVIEW_ROWS:
            lines.append(f"(bảng chỉ hiện {_PREVIEW_ROWS} file đầu)")
        if plan.missing:
            lines.append(f"<span style='color:{theme.ERROR}'>{len(plan.missing)} file không còn trên ổ đĩa sẽ bị bỏ qua.</span>")
        if not plan.items and plan.already_present:
            lines.append("<b>Tất cả ảnh đã chọn đều đã có ở thư mục này — không cần chép lại.</b>")
        enough = free > plan.total_bytes
        if not enough:
            lines.append(f"<span style='color:{theme.REJECT}'>Không đủ dung lượng trống.</span>")
        self._set_summary("<br>".join(lines), error=False, ready=bool(plan.items) and enough)

    def _set_summary(self, html: str, *, error: bool, ready: bool = False) -> None:
        self.summary.setText(f"<span style='color:{theme.REJECT}'>{html}</span>" if error else html)
        self.copy_button.setEnabled(ready)
        if ready and self.plan is not None:
            self.copy_button.setText(f"Sao chép {len(self.plan.items)} file")

    def _confirm_and_copy(self) -> None:
        if self.plan is None:
            return
        answer = QMessageBox.question(
            self, "Xác nhận sao chép",
            f"Sao chép {len(self.plan.items)} file ({_gb(self.plan.total_bytes)}) vào\n{self.plan.destination}?\n\n"
            "Ảnh gốc giữ nguyên. File trùng tên ở đích sẽ không bị ghi đè.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_copy()

    def start_copy(self) -> ExportThread:
        """Starts copying the current plan (tests call this directly, skipping the confirm box)."""
        assert self.plan is not None
        progress = QProgressDialog("Đang sao chép…", "Dừng", 0, len(self.plan.items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        thread = ExportThread(self.plan)
        thread.progress.connect(lambda done, total: progress.setValue(done))
        progress.canceled.connect(thread.cancel)
        thread.succeeded.connect(lambda result: self._finished(result, progress))
        thread.failed.connect(lambda msg: (progress.close(), QMessageBox.critical(self, "Lỗi khi sao chép", msg)))
        self._thread = thread
        thread.start()
        return thread

    def _finished(self, result: ExportResult, progress: QProgressDialog) -> None:
        progress.close()
        self.result = result
        parts = [f"Đã sao chép {len(result.copied)} file."]
        if result.renamed:
            parts.append(f"{len(result.renamed)} file được đặt tên mới để không ghi đè.")
        if result.failed:
            parts.append(f"{len(result.failed)} file lỗi: " + "; ".join(f"{k} ({v})" for k, v in list(result.failed.items())[:5]))
        if result.cancelled:
            parts.append("Bạn đã dừng giữa chừng; các file đã chép vẫn còn nguyên.")
        if result.manifest_csv:
            parts.append(f"Danh sách ảnh đã chép: thư mục con {result.manifest_csv.parent.name}")
        if self.isVisible():
            QMessageBox.information(self, "Xuất ảnh xong", "\n".join(parts))
        self.refresh()
