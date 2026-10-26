"""Main window: folders/filters | grid or loupe | inspector, plus import/export."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QSettings, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.storage import decisions
from app.storage.project import Project
from app.storage.sessions import delete_session, open_session, purge_old_sessions
from app.selection.client_list import delete_collection, list_collections
from app.ui.asset_model import ROLE_RECORD, AssetListModel, AssetRecord, Filter
from app.ui.client_list_dialog import ClientListDialog
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


def sessions_dir() -> Path:
    """Hidden per-folder session data (database + thumbnails), never shown as 'projects'."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    return Path(base or Path.home() / ".snorlu") / "sessions"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"Snorlu AI Culling {__version__}")
        self.settings = settings or QSettings("Snorlu", "AI Culling")
        self.project: Project | None = None
        self._session_root: Path | None = None
        self._restored_note = ""
        self.import_thread: ImportThread | None = None
        self._last_import_root: Path | None = None
        self.model = AssetListModel(self)

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._build_shortcuts()

        self._restore_geometry()

        self._reload_timer = QTimer(self)
        self._reload_timer.setInterval(_RELOAD_DURING_IMPORT_MS)
        self._reload_timer.timeout.connect(self.reload_preserving_view)

        # Every start is a fresh, empty session; old remembered folders expire.
        try:
            removed = purge_old_sessions(sessions_dir())
            if removed:
                log.info("purged %d expired sessions", len(removed))
        except OSError:
            log.exception("session purge failed")
        self._update_empty_state()

    # ------------------------------------------------------------ layout
    def _restore_geometry(self) -> None:
        """Reuse the user's last window size; otherwise fit the screen's usable area.

        A fixed size can exceed the usable height on scaled laptop displays
        (e.g. 1920x1080 at 125-150%), hiding the status bar behind the taskbar.
        """
        saved = self.settings.value("geometry")
        if saved is not None and self.restoreGeometry(saved):
            return
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.resize(min(1500, area.width()), min(900, area.height()))
        self._maximize_on_show = True

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if getattr(self, "_maximize_on_show", False):
            self._maximize_on_show = False
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Chính", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        self.act_import = QAction("📂 Nhập ảnh", self)
        self.act_import.setToolTip("Nhập một thư mục ảnh (Ctrl+I)")
        self.act_import.setShortcut(QKeySequence("Ctrl+I"))
        self.act_import.triggered.connect(self.choose_and_import)
        self.act_reset = QAction("↺ Làm lại", self)
        self.act_reset.setToolTip("Quên các dấu Giữ/Loại/sao và danh sách khách của thư mục này, nhập lại từ đầu")
        self.act_reset.triggered.connect(self.reset_current_folder)
        self.act_export = QAction("⤴ Xuất ảnh", self)
        self.act_export.setToolTip("Sao chép ảnh đã chọn sang thư mục khác (Ctrl+E)")
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.triggered.connect(self.open_export_dialog)
        self.act_loupe = QAction("🔍 Xem lớn", self)
        self.act_loupe.setToolTip("Xem ảnh lớn ↔ lưới (Space)")
        self.act_loupe.triggered.connect(self.toggle_loupe)
        self.act_auto_advance = QAction("Tự chuyển ảnh", self)
        self.act_auto_advance.setToolTip("Bật: bấm K/X xong tự sang ảnh kế tiếp")
        self.act_auto_advance.setCheckable(True)
        self.act_auto_advance.setChecked(self.settings.value("auto_advance", False, bool))
        self.act_auto_advance.toggled.connect(lambda on: self.settings.setValue("auto_advance", on))
        self.act_help = QAction("Phím tắt", self)
        self.act_help.triggered.connect(self.show_shortcuts)
        self.act_client_list = QAction("📋 Khách chọn", self)
        self.act_client_list.setToolTip("Dán danh sách ảnh khách chọn, app tự chọn ảnh theo tên (Ctrl+L)")
        self.act_client_list.setShortcut(QKeySequence("Ctrl+L"))
        self.act_client_list.triggered.connect(self.open_client_list_dialog)
        for act in (self.act_import, self.act_client_list, self.act_export, self.act_loupe, self.act_reset):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_auto_advance)
        tb.addAction(self.act_help)
        # The search box lives at the top of the sidebar (always visible; a toolbar
        # would hide it in its overflow menu on narrow or scaled screens).
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Tìm tên file (Ctrl+F)")
        self.search.setToolTip("Gõ một phần tên file. Nhiều số cách nhau bằng dấu cách, vd: 9645 9650")
        self.search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self, singleShot=True, interval=200)
        self._search_timer.timeout.connect(self._apply_search)
        self.search.textChanged.connect(self._search_timer.start)
        self.search.returnPressed.connect(self._leave_search)
        focus_search = QAction(self)
        focus_search.setShortcut(QKeySequence("Ctrl+F"))
        focus_search.triggered.connect(lambda: (self.search.setFocus(), self.search.selectAll()))
        self.addAction(focus_search)

    def _build_body(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 6, 6, 6)
        side_layout.addWidget(self.search)
        t1 = QLabel("THƯ MỤC")
        t1.setObjectName("sectionTitle")
        self.sources = QListWidget()
        self.sources.setMaximumHeight(180)
        self.sources.setMinimumHeight(60)
        self.sources.currentRowChanged.connect(self._on_source_changed)
        t2 = QLabel("LỌC")
        t2.setObjectName("sectionTitle")
        self.filters = QListWidget()
        self.filters.currentRowChanged.connect(self._on_filter_changed)
        self.filters.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.filters.customContextMenuRequested.connect(self._filter_context_menu)
        self._fill_filters()
        for w in (t1, self.sources, t2, self.filters):
            side_layout.addWidget(w)
        side_layout.addStretch(1)
        side.setMinimumWidth(190)

        self.center = QStackedWidget()
        self.empty_hint = QLabel(
            "Chưa có ảnh.\n\nBấm  “📂 Nhập ảnh”  (Ctrl+I) để bắt đầu.\n"
            "Ảnh gốc chỉ được đọc, không bao giờ bị sửa hay xoá."
        )
        self.empty_hint.setObjectName("emptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setWordWrap(True)  # long text must never set the window's minimum width
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
        # Scrollable so the window can shrink to small/scaled screens (e.g. 1080p at 150%).
        inspector_scroll = QScrollArea()
        inspector_scroll.setWidget(self.inspector)
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter.addWidget(side)
        splitter.addWidget(self.center)
        splitter.addWidget(inspector_scroll)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 1000, 290])
        self.setCentralWidget(splitter)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self.status = QLabel("Sẵn sàng")
        # Status messages can be long; let them be cut instead of widening the window.
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
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

    # ---------------------------------------------------------- sessions
    def _set_project(self, project: Project, photo_root: Path) -> None:
        if self.project is not None:
            self.project.close()
        self.project = project
        self._session_root = photo_root
        self.setWindowTitle(f"{photo_root.name or photo_root} — Snorlu AI Culling {__version__}")
        self.search.clear()
        self.model.set_search("")
        self.model.set_project(project)
        self._fill_filters()
        self._refresh_sidebar()
        self._update_empty_state()
        if self.model.rowCount():
            self.select_row(0)

    def _close_session(self) -> None:
        for dialog in self.findChildren(QDialog):
            dialog.close()
        self.viewer.show_photo(None)
        self.viewer.wait_idle(10000)
        self.model.wait_for_thumbnails(10000)  # Windows cannot delete files still being read
        self.model.set_project(None)
        if self.project is not None:
            self.project.close()
        self.project = None
        self._session_root = None

    def _remembered_summary(self) -> str:
        assert self.project is not None
        c = self.project.conn.execute(
            """SELECT SUM(flag = 'keep') AS k, SUM(flag = 'reject') AS x, SUM(rating > 0) AS r
               FROM decisions WHERE subject_id IS NULL"""
        ).fetchone()
        lists = len(list_collections(self.project.conn))
        parts = [f"{c['k'] or 0} Giữ", f"{c['x'] or 0} Loại", f"{c['r'] or 0} có sao"]
        if lists:
            parts.append(f"{lists} danh sách khách")
        return ", ".join(parts)

    def reset_current_folder(self) -> None:
        if self.project is None or self._session_root is None or self.import_thread is not None:
            return
        root = self._session_root
        answer = QMessageBox.question(
            self, "Làm lại từ đầu",
            f"Quên mọi dấu Giữ/Loại, sao, yêu thích và danh sách khách của thư mục\n{root}\n"
            "rồi nhập lại từ đầu?\n\nẢnh gốc không bị ảnh hưởng. Ảnh đã xuất ra thư mục khác vẫn còn nguyên.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._close_session()
        try:
            delete_session(sessions_dir(), root)
        except OSError as exc:
            QMessageBox.warning(self, "Làm lại từ đầu", f"Chưa xoá được dữ liệu cũ ({exc}). Hãy thử lại.")
        self.start_import(root)

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
        root = root.resolve()
        if self.project is None or self._session_root != root:
            # One session per photo folder: switching folders closes the current one.
            self._close_session()
            project, restored = open_session(sessions_dir(), root)
            self._set_project(project, root)
            self._restored_note = (
                f"Đã nhớ từ lần trước: {self._remembered_summary()}." if restored else ""
            )
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
            self.status.setText(", ".join(parts) + ". " + self._restored_note)

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

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        self.settings.setValue("geometry", self.saveGeometry())
        for dialog in self.findChildren(QDialog):  # they use the project database
            dialog.close()
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

    def _fill_filters(self, select_collection: int | None = None) -> None:
        """Fixed filters, then one entry per client list (UserRole = (Filter, collection id))."""
        self.filters.blockSignals(True)
        self.filters.clear()
        for flt, text in _FILTERS:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (flt, None))
            self.filters.addItem(item)
        current = 0
        if self.project is not None:
            collections = list_collections(self.project.conn)
            if collections:
                header = QListWidgetItem("DANH SÁCH KHÁCH")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.filters.addItem(header)
            for c in collections:
                item = QListWidgetItem(f"📋 {c['name']} ({c['n']})")
                item.setToolTip("Chuột phải để xoá danh sách (ảnh không bị ảnh hưởng)")
                item.setData(Qt.ItemDataRole.UserRole, (Filter.COLLECTION, c["id"]))
                self.filters.addItem(item)
                if c["id"] == select_collection:
                    current = self.filters.count() - 1
        self.filters.setCurrentRow(current)
        self.filters.blockSignals(False)

    def _on_filter_changed(self, row: int) -> None:
        item = self.filters.item(row)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if data is not None:
            flt, collection_id = data
            self.model.set_filter(flt, min_rating=3, collection_id=collection_id)
            self._after_filter()

    def _filter_context_menu(self, pos: object) -> None:
        item = self.filters.itemAt(pos)  # type: ignore[arg-type]
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if self.project is None or data is None or data[0] is not Filter.COLLECTION:
            return
        menu = QMenu(self)
        delete = menu.addAction("Xoá danh sách này (ảnh không bị ảnh hưởng)")
        if menu.exec(self.filters.mapToGlobal(pos)) is delete:  # type: ignore[arg-type]
            delete_collection(self.project.conn, data[1])
            self._fill_filters()
            self._on_filter_changed(0)

    def _apply_search(self) -> None:
        self.model.set_search(self.search.text())
        self._after_filter()

    def _leave_search(self) -> None:
        self.grid.setFocus()
        if self.center.currentIndex() == 0:
            return
        if not self.grid.currentIndex().isValid() and self.model.rowCount():
            self.select_row(0)

    def open_client_list_dialog(self) -> ClientListDialog | None:
        if self.project is None:
            QMessageBox.information(self, "Danh sách khách", "Hãy nhập một thư mục ảnh trước.")
            return None
        source = self.sources.currentItem()
        dialog = ClientListDialog(
            self.project, self, source_id=source.data(Qt.ItemDataRole.UserRole) if source else None
        )
        dialog.accepted.connect(lambda: self._show_collection(dialog.collection_id))
        dialog.show()
        return dialog

    def _show_collection(self, collection_id: int | None) -> None:
        """After creating a client list: show it and select all its photos (ready for export)."""
        if collection_id is None:
            return
        self.search.clear()
        self.model.set_search("")
        self._fill_filters(select_collection=collection_id)
        self._on_filter_changed(self.filters.currentRow())
        self.grid.selectAll()
        self.status.setText(f"Đã tạo danh sách khách: {self.model.rowCount()} ảnh. Bấm “Xuất ảnh” để chép.")

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
        has_rows = self.model.rowCount() > 0 or (self.project is not None and self.model.is_filtered)
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
        item = self.filters.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        collection_id = data[1] if data and data[0] is Filter.COLLECTION else None
        dialog = ExportDialog(self.project, [r.id for r in self.selected_records()], self, collection_id=collection_id)
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
            "Ctrl+I   nhập thư mục ảnh,  Ctrl+E   xuất ảnh\n"
            "Ctrl+F   tìm tên file,  Ctrl+L   danh sách khách chọn\n\n"
            "Trong lưới có thể chọn nhiều ảnh (Ctrl/Shift + click) rồi bấm K/X/số để áp dụng cho tất cả.",
        )
