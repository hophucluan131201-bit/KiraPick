"""Main window: folders/filters | grid or loupe | inspector, plus import/export."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QSettings, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.storage import decisions
from app.storage.project import DB_NAME, Project, ProjectError
from app.ui.asset_model import ROLE_RECORD, AssetListModel, AssetRecord, Filter
from app.ui.export_dialog import ExportDialog
from app.ui.grid import make_filmstrip, make_grid
from app.ui.inspector import Inspector
from app.ui.jobs import ImportThread
from app.ui.viewer import ImageViewer

log = logging.getLogger(__name__)

_FILTERS = [
    (Filter.ALL, "Tất cả ảnh"),
    (Filter.UNFLAGGED, "Chưa chọn"),
    (Filter.KEEP, "Giữ ✓"),
    (Filter.REJECT, "Loại ✕"),
    (Filter.FAVORITE, "Yêu thích ♥"),
    (Filter.RATED, "Từ 3 sao ★★★"),
    (Filter.ERRORS, "Ảnh lỗi"),
]
_RELOAD_DURING_IMPORT_MS = 1500


def default_projects_dir() -> Path:
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(docs or Path.home()) / "Snorlu Projects"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"Snorlu AI Culling {__version__}")
        self.resize(1500, 900)
        self.settings = settings or QSettings("Snorlu", "AI Culling")
        self.project: Project | None = None
        self.import_thread: ImportThread | None = None
        self._last_import_root: Path | None = None
        self.model = AssetListModel(self)

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._build_shortcuts()

        self._reload_timer = QTimer(self)
        self._reload_timer.setInterval(_RELOAD_DURING_IMPORT_MS)
        self._reload_timer.timeout.connect(self.reload_preserving_view)

        last = self.settings.value("last_project", "", str)
        if last and (Path(last) / DB_NAME).is_file():
            try:
                self.open_project(Path(last))
            except Exception:  # noqa: BLE001 - a broken last project must not block startup
                log.exception("could not reopen last project")
        self._update_empty_state()

    # ------------------------------------------------------------ layout
    def _build_toolbar(self) -> None:
        tb = QToolBar("Chính", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        self.act_import = QAction("📂  Nhập thư mục ảnh", self)
        self.act_import.setShortcut(QKeySequence("Ctrl+I"))
        self.act_import.triggered.connect(self.choose_and_import)
        self.act_open = QAction("Mở dự án…", self)
        self.act_open.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open.triggered.connect(self.choose_and_open_project)
        self.act_export = QAction("⤴  Xuất ảnh…", self)
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.triggered.connect(self.open_export_dialog)
        self.act_loupe = QAction("🔍  Xem lớn (Space)", self)
        self.act_loupe.triggered.connect(self.toggle_loupe)
        self.act_auto_advance = QAction("Tự chuyển ảnh sau khi Giữ/Loại", self)
        self.act_auto_advance.setCheckable(True)
        self.act_auto_advance.setChecked(self.settings.value("auto_advance", False, bool))
        self.act_auto_advance.toggled.connect(lambda on: self.settings.setValue("auto_advance", on))
        self.act_help = QAction("Phím tắt", self)
        self.act_help.triggered.connect(self.show_shortcuts)
        for act in (self.act_import, self.act_open, self.act_export, self.act_loupe):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_auto_advance)
        tb.addAction(self.act_help)

    def _build_body(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 6, 6, 6)
        t1 = QLabel("THƯ MỤC")
        t1.setObjectName("sectionTitle")
        self.sources = QListWidget()
        self.sources.setMaximumHeight(180)
        self.sources.currentRowChanged.connect(self._on_source_changed)
        t2 = QLabel("LỌC")
        t2.setObjectName("sectionTitle")
        self.filters = QListWidget()
        for flt, text in _FILTERS:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, flt)
            self.filters.addItem(item)
        self.filters.setCurrentRow(0)
        self.filters.currentRowChanged.connect(self._on_filter_changed)
        for w in (t1, self.sources, t2, self.filters):
            side_layout.addWidget(w)
        side_layout.addStretch(1)
        side.setMinimumWidth(190)

        self.center = QStackedWidget()
        self.empty_hint = QLabel(
            "Chưa có ảnh.\n\nBấm  “📂 Nhập thư mục ảnh”  (Ctrl+I) để bắt đầu.\n"
            "Ảnh gốc chỉ được đọc, không bao giờ bị sửa hay xoá."
        )
        self.empty_hint.setObjectName("emptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid = make_grid(self, 220)
        self.grid.setModel(self.model)
        self.grid.selectionModel().currentChanged.connect(self._on_current_changed)
        self.grid.doubleClicked.connect(lambda _: self.toggle_loupe())

        loupe = QWidget()
        loupe_layout = QVBoxLayout(loupe)
        loupe_layout.setContentsMargins(0, 0, 0, 0)
        self.viewer = ImageViewer()
        self.viewer.status_changed.connect(lambda msg: self.status.setText(msg))
        self.filmstrip = make_filmstrip(self, 96)
        self.filmstrip.setModel(self.model)
        self.filmstrip.setSelectionModel(self.grid.selectionModel())  # one shared selection
        loupe_layout.addWidget(self.viewer, 1)
        loupe_layout.addWidget(self.filmstrip)

        self.center.addWidget(self.empty_hint)  # 0
        self.center.addWidget(self.grid)  # 1
        self.center.addWidget(loupe)  # 2

        self.inspector = Inspector()
        splitter.addWidget(side)
        splitter.addWidget(self.center)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 1000, 290])
        self.setCentralWidget(splitter)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self.status = QLabel("Sẵn sàng")
        self.counts = QLabel("")
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setVisible(False)
        self.pause_button = QPushButton("Tạm dừng")
        self.pause_button.setVisible(False)
        self.pause_button.clicked.connect(self._pause_or_resume)
        sb.addWidget(self.status, 1)
        sb.addPermanentWidget(self.counts)
        sb.addPermanentWidget(self.progress)
        sb.addPermanentWidget(self.pause_button)

    def _build_shortcuts(self) -> None:
        def sc(key: str, fn: object) -> None:
            QShortcut(QKeySequence(key), self, fn, context=Qt.ShortcutContext.WindowShortcut)

        sc("K", lambda: self.set_flag("keep"))
        sc("X", lambda: self.set_flag("reject"))
        sc("U", lambda: self.set_flag(None))
        sc("F", self.toggle_favorite)
        for n in range(6):
            sc(str(n), lambda n=n: self.set_rating(n))
        sc("Right", lambda: self.step(1))
        sc("Left", lambda: self.step(-1))
        sc("Space", self.toggle_loupe)
        sc("Return", self.toggle_loupe)
        sc("Escape", lambda: self.show_loupe(False))
        sc("Z", self.toggle_zoom)
        sc("F1", self.show_shortcuts)

    # ---------------------------------------------------------- projects
    def choose_and_open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục dự án", str(default_projects_dir()))
        if folder:
            try:
                self.open_project(Path(folder))
            except ProjectError as exc:
                QMessageBox.warning(self, "Không mở được dự án", str(exc))

    def open_project(self, folder: Path) -> None:
        project = Project.open(folder)
        self._set_project(project)

    def _set_project(self, project: Project) -> None:
        if self.project is not None:
            self.project.close()
        self.project = project
        self.settings.setValue("last_project", str(project.folder))
        self.setWindowTitle(f"{project.name} — Snorlu AI Culling {__version__}")
        self.model.set_project(project)
        self._refresh_sidebar()
        self._update_empty_state()
        self._offer_resume()
        if self.model.rowCount():
            self.select_row(0)

    def _new_project_for(self, photo_root: Path) -> Project:
        base = default_projects_dir()
        name = photo_root.name or "Du an"
        folder = base / name
        n = 1
        while (folder / DB_NAME).exists():
            n += 1
            folder = base / f"{name} ({n})"
        return Project.create(folder, name)

    # ------------------------------------------------------------ import
    def choose_and_import(self) -> None:
        if self.import_thread is not None:
            return
        start = self.settings.value("last_import_dir", "", str)
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục ảnh để nhập", start)
        if folder:
            self.settings.setValue("last_import_dir", folder)
            self.start_import(Path(folder))

    def start_import(self, root: Path) -> ImportThread | None:
        if self.import_thread is not None:
            return None
        if self.project is None:
            self._set_project(self._new_project_for(root))
            self.status.setText(f"Đã tạo dự án mới tại {self.project.folder}")  # type: ignore[union-attr]
        assert self.project is not None
        self._last_import_root = root
        thread = ImportThread(self.project.folder, root)
        thread.progress.connect(self._on_import_progress)
        thread.succeeded.connect(self._on_import_done)
        thread.failed.connect(self._on_import_failed)
        thread.finished.connect(self._on_import_thread_finished)
        self.import_thread = thread
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.pause_button.setText("Tạm dừng")
        self.pause_button.setVisible(True)
        self.pause_button.setEnabled(True)
        self.act_import.setEnabled(False)
        self._reload_timer.start()
        thread.start()
        return thread

    def _on_import_progress(self, phase: str, done: int, total: int) -> None:
        label = {"scan": "Đang quét thư mục…", "register": "Đang ghi nhận file…",
                 "ingest": "Đang tạo ảnh xem trước…", "pair": "Đang ghép cặp RAW+JPEG…"}.get(phase, phase)
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status.setText(f"{label} {done}/{total}")
        else:
            self.progress.setRange(0, 0)
            self.status.setText(label)

    def _on_import_done(self, summary: dict) -> None:
        if summary["cancelled"]:
            self.status.setText(f"Đã tạm dừng nhập ảnh ({summary['ingested']} ảnh xong). Bấm “Tiếp tục” để làm tiếp.")
        else:
            parts = [f"Nhập xong: {summary['found']} file"]
            if summary["new"]:
                parts.append(f"{summary['new']} mới")
            if summary["duplicates"]:
                parts.append(f"{summary['duplicates']} trùng lặp (bỏ qua)")
            if summary["failed"]:
                parts.append(f"{summary['failed']} lỗi")
            if summary["missing"]:
                parts.append(f"{summary['missing']} không còn trên ổ đĩa")
            if summary["pairs"]:
                parts.append(f"{summary['pairs']} cặp RAW+JPEG")
            self.status.setText(", ".join(parts) + ".")

    def _on_import_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Lỗi khi nhập ảnh", message)

    def _on_import_thread_finished(self) -> None:
        cancelled = self.import_thread is not None and self.import_thread.cancel_requested
        self.import_thread = None
        self._reload_timer.stop()
        self.progress.setVisible(False)
        self.act_import.setEnabled(True)
        if cancelled:
            self.pause_button.setText("Tiếp tục")
            self.pause_button.setEnabled(True)
        else:
            self.pause_button.setVisible(False)
        self.reload_preserving_view()
        self._refresh_sidebar()
        self._update_empty_state()
        if not self.grid.currentIndex().isValid() and self.model.rowCount():
            self.select_row(0)

    def _pause_or_resume(self) -> None:
        if self.import_thread is not None:
            self.import_thread.cancel()
            self.pause_button.setEnabled(False)
            self.status.setText("Đang tạm dừng…")
        elif self._last_import_root is not None:
            self.start_import(self._last_import_root)

    def _offer_resume(self) -> None:
        """After a crash/close mid-import, offer to finish the remaining files."""
        assert self.project is not None
        row = self.project.conn.execute(
            """SELECT s.root_path, COUNT(*) AS n FROM stage_status st JOIN assets a ON a.id = st.asset_id
               JOIN sources s ON s.id = a.source_id
               WHERE st.state = 'pending' AND a.status = 'pending' GROUP BY s.id ORDER BY n DESC LIMIT 1"""
        ).fetchone()
        if row and Path(row["root_path"]).is_dir():
            self._last_import_root = Path(row["root_path"])
            self.pause_button.setText(f"Tiếp tục nhập ({row['n']} ảnh còn lại)")
            self.pause_button.setVisible(True)
            self.pause_button.setEnabled(True)
        else:
            self.pause_button.setVisible(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        if self.import_thread is not None:
            self.import_thread.cancel()
            self.import_thread.wait(15000)  # resumable: unfinished files continue next time
        self.viewer.wait_idle(5000)
        if self.project is not None:
            self.project.close()
        super().closeEvent(event)

    # ------------------------------------------------------- navigation
    def reload_preserving_view(self) -> None:
        current = self.current_record()
        selected = {r.id for r in self.selected_records()}
        scroll = self.grid.verticalScrollBar().value()
        self.model.reload()
        sel = self.grid.selectionModel()
        for asset_id in selected:
            idx = self.model.index_of(asset_id)
            if idx.isValid():
                sel.select(idx, QItemSelectionModel.SelectionFlag.Select)
        if current is not None:
            idx = self.model.index_of(current.id)
            if idx.isValid():
                sel.setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)
        self.grid.verticalScrollBar().setValue(scroll)
        self._update_counts()
        self._update_empty_state()

    def current_record(self) -> AssetRecord | None:
        return self.model.record(self.grid.currentIndex())

    def selected_records(self) -> list[AssetRecord]:
        recs = [self.model.record(i) for i in self.grid.selectionModel().selectedIndexes()]
        return [r for r in recs if r is not None]

    def select_row(self, row: int) -> None:
        idx = self.model.index(row)
        if idx.isValid():
            self.grid.selectionModel().setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            self.grid.scrollTo(idx)
            self.filmstrip.scrollTo(idx)

    def step(self, delta: int) -> None:
        if not self.model.rowCount():
            return
        row = self.grid.currentIndex().row()
        self.select_row(max(0, min(self.model.rowCount() - 1, (row if row >= 0 else -delta) + delta)))

    def _on_current_changed(self, current: QModelIndex, _prev: QModelIndex) -> None:
        rec = self.model.record(current)
        self.inspector.show_record(rec)
        if rec is not None and self.center.currentIndex() == 2:
            self.viewer.show_photo(rec.path, self.model.pixmap(rec))

    def _on_source_changed(self, row: int) -> None:
        item = self.sources.item(row)
        if item is not None:
            self.model.set_filter(self.model.current_filter, source_id=item.data(Qt.ItemDataRole.UserRole))
            self._after_filter()

    def _on_filter_changed(self, row: int) -> None:
        item = self.filters.item(row)
        if item is not None:
            self.model.set_filter(item.data(Qt.ItemDataRole.UserRole), min_rating=3)
            self._after_filter()

    def _after_filter(self) -> None:
        self._update_counts()
        self._update_empty_state()
        if self.model.rowCount():
            self.select_row(0)
        else:
            self.inspector.show_record(None)

    def _refresh_sidebar(self) -> None:
        self.sources.blockSignals(True)
        self.sources.clear()
        all_item = QListWidgetItem("Tất cả thư mục")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.sources.addItem(all_item)
        if self.project is not None:
            for r in self.project.conn.execute("SELECT id, root_path FROM sources ORDER BY id"):
                item = QListWidgetItem(Path(r["root_path"]).name)
                item.setToolTip(r["root_path"])
                item.setData(Qt.ItemDataRole.UserRole, r["id"])
                self.sources.addItem(item)
        self.sources.setCurrentRow(0)
        self.sources.blockSignals(False)
        self._update_counts()

    def _update_counts(self) -> None:
        if self.project is None:
            self.counts.setText("")
            return
        c = self.project.conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(d.flag = 'keep') AS keep, SUM(d.flag = 'reject') AS reject,
                      SUM(a.status = 'error') AS errors
               FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
               WHERE a.status NOT IN ('missing', 'duplicate')
                 AND NOT (a.media_kind = 'raster' AND a.pair_group_id IS NOT NULL)"""
        ).fetchone()
        self.counts.setText(
            f"Đang hiện {self.model.rowCount()}  ·  Tổng {c['total'] or 0}  ·  Giữ {c['keep'] or 0}"
            f"  ·  Loại {c['reject'] or 0}  ·  Lỗi {c['errors'] or 0}"
        )

    def _update_empty_state(self) -> None:
        has_rows = self.model.rowCount() > 0 or (self.project is not None and self.model.current_filter is not Filter.ALL)
        if not has_rows:
            self.center.setCurrentIndex(0)
        elif self.center.currentIndex() == 0:
            self.center.setCurrentIndex(1)

    # ------------------------------------------------------------ loupe
    def toggle_loupe(self) -> None:
        self.show_loupe(self.center.currentIndex() != 2)

    def show_loupe(self, on: bool) -> None:
        if on:
            rec = self.current_record()
            if rec is None:
                return
            self.center.setCurrentIndex(2)
            self.viewer.show_photo(rec.path, self.model.pixmap(rec))
            self.filmstrip.scrollTo(self.grid.currentIndex())
        elif self.center.currentIndex() == 2:
            self.center.setCurrentIndex(1)
            self.grid.scrollTo(self.grid.currentIndex())
            self.grid.setFocus()

    def toggle_zoom(self) -> None:
        if self.center.currentIndex() != 2:
            self.show_loupe(True)
        self.viewer.toggle_zoom()

    # --------------------------------------------------------- culling
    def _targets(self) -> list[AssetRecord]:
        if self.center.currentIndex() == 2:
            rec = self.current_record()
            return [rec] if rec else []
        return self.selected_records() or ([self.current_record()] if self.current_record() else [])

    def _apply(self, fn: object, *, advance: bool = False) -> None:
        if self.project is None:
            return
        targets = self._targets()
        if not targets:
            return
        with self.project.transaction() as conn:
            for rec in targets:
                fn(conn, rec)  # type: ignore[operator]
        for rec in targets:
            self.model.refresh_record(rec.id)
        current = self.current_record()
        self.inspector.show_record(current)
        self._update_counts()
        if advance and len(targets) == 1 and self.act_auto_advance.isChecked():
            self.step(1)

    def set_flag(self, flag: str | None) -> None:
        self._apply(lambda conn, rec: decisions.set_flag(conn, rec.id, flag), advance=flag is not None)

    def set_rating(self, rating: int) -> None:
        self._apply(lambda conn, rec: decisions.set_rating(conn, rec.id, rating))

    def toggle_favorite(self) -> None:
        targets = self._targets()
        new = not all(r.favorite for r in targets) if targets else True
        self._apply(lambda conn, rec: decisions.set_favorite(conn, rec.id, new))

    # ----------------------------------------------------------- export
    def open_export_dialog(self) -> ExportDialog | None:
        if self.project is None:
            QMessageBox.information(self, "Xuất ảnh", "Hãy nhập một thư mục ảnh trước.")
            return None
        dialog = ExportDialog(self.project, [r.id for r in self.selected_records()], self)
        dialog.show()
        return dialog

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self, "Phím tắt",
            "← / →   ảnh trước / sau (↑ ↓ trong lưới)\n"
            "Space / Enter   xem lớn ↔ lưới,  Esc   về lưới\n"
            "Z   zoom 100% (ảnh độ phân giải đầy đủ) ↔ vừa khung\n"
            "K   Giữ      X   Loại      U   bỏ đánh dấu\n"
            "1 – 5   chấm sao,  0   xoá sao\n"
            "F   Yêu thích\n"
            "Ctrl+I   nhập thư mục,  Ctrl+E   xuất ảnh,  Ctrl+O   mở dự án\n\n"
            "Trong lưới có thể chọn nhiều ảnh (Ctrl/Shift + click) rồi bấm K/X/số để áp dụng cho tất cả.",
        )
