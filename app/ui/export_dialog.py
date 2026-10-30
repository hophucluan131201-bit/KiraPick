"""Export dialog (Part 3 spec §4): which photos, ① source, ② format, ③ destination layout — three independent choices
(12 combinations) — a preview of every file and every problem, confirmation of unsure matches, the copy, and a tab
that copies the names of the kept photos.

Planning from the imported folders runs on the GUI thread (stat only, as before Part 3). Planning from another folder
(scan, EXIF reads, full SHA-256) runs in an ExportPlanThread; each request has a generation and a result for an older
choice is dropped."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.export.copy_export import (
    ExportError,
    ExportIssue,
    ExportPlan,
    ExportResult,
    IssueStatus,
    OpStatus,
    Selection,
    free_space,
    plan_export,
    select_assets,
)
from app.export.formats import ExportFormat
from app.export.hashing import HashCache
from app.export.layout import UNKNOWN_FOLDER, Layout
from app.export.names import keep_names
from app.export.sources import Candidate, ExternalIndex, SourceSpec
from app.selection.client_list import list_collections
from app.storage import exports
from app.storage.project import Project
from app.ui import theme
from app.ui.jobs import ExportPlanThread, ExportThread, PlanRequest
from app.ui.shutdown import Gate

_PREVIEW_ROWS = 300
MAX_PICKERS = 50  # candidate pickers built at once (widgets are slow); the next ones appear once these are decided
IMPORTED_SYNC_LIMIT = 1000  # more photos than this: the imported-folder plan runs in the plan thread too (spec §5)
FORMAT_KEY = "export/format"
SOURCE_KEY = "export/source"
LAYOUT_KEY = "export/layout"
EXTERNAL_ROOT_KEY = "export/external_root"
LEGACY_INCLUDE_PAIRS_KEY = "export/include_pairs"  # before Part 3: "Kèm file JPEG của cặp RAW+JPEG"
MIGRATION_NOTICE_KEY = "export/migration_notice_pending"
FORMAT_LABELS = {ExportFormat.RAW_JPEG: "RAW + JPEG", ExportFormat.RAW: "Chỉ RAW", ExportFormat.JPEG: "Chỉ JPEG/JPG"}
LAYOUT_LABELS = {Layout.SINGLE: "Tất cả vào một thư mục", Layout.SUBJECTS: "Mỗi chủ thể một thư mục"}
MIGRATION_NOTICE = ("Trước đây bạn tắt 'Kèm JPEG của cặp RAW+JPEG'. Bản mới mặc định chép RAW + JPEG — chọn 'Chỉ RAW' "
                    "nếu chỉ muốn file RAW (ảnh chỉ có JPEG khi đó sẽ được báo thiếu).")
MATCH_LABELS = {"imported": "", "content": "giống hệt nội dung", "time": "khớp theo giờ chụp",
                "manual": "✋ xác nhận tay"}
ISSUE_LABELS = {
    IssueStatus.MISSING: "Thiếu", IssueStatus.MISSING_FORMAT: "Thiếu định dạng", IssueStatus.NOT_MATCHED: "Không khớp",
    IssueStatus.CONTENT_DIFFERS: "Khác nội dung", IssueStatus.AMBIGUOUS: "Không chắc",
    IssueStatus.PATH_TOO_LONG: "Đường dẫn quá dài",
}
_KIND_LABELS = {"raw": "RAW", "jpeg": "JPEG", "other": "khác", None: ""}
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


def _remembered(settings: QSettings | None, key: str, enum, default):  # noqa: ANN001, ANN202
    if settings is None:
        return default
    try:
        return enum(str(settings.value(key, default.value)))
    except ValueError:
        return default


def _gb(n: int) -> str:
    if n >= 1e8:
        return f"{n / 1e9:.2f} GB"
    return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{n / 1e3:.0f} KB"


def _note_only(issue: ExportIssue) -> bool:
    """"RAW/JPEG không có tại nguồn được chọn": the photo's other format is copied — information, not a problem."""
    return issue.status is IssueStatus.MISSING and issue.detail.endswith("không có tại nguồn được chọn")


def _candidate_text(c: Candidate) -> str:
    when = c.capture_time.strftime("%d/%m/%Y %H:%M:%S") if c.capture_time else "giờ chụp: không đọc được"
    return f"{c.relative} · {_gb(c.size)} · {when}" + (f" · {c.camera}" if c.camera else "")


