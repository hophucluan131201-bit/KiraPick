"""Export dialog: choose what to copy, preview the exact file names, confirm, copy."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
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
from app.export.formats import ExportFormat
from app.selection.client_list import list_collections
from app.storage import exports
from app.storage.project import Project
from app.ui import theme
from app.ui.jobs import ExportThread
from app.ui.shutdown import Gate

_PREVIEW_ROWS = 300
FORMAT_KEY = "export/format"
LEGACY_INCLUDE_PAIRS_KEY = "export/include_pairs"  # before Part 3: "Kèm file JPEG của cặp RAW+JPEG"
MIGRATION_NOTICE_KEY = "export/migration_notice_pending"
FORMAT_LABELS = {ExportFormat.RAW_JPEG: "RAW + JPEG", ExportFormat.RAW: "Chỉ RAW", ExportFormat.JPEG: "Chỉ JPEG/JPG"}
log = logging.getLogger(__name__)


def migrate_export_settings(settings: QSettings) -> None:
    """The old "Kèm JPEG" box becomes ② Định dạng = RAW + JPEG whatever its value (spec §4, CR-P3-D03). When it was
    off this changes what an export copies (a pair's JPEG now comes too): a one-time notice is pending then."""
    if not settings.contains(LEGACY_INCLUDE_PAIRS_KEY):
        return
    was_on = settings.value(LEGACY_INCLUDE_PAIRS_KEY, True, bool)
    if not settings.contains(FORMAT_KEY):
        settings.setValue(FORMAT_KEY, ExportFormat.RAW_JPEG.value)
    if not was_on:
        settings.setValue(MIGRATION_NOTICE_KEY, True)
    settings.remove(LEGACY_INCLUDE_PAIRS_KEY)


def export_format(settings: QSettings | None) -> ExportFormat:
    """The remembered ② Định dạng (RAW + JPEG when none, or unreadable)."""
    if settings is None:
        return ExportFormat.RAW_JPEG
    migrate_export_settings(settings)
    try:
        return ExportFormat(str(settings.value(FORMAT_KEY, ExportFormat.RAW_JPEG.value)))
    except ValueError:
        return ExportFormat.RAW_JPEG


def _gb(n: int) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


class ExportDialog(QDialog):
    run_recorded = Signal()  # an export finished and was recorded: the "Xuất ảnh" step can show ✓
    def __init__(self, project: Project, selected_ids: list[int], parent: QWidget | None = None,
                 default_destination: Path | None = None, collection_id: int | None = None,
                 settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Xuất ảnh đã chọn (sao chép)")
        self.resize(820, 620)
        self.project = project
        self.selected_ids = selected_ids
        self.plan: ExportPlan | None = None
        self.result: ExportResult | None = None
        self._thread: ExportThread | None = None
        self.gate = Gate()  # the window shares its own: closed while the session is released (no dialogs then)

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

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Định dạng:"))
        self.format_group = QButtonGroup(self)
        self.format_buttons: dict[ExportFormat, QRadioButton] = {}
        chosen = export_format(settings)
        for fmt, text in FORMAT_LABELS.items():
            rb = QRadioButton(text)
            rb.setChecked(fmt is chosen)
            self.format_group.addButton(rb)
            self.format_buttons[fmt] = rb
            opts.addWidget(rb)
        if settings is not None:  # the bottom bar's "x GB" follows this choice
            for fmt, rb in self.format_buttons.items():
                rb.toggled.connect(lambda on, f=fmt: on and settings.setValue(FORMAT_KEY, f.value))
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
        for rb in self.format_buttons.values():
            rb.toggled.connect(lambda on: on and self.refresh())
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

    @property
    def export_format(self) -> ExportFormat:
        return next(fmt for fmt, rb in self.format_buttons.items() if rb.isChecked())

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
            plan = plan_export(self.project, ids, Path(dest_text), fmt=self.export_format)
        except ExportError as exc:
            self._set_summary(f"Không xuất được: {exc}", error=True)
            return
        self.plan = plan
        for item in plan.to_copy[:_PREVIEW_ROWS]:
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
            skip = QTableWidgetItem(f"{name} — có vẻ đã có sẵn (kiểm tra đầy đủ khi chép)")
            skip.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(r, 1, skip)
        free = free_space(plan.destination)
        size = f"khoảng {_gb(plan.estimated_bytes)}"
        if plan.worst_case_bytes > plan.estimated_bytes:  # seemingly present targets may still differ (RV-P3-B-02)
            size += f", tối đa {_gb(plan.worst_case_bytes)} nếu file 'có vẻ đã có' khác nội dung"
        lines = [f"<b>{len(plan.to_copy)} file sẽ chép</b> ({size}) → {plan.destination}",
                 f"Dung lượng trống ở đích: {_gb(free)}"]
        if plan.already_present:
            lines.append(f"{len(plan.already_present)} file có vẻ đã có sẵn ở đích → khi chép sẽ so toàn bộ nội dung: "
                         "giống hệt thì bỏ qua, khác thì chép thành tên mới (không ghi đè).")
        if len(plan.to_copy) > _PREVIEW_ROWS:
            lines.append(f"(bảng chỉ hiện {_PREVIEW_ROWS} file đầu)")
        if plan.missing:
            lines.append(f"<span style='color:{theme.ERROR}'>{len(plan.missing)} file không còn trên ổ đĩa sẽ bị bỏ qua.</span>")
        if not plan.to_copy and plan.already_present:
            lines.append("<b>Tất cả ảnh đã chọn có vẻ đã có ở thư mục này.</b> Bấm nút để kiểm tra đầy đủ "
                         "(chỉ file khác nội dung mới được chép).")
        enough = free > plan.estimated_bytes
        if not enough:
            lines.append(f"<span style='color:{theme.REJECT}'>Không đủ dung lượng trống.</span>")
        elif free < plan.worst_case_bytes:
            lines.append("Nếu phải chép thêm, KiraPick đo lại chỗ trống trước mỗi ảnh; thiếu chỗ thì báo lỗi ảnh đó, "
                         "không bao giờ ghi đè hay xoá file ở đích.")
        self._set_summary("<br>".join(lines), error=False, ready=bool(plan.operations) and enough)

    def _record_run(self, result: ExportResult) -> None:
        """A finished, not cancelled export that copied something counts for the "Xuất ảnh" step."""
        if result.cancelled or not result.copied:
            return
        if len(result.copied) != len(result.copied_ids):  # one asset id per copied file, always
            log.error("export result lists disagree (%d files, %d ids): run not recorded",
                      len(result.copied), len(result.copied_ids))
            return
        try:  # copied_ids lists the asset of every copied file, renames and subfolders included
            with self.project.transaction() as conn:
                exports.record(conn, exports.photo_count(conn, result.copied_ids), len(result.copied))
        except Exception:  # noqa: BLE001 - the copies are done; only the step mark is lost
            log.exception("could not record the export run")
            return
        self.run_recorded.emit()

    def _set_summary(self, html: str, *, error: bool, ready: bool = False) -> None:
        self.summary.setText(f"<span style='color:{theme.REJECT}'>{html}</span>" if error else html)
        self.copy_button.setEnabled(ready)
        if ready and self.plan is not None:
            n, k = len(self.plan.to_copy), len(self.plan.already_present)
            self.copy_button.setText(f"Sao chép {n} file" + (f" · kiểm tra {k} file đã có" if k else "") if n
                                     else f"Kiểm tra {k} file đã có")

    def _confirm_and_copy(self) -> None:
        if self.plan is None:
            return
        answer = QMessageBox.question(
            self, "Xác nhận sao chép",
            f"Sao chép {len(self.plan.to_copy)} file (khoảng {_gb(self.plan.estimated_bytes)}) vào\n{self.plan.destination}?\n\n"
            "Ảnh gốc giữ nguyên. File trùng tên ở đích sẽ không bị ghi đè.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_copy()

    @property
    def copy_thread(self) -> ExportThread | None:
        """The copy started from this dialog (the window waits for it before closing the session)."""
        return self._thread

    def start_copy(self) -> ExportThread:
        """Starts copying the current plan (tests call this directly, skipping the confirm box)."""
        assert self.plan is not None
        if self._thread is not None and self._thread.isRunning():  # one copy at a time: never drop a running thread
            return self._thread
        progress = QProgressDialog("Đang sao chép…", "Dừng", 0, len(self.plan.items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        thread = ExportThread(self.plan)
        thread.progress.connect(lambda done, total: progress.setValue(done))
        progress.canceled.connect(thread.cancel)
        thread.succeeded.connect(lambda result: self._finished(result, progress))
        thread.failed.connect(lambda msg: (progress.close(), QMessageBox.critical(self, "Lỗi khi sao chép", msg)
                                           if self.gate.open else log.warning("export failed while closing: %s", msg)))
        self._thread = thread
        thread.start()
        return thread

    def _finished(self, result: ExportResult, progress: QProgressDialog) -> None:
        progress.close()
        self.result = result
        self._record_run(result)
        parts = [f"Đã sao chép {len(result.copied)} file."]
        if result.already_present:
            parts.append(f"{len(result.already_present)} file đã có sẵn, giống hệt từng byte → không chép lại.")
        if result.renamed:
            parts.append(f"{len(result.renamed)} file được đặt tên mới để không ghi đè.")
        if result.failed:
            parts.append(f"{len(result.failed)} file lỗi: " + "; ".join(f"{k} ({v})" for k, v in list(result.failed.items())[:5]))
        changed = sum(v == "source_changed" for v in result.statuses.values())
        if changed:
            parts.append(f"{changed} file nguồn đã thay đổi sau khi xem trước → không chép; hãy xem trước lại.")
        if result.source_unavailable:
            parts.append("Nguồn không còn truy cập được (thẻ nhớ / ổ đĩa đã rút?); các file đã chép vẫn còn nguyên.")
        if result.cancelled:
            parts.append("Bạn đã dừng giữa chừng; các file đã chép vẫn còn nguyên.")
        if result.manifest_csv:
            parts.append(f"Danh sách xuất (mọi file và lý do): thư mục con {result.manifest_csv.parent.name}")
        if self.isVisible():
            QMessageBox.information(self, "Xuất ảnh xong", "\n".join(parts))
        self.refresh()