class ExportDialog(QDialog):
    run_recorded = Signal()  # an export finished and was recorded: the "Xuất ảnh" step can show ✓

    def __init__(self, project: Project, selected_ids: list[int], parent: QWidget | None = None,
                 default_destination: Path | None = None, collection_id: int | None = None,
                 settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Xuất ảnh (sao chép)")
        self.resize(880, 700)
        self.project = project
        self.selected_ids = selected_ids
        self.settings = settings
        self.plan: ExportPlan | None = None
        self.result: ExportResult | None = None
        self._thread: ExportThread | None = None
        self.gate = Gate()  # the window shares its own: closed while the session is released (no dialogs then)
        self._generation = 0
        self._plan_threads: list[ExportPlanThread] = []
        self._index: ExternalIndex | None = None  # the scan of _index_root, reused until the folder is chosen again
        self._index_root: Path | None = None
        self._pending_root: Path | None = None
        self._hashes = HashCache()  # one per dialog and source folder (spec §3.9)
        self.confirmations: dict[tuple[int, str], Path] = {}  # the user's choices for unsure matches (memory only)
        self._issue_rows: list[ExportIssue] = []
        self._retry_pending = False
        self.scanning = False

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        page = QWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(page)
        self.tabs.addTab(self.scroll, "Sao chép file")
        layout = QVBoxLayout(page)
        intro = QLabel("Ảnh gốc <b>không bao giờ bị thay đổi</b> (cả trên thẻ nhớ): KiraPick chỉ sao chép sang thư mục "
                       "bạn chọn.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Ảnh nào
        scope = QGroupBox("Ảnh nào")
        grid = QGridLayout(scope)
        self.mode = QButtonGroup(self)
        self.radios: dict[Selection, QRadioButton] = {}
        for sel, text in ((Selection.KEEP, "Ảnh đã Giữ (K)"), (Selection.FAVORITE, "Ảnh Yêu thích (F)"),
                          (Selection.IDS, "Ảnh đang chọn"), (Selection.RATED, "Ảnh có từ"),
                          (Selection.COLLECTION, "Danh sách khách:")):
            rb = QRadioButton(text)
            self.mode.addButton(rb)
            self.radios[sel] = rb
        grid.addWidget(self.radios[Selection.KEEP], 0, 0)
        grid.addWidget(self.radios[Selection.FAVORITE], 0, 1)
        grid.addWidget(self.radios[Selection.IDS], 0, 2)
        self.min_rating = QSpinBox()
        self.min_rating.setRange(1, 5)
        self.min_rating.setValue(3)
        self.min_rating.setSuffix(" sao")
        rated = QHBoxLayout()
        rated.addWidget(self.radios[Selection.RATED])
        rated.addWidget(self.min_rating)
        rated.addStretch(1)
        grid.addLayout(rated, 1, 0)
        self.collection = QComboBox()
        for c in list_collections(project.conn):
            self.collection.addItem(f"{c['name']} ({c['n']} ảnh)", c["id"])
        client = QHBoxLayout()
        client.addWidget(self.radios[Selection.COLLECTION])
        client.addWidget(self.collection, 1)
        grid.addLayout(client, 1, 1, 1, 2)
        layout.addWidget(scope)
        self.radios[Selection.KEEP].setChecked(True)

        # ① Nguồn lấy ảnh
        source = QGroupBox("① Nguồn lấy ảnh")
        sbox = QVBoxLayout(source)
        self.source_group = QButtonGroup(self)
        self.source_imported = QRadioButton("Thư mục đã nhập vào KiraPick")
        self.source_external = QRadioButton("Nguồn khác (thẻ nhớ, ổ cứng):")
        self.source_group.addButton(self.source_imported)
        self.source_group.addButton(self.source_external)
        sbox.addWidget(self.source_imported)
        ext_row = QHBoxLayout()
        ext_row.addWidget(self.source_external)
        self.external_path = QLineEdit(str(settings.value(EXTERNAL_ROOT_KEY, "")) if settings is not None else "")
        self.external_path.setPlaceholderText("Chọn thư mục trên thẻ nhớ / ổ cứng…")
        self.external_path.setReadOnly(True)
        ext_row.addWidget(self.external_path, 1)
        self.browse_source = QPushButton("Chọn…")
        self.browse_source.clicked.connect(self._browse_source)
        ext_row.addWidget(self.browse_source)
        sbox.addLayout(ext_row)
        scan_row = QHBoxLayout()
        self.scan_status = QLabel()
        self.scan_status.setWordWrap(True)
        scan_row.addWidget(self.scan_status, 1)
        self.stop_scan_button = QPushButton("Dừng quét")
        self.stop_scan_button.clicked.connect(self.stop_scan)
        self.stop_scan_button.hide()
        scan_row.addWidget(self.stop_scan_button)
        sbox.addLayout(scan_row)
        layout.addWidget(source)
        if settings is not None:
            migrate_export_settings(settings)  # before the notice below reads its flag
        external = settings is not None and str(settings.value(SOURCE_KEY, "imported")) == "external"
        (self.source_external if external else self.source_imported).setChecked(True)

        # ② Định dạng
        self.notice = QWidget()
        nrow = QHBoxLayout(self.notice)
        nrow.setContentsMargins(0, 0, 0, 0)
        self.notice_label = QLabel(MIGRATION_NOTICE)
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet(f"color: {theme.ERROR};")
        nrow.addWidget(self.notice_label, 1)
        close_notice = QPushButton("×")
        close_notice.setToolTip("Đã hiểu, ẩn thông báo này")
        close_notice.setFixedWidth(28)
        close_notice.clicked.connect(self.dismiss_notice)
        nrow.addWidget(close_notice)
        layout.addWidget(self.notice)
        self.notice.setVisible(bool(settings is not None and settings.value(MIGRATION_NOTICE_KEY, False, bool)))
        fmt_box = QGroupBox("② Định dạng")
        frow = QHBoxLayout(fmt_box)
        self.format_group = QButtonGroup(self)
        self.format_buttons: dict[ExportFormat, QRadioButton] = {}
        chosen = export_format(settings)
        for fmt, text in FORMAT_LABELS.items():
            rb = QRadioButton(text)
            rb.setChecked(fmt is chosen)
            self.format_group.addButton(rb)
            self.format_buttons[fmt] = rb
            frow.addWidget(rb)
        frow.addStretch(1)
        layout.addWidget(fmt_box)

        # ③ Thư mục đích
        dest_box = QGroupBox("③ Thư mục đích")
        dbox = QVBoxLayout(dest_box)
        lrow = QHBoxLayout()
        self.layout_group = QButtonGroup(self)
        self.layout_buttons: dict[Layout, QRadioButton] = {}
        chosen_layout = _remembered(settings, LAYOUT_KEY, Layout, Layout.SINGLE)
        for lay, text in LAYOUT_LABELS.items():
            rb = QRadioButton(text)
            rb.setChecked(lay is chosen_layout)
            self.layout_group.addButton(rb)
            self.layout_buttons[lay] = rb
            lrow.addWidget(rb)
        lrow.addStretch(1)
        dbox.addLayout(lrow)
        dest_row = QHBoxLayout()
        self.dest = QLineEdit(str(default_destination) if default_destination else "")
        self.dest.setPlaceholderText("Chọn thư mục để chép ảnh vào…")
        browse = QPushButton("Chọn…")
        browse.clicked.connect(self._browse)
        dest_row.addWidget(self.dest, 1)
        dest_row.addWidget(browse)
        dbox.addLayout(dest_row)
        layout.addWidget(dest_box)

        # Xem trước
        self.preview_tabs = QTabWidget()
        self.plan_table = QTableWidget(0, 3)
        self.plan_table.setHorizontalHeaderLabels(["Ảnh", "Lấy từ", "Chép vào"])
        self.issue_table = QTableWidget(0, 5)
        self.issue_table.setHorizontalHeaderLabels(["Tình trạng", "Ảnh", "Loại", "Chi tiết / file ứng viên", ""])
        modes = {self.plan_table: (QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.Stretch,
                                   QHeaderView.ResizeMode.Stretch),
                 self.issue_table: (QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents,
                                    QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.Stretch,
                                    QHeaderView.ResizeMode.ResizeToContents)}
        for table, column_modes in modes.items():
            for column, mode in enumerate(column_modes):
                table.horizontalHeader().setSectionResizeMode(column, mode)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setMinimumHeight(120)
        self.table = self.plan_table  # the name used before Part 3
        self.preview_tabs.addTab(self.plan_table, "Sẽ chép (0)")
        self.preview_tabs.addTab(self.issue_table, "Cần xem lại (0)")
        layout.addWidget(self.preview_tabs, 1)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        # Tên ảnh đã Chọn
        self.names_tab = QWidget()
        nbox = QVBoxLayout(self.names_tab)
        self.names_count = QLabel()
        nbox.addWidget(self.names_count)
        self.names_with_ext = QCheckBox("Kèm đuôi file (.NEF, .JPG …)")
        self.names_with_ext.toggled.connect(lambda _on: self._refresh_names(self._names_ids))
        nbox.addWidget(self.names_with_ext)
        self.names_warning = QLabel()
        self.names_warning.setWordWrap(True)
        self.names_warning.hide()
        self.names_warning.setStyleSheet(f"color: {theme.ERROR};")
        nbox.addWidget(self.names_warning)
        self.names_list = QPlainTextEdit()
        self.names_list.setReadOnly(True)
        nbox.addWidget(self.names_list, 1)
        self.copy_names_button = QPushButton("📋 Sao chép tên ảnh")
        self.copy_names_button.clicked.connect(self.copy_names)
        nbox.addWidget(self.copy_names_button)
        self.names_status = QLabel()
        nbox.addWidget(self.names_status)
        self.tabs.addTab(self.names_tab, "📋 Tên ảnh đã Chọn")
        self._names: list[str] = []
        self._names_ids: list[int] = []
        self._names_dirty = True  # computed when the tab is shown (database only, but 10 000 photos take ~0.3 s)
        self.tabs.currentChanged.connect(lambda _i: self._names_if_shown())

        self.buttons = QDialogButtonBox()
        self.retry_button = self.buttons.addButton("Thử lại các file chưa chép", QDialogButtonBox.ButtonRole.ActionRole)
        self.retry_button.hide()
        self.retry_button.clicked.connect(self.retry)
        self.copy_button = self.buttons.addButton("Sao chép", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton("Đóng", QDialogButtonBox.ButtonRole.RejectRole)
        self.copy_button.clicked.connect(self._confirm_and_copy)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

        for rb in self.radios.values():
            rb.toggled.connect(lambda on: on and self.refresh())
        for fmt, rb in self.format_buttons.items():
            rb.toggled.connect(lambda on, f=fmt: on and self._choice(FORMAT_KEY, f.value, notice=True))
        for lay, rb in self.layout_buttons.items():
            rb.toggled.connect(lambda on, v=lay: on and self._choice(LAYOUT_KEY, v.value))
        self.source_imported.toggled.connect(lambda on: on and self._choice(SOURCE_KEY, "imported"))
        self.source_external.toggled.connect(lambda on: on and self._choice(SOURCE_KEY, "external"))
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

    # ------------------------------------------------------------------ choices
    @property
    def export_format(self) -> ExportFormat:
        return next(fmt for fmt, rb in self.format_buttons.items() if rb.isChecked())

    @property
    def export_layout(self) -> Layout:
        return next(lay for lay, rb in self.layout_buttons.items() if rb.isChecked())

    def _selection(self) -> Selection:
        return next(sel for sel, rb in self.radios.items() if rb.isChecked())

    def _ids(self) -> list[int]:
        return select_assets(self.project, self._selection(), min_rating=self.min_rating.value(),
                             ids=self.selected_ids, collection_id=self.collection.currentData())

    def _choice(self, key: str, value: str, *, notice: bool = False) -> None:
        if self.settings is not None:
            self.settings.setValue(key, value)
        if notice:
            self.dismiss_notice()
        self.refresh()

    def dismiss_notice(self) -> None:
        """The one-time migration notice goes away for good (a change of ② or ×, or closing the dialog)."""
        if self.notice.isVisible() or (self.settings is not None and self.settings.contains(MIGRATION_NOTICE_KEY)):
            self.notice.hide()
            if self.settings is not None:
                self.settings.remove(MIGRATION_NOTICE_KEY)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục để chép ảnh vào", self.dest.text())
        if folder:
            self.dest.setText(folder)
            self.refresh()

    def _browse_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục nguồn (thẻ nhớ, ổ cứng)",
                                                  self.external_path.text())
        if folder:
            self.set_external_root(Path(folder))

    def set_external_root(self, root: Path) -> None:
        """A (new) folder on a card or drive: scanned again; confirmations and hashes of the previous one are
        forgotten (spec §3.3 point 6)."""
        self.external_path.setText(str(root))
        if self.settings is not None:
            self.settings.setValue(EXTERNAL_ROOT_KEY, str(root))
        self._forget_source()
        if self.source_external.isChecked():
            self.refresh()
        else:
            self.source_external.setChecked(True)

    def _forget_source(self) -> None:
        self._index = self._index_root = None
        self.confirmations.clear()
        self._hashes = HashCache()

    # ------------------------------------------------------------------ planning
    @property
    def plan_threads(self) -> list[ExportPlanThread]:
        """Plan threads still running (the window waits for them before closing the session)."""
        return [t for t in self._plan_threads if t.isRunning()]

    def _cancel_plans(self) -> None:
        for t in self._plan_threads:
            t.cancel()

    def refresh(self) -> None:
        self._generation += 1  # any result still on its way is for an older choice
        self._cancel_plans()
        self.plan = None
        self._set_scanning(False)
        self._clear_preview()
        ids = self._ids()
        if ids != self._names_ids:
            self._names_ids, self._names_dirty = ids, True
            self._names_if_shown()
        dest_text = self.dest.text().strip()
        if not ids:
            self._set_summary("Không có ảnh nào khớp lựa chọn này.", error=True)
            return
        external = self.source_external.isChecked()
        root_text = self.external_path.text().strip()
        if external and not root_text:
            self.scan_status.setText("Chưa chọn thư mục")
            self._set_summary(f"{len(ids)} ảnh được chọn. Hãy chọn thư mục nguồn khác (thẻ nhớ, ổ cứng).",
                              error=False, ready=False)
            return
        self.scan_status.setText("" if not external else self.scan_status.text())
        if not dest_text:
            self._set_summary(f"{len(ids)} ảnh được chọn. Hãy chọn thư mục đích.", error=False, ready=False)
            return
        if external:
            root = Path(root_text)
            index = self._index if self._index_root == root else None
            self._start_plan(PlanRequest(tuple(ids), Path(dest_text), SourceSpec("external", root, index),
                                         self.export_format, self.export_layout, dict(self.confirmations)), root)
            return
        if len(ids) > IMPORTED_SYNC_LIMIT:  # measured: 10 000 photos plan in ~0.9 s — not on the GUI thread
            self._start_plan(PlanRequest(tuple(ids), Path(dest_text), SourceSpec(), self.export_format,
                                         self.export_layout), None)
            return
        try:
            plan = plan_export(self.project, ids, Path(dest_text), fmt=self.export_format, layout=self.export_layout)
        except ExportError as exc:
            self._set_summary(f"Không xuất được: {exc}", error=True)
            return
        self._show_plan(plan)

    def _start_plan(self, request: PlanRequest, root: Path | None) -> None:
        if not self.gate.open:  # the session is being released: no new work
            return
        thread = ExportPlanThread(self.project.folder, request, self._generation, self._hashes)
        thread.progress.connect(self._on_plan_progress)
        thread.planned.connect(self._on_planned)
        thread.failed.connect(self._on_plan_failed)
        thread.finished.connect(self._on_plan_thread_finished)
        self._plan_threads.append(thread)
        self._pending_root = root
        external = request.source.mode == "external"
        self._set_scanning(True, "" if not external else "Đang quét thư mục nguồn…" if request.source.index is None
                           else "Đang so khớp file…")
        self._set_summary("Đang chuẩn bị bản xem trước…", error=False, ready=False)
        thread.start()

    def stop_scan(self) -> None:
        self._generation += 1
        self._cancel_plans()
        self._set_scanning(False)
        self.scan_status.setText("Đã dừng quét. Chọn lại để quét tiếp.")
        self._set_summary("Đã dừng quét thư mục nguồn.", error=False, ready=False)

    def _set_scanning(self, on: bool, text: str = "") -> None:
        self.scanning = on
        self.stop_scan_button.setVisible(on)
        if on:
            self.scan_status.setText(text)
            self.copy_button.setEnabled(False)

    @Slot(int, str, int)
    def _on_plan_progress(self, generation: int, phase: str, count: int) -> None:
        if generation != self._generation:
            return
        self.scan_status.setText(f"Đang quét … {count:,} file".replace(",", " ") if phase == "scan" else
                                 f"Đã quét {count:,} file · đang so khớp và kiểm tra nội dung…".replace(",", " "))

    @Slot(int, object, object)
    def _on_planned(self, generation: int, plan: ExportPlan, index: ExternalIndex | None) -> None:
        if generation != self._generation:
            return  # a result for an older choice (spec §5)
        if index is not None:
            self._index, self._index_root = index, self._pending_root
        self._set_scanning(False)
        if index is not None:
            self.scan_status.setText(f"Đã quét {index.files:,} file".replace(",", " "))
        self._show_plan(plan)

    @Slot(int, str)
    def _on_plan_failed(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self._set_scanning(False)
        if not message:
            self.scan_status.setText("Đã dừng quét.")
            self._set_summary("Đã dừng quét thư mục nguồn.", error=False, ready=False)
            return
        self.scan_status.setText("")
        self._set_summary(f"Không xuất được: {message}", error=True)

    @Slot()
    def _on_plan_thread_finished(self) -> None:
        self._plan_threads = [t for t in self._plan_threads if t.isRunning()]

    # ------------------------------------------------------------------ preview
    def _clear_preview(self) -> None:
        self.plan_table.setRowCount(0)
        self.issue_table.setRowCount(0)
        self._issue_rows = []
        self.preview_tabs.setTabText(0, "Sẽ chép (0)")
        self.preview_tabs.setTabText(1, "Cần xem lại (0)")

    def _show_plan(self, plan: ExportPlan) -> None:
        self.plan = plan
        self._fill_plan_table(plan)
        self._fill_issue_table(plan)
        free = free_space(plan.destination)
        lines = [self._summary_line(plan, free)]
        if plan.already_present:
            lines.append(f"{len(plan.already_present)} file có vẻ đã có sẵn ở đích → khi chép sẽ so toàn bộ nội dung: "
                         "giống hệt thì bỏ qua, khác thì chép thành tên mới (không ghi đè).")
        if len(plan.operations) > _PREVIEW_ROWS:
            lines.append(f"(bảng chỉ hiện {_PREVIEW_ROWS} file đầu)")
        missing = sum(1 for i in plan.issues if i.status is IssueStatus.MISSING)
        if missing and not self.source_external.isChecked():
            lines.append(f"<span style='color:{theme.ERROR}'>{missing} file không còn trên ổ đĩa sẽ bị bỏ qua.</span>")
        problems = [i for i in plan.issues if not _note_only(i)]
        if problems:
            lines.append(f"<span style='color:{theme.ERROR}'>{len(problems)} mục cần xem lại (tab 'Cần xem lại') "
                         "sẽ bị bỏ qua nếu không xử lý.</span>")
        notes = len(plan.issues) - len(problems)
        if notes:
            lines.append(f"{notes} ảnh chỉ có một định dạng ở nguồn đã chọn: chép định dạng có sẵn (ghi chú trong "
                         "tab 'Cần xem lại').")
        lines += self._subject_hints(plan)
        if not plan.to_copy and plan.already_present:
            lines.append("<b>Tất cả ảnh đã chọn có vẻ đã có ở thư mục này.</b> Bấm nút để kiểm tra đầy đủ "
                         "(chỉ file khác nội dung mới được chép).")
        enough = free > plan.estimated_bytes
        if not enough:
            lines.append(f"<span style='color:{theme.REJECT}'>Không đủ dung lượng trống.</span>")
        elif free < plan.worst_case_bytes:
            lines.append("Nếu phải chép thêm, KiraPick đo lại chỗ trống trước mỗi ảnh; thiếu chỗ thì báo lỗi ảnh đó, "
                         "không bao giờ ghi đè hay xoá file ở đích.")
        ready = bool(plan.operations) and enough
        self._set_summary("<br>".join(lines), error=False, ready=ready)
        if self._retry_pending:
            self._retry_pending = False
            if ready:
                self._confirm_and_copy()

    def _summary_line(self, plan: ExportPlan, free: int) -> str:
        folders = len({op.folder for op in plan.operations})
        size = f"khoảng {_gb(plan.estimated_bytes)}"
        if plan.worst_case_bytes > plan.estimated_bytes:  # seemingly present targets may still differ (RV-P3-B-02)
            size += f", tối đa {_gb(plan.worst_case_bytes)} nếu file 'có vẻ đã có' khác nội dung"
        parts = [f"<b>{plan.photos_planned} ảnh → {len(plan.to_copy)} file sẽ chép</b> ({size}) vào "
                 f"{folders} thư mục ({plan.destination})", f"dung lượng trống {_gb(free)}"]
        if plan.already_present:
            parts.append(f"có vẻ đã có sẵn {len(plan.already_present)} (kiểm tra đầy đủ khi chép)")
        missing = sum(1 for i in plan.issues if i.status is IssueStatus.MISSING and not _note_only(i))
        if missing:
            parts.append(f"thiếu {missing}")
        for status, word in ((IssueStatus.MISSING_FORMAT, "thiếu định dạng"), (IssueStatus.NOT_MATCHED, "không khớp"),
                             (IssueStatus.CONTENT_DIFFERS, "khác nội dung"), (IssueStatus.AMBIGUOUS, "không chắc"),
                             (IssueStatus.PATH_TOO_LONG, "đường dẫn quá dài")):
            n = plan.counts().get(status, 0)
            if n:
                parts.append(f"{word} {n}")
        return " · ".join(parts)

    def _subject_hints(self, plan: ExportPlan) -> list[str]:
        stats = plan.layout_stats
        if stats is None:
            return []
        if not stats.analysed:
            return ["Chưa nhận diện chủ thể — mọi ảnh sẽ vào Chưa xác định."]
        out = []
        if stats.multi_subject:
            out.append(f"{stats.multi_subject} ảnh có nhiều chủ thể → được chép vào thư mục của từng người.")
        unknown = stats.unknown_suggested + stats.unknown_other
        if unknown:
            out.append(f"{unknown} ảnh vào '{UNKNOWN_FOLDER}' ({stats.unknown_suggested} AI chưa chắc, "
                       f"{stats.unknown_other} chưa có người / chưa phân tích).")
        if stats.unknown_suggested:
            out.append("Nên xem lại mục Cần xem lại (Nhận diện chủ thể) trước khi xuất.")
        return out

    def _fill_plan_table(self, plan: ExportPlan) -> None:
        self.plan_table.setUpdatesEnabled(False)
        shown = plan.operations[:_PREVIEW_ROWS]
        self.plan_table.setRowCount(len(shown))
        for r, op in enumerate(shown):
            photo = plan.photos.get(op.photo_id)
            self.plan_table.setItem(r, 0, QTableWidgetItem(f"{photo.stem if photo else ''} · {_KIND_LABELS[op.kind]}"))
            src = QTableWidgetItem(op.source_relative + (f" ({MATCH_LABELS[op.match]})" if MATCH_LABELS[op.match]
                                                         else ""))
            self.plan_table.setItem(r, 1, src)
            if op.maybe_present:
                dest_item = QTableWidgetItem(f"{op.dest_relative} — có vẻ đã có sẵn (kiểm tra đầy đủ khi chép)")
                dest_item.setForeground(Qt.GlobalColor.gray)
            else:
                dest_item = QTableWidgetItem(op.dest_relative)
                if Path(op.dest_relative).stem != op.source.stem:
                    dest_item.setForeground(Qt.GlobalColor.yellow)  # renamed to avoid overwriting
                    dest_item.setToolTip("Đã có file trùng tên ở đích → đặt tên mới, không ghi đè")
            self.plan_table.setItem(r, 2, dest_item)
        self.plan_table.setUpdatesEnabled(True)
        self.preview_tabs.setTabText(0, f"Sẽ chép ({len(plan.operations)})")

    def _fill_issue_table(self, plan: ExportPlan) -> None:
        self.issue_table.setUpdatesEnabled(False)
        unsure = [i for i in plan.issues if i.status is IssueStatus.AMBIGUOUS]  # the ones the user can act on first
        self._issue_rows = (unsure + [i for i in plan.issues if i.status is not IssueStatus.AMBIGUOUS])[:_PREVIEW_ROWS]
        self.issue_table.setRowCount(len(self._issue_rows))
        pickers = 0
        for r, issue in enumerate(self._issue_rows):
            self.issue_table.setItem(r, 0, QTableWidgetItem("Ghi chú" if _note_only(issue)
                                                            else ISSUE_LABELS[issue.status]))
            self.issue_table.setItem(r, 1, QTableWidgetItem(issue.stem))
            self.issue_table.setItem(r, 2, QTableWidgetItem(_KIND_LABELS.get(issue.kind, "")))
            candidates = [c for c in issue.candidates if isinstance(c, Candidate)]
            if issue.status is IssueStatus.AMBIGUOUS and candidates and pickers < MAX_PICKERS:
                pickers += 1
                box = QComboBox()
                for c in candidates:
                    box.addItem(_candidate_text(c))
                box.setToolTip(issue.detail)
                self.issue_table.setCellWidget(r, 3, box)
                use = QPushButton("Dùng file này")
                use.clicked.connect(lambda _c=False, row=r, b=box: self.use_candidate(row, b.currentIndex()))
                self.issue_table.setCellWidget(r, 4, use)
            elif issue.status is IssueStatus.AMBIGUOUS and candidates:
                self.issue_table.setItem(r, 3, QTableWidgetItem(
                    f"{issue.detail} · {len(candidates)} file ứng viên (chọn được sau khi xử lý các dòng trên)"))
            else:
                self.issue_table.setItem(r, 3, QTableWidgetItem(issue.detail))
        self.issue_table.setUpdatesEnabled(True)
        self.preview_tabs.setTabText(1, f"Cần xem lại ({len(plan.issues)})")

    def use_candidate(self, row: int, candidate: int) -> None:
        """"Dùng file này": the user's choice for an unsure match, for this dialog only (spec §3.3 point 6)."""
        issue = self._issue_rows[row]
        chosen = [c for c in issue.candidates if isinstance(c, Candidate)][candidate]
        if issue.kind is not None:
            self.confirmations[(issue.photo_id, issue.kind)] = chosen.path
        self.refresh()

    # ------------------------------------------------------------------ names
    def _names_if_shown(self) -> None:
        if self._names_dirty and self.tabs.currentWidget() is self.names_tab:
            self._refresh_names(self._names_ids)

    def _refresh_names(self, ids: list[int]) -> None:
        """Database only: works whatever the source, destination or card state (spec §3.8)."""
        self._names_dirty = False
        names = keep_names(self.project.conn, ids, with_extension=self.names_with_ext.isChecked())
        self._names = names.lines
        self.names_count.setText(f"{names.photos} ảnh đã Chọn trong phạm vi này · {len(names.lines)} tên")
        self.names_list.setPlainText("\n".join(names.lines))
        if names.shared_stems:
            shown = ", ".join(f"{stem} ({n} ảnh)" for stem, n in list(names.shared_stems.items())[:5])
            more = len(names.shared_stems) - 5
            self.names_warning.setText(
                f"⚠ Có ảnh khác nhau trùng tên: {shown}" + (f" và {more} tên khác" if more > 0 else "")
                + ". Mỗi tên chỉ ghi một lần; người nhận dò theo tên có thể gặp nhiều ảnh cùng tên.")
        else:
            self.names_warning.setText("")
        self.names_warning.setVisible(bool(names.shared_stems))
        self.names_status.setText("")
        self.copy_names_button.setEnabled(bool(names.lines))

    def copy_names(self) -> None:
        if self._names_dirty:
            self._refresh_names(self._names_ids)
        QGuiApplication.clipboard().setText("\n".join(self._names))  # local clipboard only
        self.names_status.setText(f"Đã sao chép {len(self._names)} tên vào bộ nhớ tạm")

    # ------------------------------------------------------------------ copy
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
        self.copy_button.setEnabled(ready and not self.scanning)
        if ready and self.plan is not None:
            n, k = len(self.plan.to_copy), len(self.plan.already_present)
            self.copy_button.setText(f"Sao chép {n} file" + (f" · kiểm tra {k} file đã có" if k else "") if n
                                     else f"Kiểm tra {k} file đã có")
        elif not ready:
            self.copy_button.setText("Sao chép")

    def confirm_text(self) -> str:
        assert self.plan is not None
        plan = self.plan
        text = (f"Sao chép {len(plan.to_copy)} file (khoảng {_gb(plan.estimated_bytes)}) của {plan.photos_planned} "
                f"ảnh vào\n{plan.destination}?\n\nẢnh gốc giữ nguyên (cả trên thẻ nhớ). File trùng tên ở đích sẽ "
                "không bị ghi đè.")
        if plan.already_present:
            text += f"\n{len(plan.already_present)} file có vẻ đã có sẵn sẽ được kiểm tra đầy đủ."
        if plan.issues:
            counts = plan.counts()
            listed = ", ".join(f"{n} {ISSUE_LABELS[s].lower()}" for s, n in counts.items())
            text += f"\n\nSẽ bỏ qua: {listed}."
        return text

    def _confirm_and_copy(self) -> None:
        if self.plan is None or self.scanning:
            return
        answer = QMessageBox.question(self, "Xác nhận sao chép", self.confirm_text())
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
        self.retry_button.hide()
        progress = QProgressDialog("Đang sao chép…", "Dừng", 0, len(self.plan.items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        thread = ExportThread(self.plan, options={"scope": self._selection().value})
        thread.progress.connect(lambda done, total: progress.setValue(done))
        stop = QPushButton("Dừng")
        progress.setCancelButton(stop)
        stop.clicked.connect(thread.cancel)  # the user's Dừng: stops inside the file being copied (removed)
        progress.canceled.connect(thread.stop_after_file)  # closed with the window: finishes the current photo
        thread.succeeded.connect(lambda result: self._finished(result, progress))
        thread.failed.connect(lambda msg: (progress.close(), QMessageBox.critical(self, "Lỗi khi sao chép", msg)
                                           if self.gate.open else log.warning("export failed while closing: %s", msg)))
        self._thread = thread
        thread.start()
        return thread

    def retry(self) -> None:
        """"Thử lại các file chưa chép": plan again (the other folder is scanned again), then the usual confirmation;
        identical files already copied are verified and skipped (spec §3.7)."""
        self._index = self._index_root = None
        self._retry_pending = True
        self.refresh()

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
        statuses = list(result.statuses.values())
        changed = statuses.count(OpStatus.SOURCE_CHANGED.value)
        if changed:
            parts.append(f"{changed} file nguồn đã thay đổi sau khi xem trước → không chép; hãy xem trước lại.")
        if result.source_unavailable:
            parts.append("Nguồn không còn truy cập được (thẻ nhớ / ổ đĩa đã rút?); các file đã chép vẫn còn nguyên.")
        if result.cancelled:
            parts.append("Bạn đã dừng giữa chừng; các file đã chép vẫn còn nguyên.")
        if result.manifest_csv:
            parts.append(f"Danh sách đầy đủ (cả file bỏ qua): thư mục con {result.manifest_csv.parent.name}")
        left = sum(statuses.count(s.value) for s in (OpStatus.FAILED, OpStatus.NOT_STARTED, OpStatus.SOURCE_CHANGED))
        if left:
            parts.append(f"Còn {left} file chưa chép: bấm 'Thử lại các file chưa chép'.")
        self.retry_button.setVisible(bool(left))
        if self.source_external.isChecked():
            self._index = self._index_root = None  # the card may have changed: the next preview scans it again
        if self.isVisible():
            QMessageBox.information(self, "Xuất ảnh xong", "\n".join(parts))
        self.refresh()

    # ------------------------------------------------------------------ closing
    def _stop_background(self) -> None:
        self._generation += 1
        self._cancel_plans()
        self.dismiss_notice()

    def reject(self) -> None:
        self._stop_background()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        self._stop_background()
        super().closeEvent(event)
