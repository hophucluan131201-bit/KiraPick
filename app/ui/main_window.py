"""Main window: folders/filters | grid or loupe | inspector, plus import/export."""

from __future__ import annotations

import json
from collections.abc import Callable
import logging
import time
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPointF, QSettings, QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QGuiApplication, QIcon, QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QInputDialog,
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
from app.branding import APP_NAME, SETTINGS_IDS, data_dir
from app.storage import decisions
from app.storage.project import Project
from app.storage.sessions import delete_session, open_session, purge_old_sessions
from app.ai.models import ModelRegistry
from app.identity import actions
from app.identity.cluster import merge_suggestions
from app.learning.store import LearningStore
from app.quality import select
from app.learning.teacher import Teacher
from app.selection.client_list import delete_collection, list_collections
from app.ui.asset_model import ROLE_RECORD, AssetListModel, AssetRecord, Filter, Sort
from app.ui.client_list_dialog import ClientListDialog
from app.ui.export_dialog import ExportDialog
from app.ui.grid import make_filmstrip, make_grid
from app.ui.inspector import Inspector
from app.ui.review_dialog import ReviewDialog
from app.ui.select_dialog import SelectDialog
from app.ui.jobs import AnalyzeThread, ImportThread
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
    return data_dir() / "sessions"


_KEYS_GRID = [
    ("Space / Enter", "xem ảnh lớn"), ("← → ↑ ↓", "di chuyển"), ("K", "giữ"), ("X", "loại"), ("U", "bỏ đánh dấu"),
    ("1–5 / 0", "sao / xoá sao"), ("F", "yêu thích"), ("Ctrl/Shift + click", "chọn nhiều ảnh"),
    ("Ctrl+A", "chọn tất cả"), ("Ctrl+F", "tìm tên file"), ("Ctrl+E", "xuất ảnh"), ("F1", "tất cả phím tắt"),
]
_KEYS_LOUPE = [
    ("Esc", "về lưới ảnh"), ("← →", "ảnh trước / sau"), ("Z", "100% ↔ vừa khung"), ("E", "phóng tới mắt"),
    ("+ / − / cuộn chuột", "phóng to / nhỏ"), ("nháy đúp", "100% tại chỗ đó"), ("kéo chuột", "di chuyển ảnh"),
    ("K", "giữ"), ("X", "loại"), ("U", "bỏ đánh dấu"), ("1–5", "sao"), ("F", "yêu thích"),
]


def key_hints_html(loupe: bool) -> str:
    """One compact line of key chips for the current view."""
    chip = ("<span style='background-color:#3a3d42; color:#e8eaed;'>&nbsp;{}&nbsp;</span>"
            "&nbsp;<span style='color:#9aa0a6;'>{}</span>")
    items = _KEYS_LOUPE if loupe else _KEYS_GRID
    nb = lambda text: text.replace(" ", "&nbsp;")  # noqa: E731 - a key and its meaning never wrap apart
    return "<b>Phím tắt</b>&nbsp;&nbsp; " + " &nbsp; ".join(chip.format(nb(k), nb(v)) for k, v in items)


def _duration(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60} phút {seconds % 60} giây" if seconds >= 60 else f"{seconds} giây"


def _long_side(rec: AssetRecord) -> int | None:
    return max(rec.width or 0, rec.height or 0) or None


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.settings = settings or QSettings(*SETTINGS_IDS)
        self.project: Project | None = None
        self._session_root: Path | None = None
        self._restored_note = ""
        self.import_thread: ImportThread | None = None
        self.analyze_thread: AnalyzeThread | None = None
        self._paused_job: str | None = None  # "import" | "people" | "quality"
        self._registry: ModelRegistry | None = None
        self._last_import_root: Path | None = None
        self.model = AssetListModel(self)
        self.teacher = Teacher(self._open_learning())

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._build_shortcuts()
        self._update_steps()

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
        # The workflow goes step by step; each step waits for the user (and their corrections).
        self.act_analyze = QAction("🧠 Nhận diện chủ thể", self)
        self.act_analyze.setToolTip("Bước 2: AI tìm các chủ thể trong ảnh và gom ảnh theo từng chủ thể. Xong thì dừng để bạn "
                                    "kiểm tra, gộp/tách cho đúng.")
        self.act_analyze.triggered.connect(lambda: self.start_analysis("people"))
        self.act_quality = QAction("📊 Phân tích ảnh", self)
        self.act_quality.triggered.connect(lambda: self.start_analysis("quality"))
        self.act_reset = QAction("↺ Làm lại", self)
        self.act_reset.setToolTip("Quên các dấu Giữ/Loại/sao và danh sách khách của thư mục này, nhập lại từ đầu")
        self.act_reset.triggered.connect(self.reset_current_folder)
        self.act_export = QAction("⤴ Xuất ảnh", self)
        self.act_export.setToolTip("Sao chép ảnh đã chọn sang thư mục khác (Ctrl+E)")
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.triggered.connect(self.open_export_dialog)
        # View switch: two buttons, the active one stays highlighted.
        self.act_grid_view = QAction("▦ Lưới ảnh", self)
        self.act_grid_view.setToolTip("Xem nhiều ảnh dạng lưới (Esc)")
        self.act_grid_view.setCheckable(True)
        self.act_grid_view.triggered.connect(lambda: self.show_loupe(False))
        self.act_loupe = QAction("🔍 Xem lớn", self)
        self.act_loupe.setToolTip("Xem một ảnh lớn, phóng to tới 800% (Space / Enter)")
        self.act_loupe.setCheckable(True)
        self.act_loupe.triggered.connect(lambda: self.show_loupe(True))
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        for act in (self.act_grid_view, self.act_loupe):
            view_group.addAction(act)
        self.act_grid_view.setChecked(True)
        self.act_auto_advance = QAction("Tự chuyển ảnh", self)
        self.act_auto_advance.setToolTip("Bật: bấm K/X xong tự sang ảnh kế tiếp")
        self.act_auto_advance.setCheckable(True)
        self.act_auto_advance.setChecked(self.settings.value("auto_advance", False, bool))
        self.act_auto_advance.toggled.connect(lambda on: self.settings.setValue("auto_advance", on))
        self.act_help = QAction("⌨ Phím tắt", self)
        self.act_help.setToolTip("Hiện/ẩn bảng phím tắt nhỏ dưới khu vực ảnh (F1: bảng đầy đủ)")
        self.act_help.setCheckable(True)
        self.act_help.setChecked(self.settings.value("show_key_hints", True, bool))
        self.act_help.toggled.connect(self._toggle_key_hints)
        self.act_client_list = QAction("📋 Khách chọn", self)
        self.act_client_list.setToolTip("Dán danh sách ảnh khách chọn, app tự chọn ảnh theo tên (Ctrl+L)")
        self.act_client_list.setShortcut(QKeySequence("Ctrl+L"))
        self.act_client_list.triggered.connect(self.open_client_list_dialog)
        self.act_merge = QAction("🔗 Gộp chủ thể", self)
        self.act_merge.setToolTip("Tick ô vuông cạnh 2 chủ thể trở lên trong danh sách CHỦ THỂ, rồi bấm để gộp thành một chủ thể")
        self.act_merge.setEnabled(False)
        self.act_merge.triggered.connect(lambda: self.merge_selected_people())
        self.act_select = QAction("⭐ Chọn ảnh", self)
        self.act_select.triggered.connect(lambda: self.open_select_dialog())
        for act in (self.act_import, self.act_analyze, self.act_merge, self.act_quality, self.act_select,
                    self.act_client_list, self.act_export):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_grid_view)
        tb.addAction(self.act_loupe)
        tb.addSeparator()
        tb.addAction(self.act_reset)
        self.act_learning = QAction("🎓 AI đã học", self)
        self.act_learning.setToolTip("Xem AI đã học gì từ các lần bạn sửa (chỉ trên máy này), hoặc xoá để học lại")
        self.act_learning.triggered.connect(self.show_learning)
        tb.addAction(self.act_learning)
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
        self.sort = QComboBox()
        for label, mode in (("Xếp theo thời gian chụp", Sort.TIME), ("Xếp theo điểm (cao → thấp)", Sort.SCORE),
                            ("Ảnh AI chọn trước, rồi theo điểm", Sort.PICKS_FIRST)):
            self.sort.addItem(label, mode.value)
        self.sort.currentIndexChanged.connect(lambda _i: self._on_sort_changed())
        side_layout.addWidget(self.sort)
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
        t3 = QLabel("CHỦ THỂ")
        t3.setObjectName("sectionTitle")
        self.people = QListWidget()
        self.people.setIconSize(QSize(36, 36))
        self.people.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.people.setToolTip("Bấm để xem ảnh của chủ thể này. Nháy đúp để đặt tên. "
                               "Tick ô vuông cạnh nhiều chủ thể rồi bấm 🔗 Gộp chủ thể để gộp.")
        self.people.itemChanged.connect(lambda _item: self._update_merge_action())
        self.people.itemSelectionChanged.connect(self._update_merge_action)
        self.people.currentRowChanged.connect(self._on_person_changed)
        self.people.itemDoubleClicked.connect(lambda _item: self.rename_current_person())
        self.people.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.people.customContextMenuRequested.connect(self._people_context_menu)
        self.people_sort = QComboBox()
        self.people_sort.setToolTip("Cách xếp danh sách chủ thể")
        for key, label in actions.PEOPLE_ORDERS.items():
            self.people_sort.addItem(label, key)
        saved = self.settings.value("people_sort", "number", str)
        self.people_sort.setCurrentIndex(max(0, self.people_sort.findData(saved)))
        self.people_sort.currentIndexChanged.connect(self._on_people_sort_changed)
        for w in (t1, self.sources, t2, self.filters, t3, self.people_sort, self.people):
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
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._grid_context_menu)

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
        self.viewer.back_requested.connect(lambda: self.show_loupe(False))

        # Small cheat sheet under the photos; its content follows the current view.
        self.key_hints = QLabel()
        self.key_hints.setObjectName("keyHints")
        self.key_hints.setWordWrap(True)
        self.key_hints.setTextFormat(Qt.TextFormat.RichText)
        self.key_hints.setVisible(self.act_help.isChecked())
        center_box = QWidget()
        center_layout = QVBoxLayout(center_box)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.center, 1)
        center_layout.addWidget(self.key_hints)
        self.center.currentChanged.connect(self._on_view_changed)
        self._on_view_changed(self.center.currentIndex())

        self.inspector = Inspector()
        # Scrollable so the window can shrink to small/scaled screens (e.g. 1080p at 150%).
        inspector_scroll = QScrollArea()
        inspector_scroll.setWidget(self.inspector)
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter.addWidget(side)
        splitter.addWidget(center_box)
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
        sc("+", lambda: self.zoom_step(1))
        sc("=", lambda: self.zoom_step(1))
        sc("-", lambda: self.zoom_step(-1))
        sc("E", self.zoom_to_eyes)
        sc("F1", self.show_shortcuts)

    # ---------------------------------------------------------- sessions
    def _set_project(self, project: Project, photo_root: Path) -> None:
        if self.project is not None:
            self.project.close()
        self.project = project
        self._session_root = photo_root
        self.setWindowTitle(f"{photo_root.name or photo_root} — {APP_NAME} {__version__}")
        self.search.clear()
        self.model.set_search("")
        self.model.set_project(project)
        self._fill_filters()
        self._fill_people()
        self._refresh_sidebar()
        self._update_empty_state()
        self._update_steps()
        if self.model.rowCount():
            self.select_row(0)

    def _close_session(self) -> None:
        self._stop_analysis()
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
        self._paused_job = None
        self._fill_people()
        self._update_steps()

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
        self._stop_analysis()
        self._paused_job = None
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
        self._update_steps()
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
        if self.sender() is not self.import_thread:
            return
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
        if self.sender() is not self.import_thread or self.project is None:
            return  # window closed meanwhile
        cancelled = self.import_thread is not None and self.import_thread.cancel_requested
        self.import_thread = None
        self._reload_timer.stop()
        self.progress.setVisible(False)
        self.act_import.setEnabled(True)
        if cancelled:
            self._paused_job = "import"
            self.pause_button.setText("Tiếp tục")
            self.pause_button.setEnabled(True)
        else:
            self.pause_button.setVisible(False)
        self.reload_preserving_view()
        self._refresh_sidebar()
        self._update_empty_state()
        if not self.grid.currentIndex().isValid() and self.model.rowCount():
            self.select_row(0)
        self._update_steps()
        if not cancelled and self.project is not None:
            self.status.setText(self.status.text().rstrip(". ") + ". Bước tiếp theo: bấm 🧠 Nhận diện chủ thể.")

    def _pause_or_resume(self) -> None:
        running = self.import_thread or self.analyze_thread
        if running is not None:
            running.cancel()
            self.pause_button.setEnabled(False)
            self.status.setText("Đang tạm dừng…")
        elif self._paused_job in ("people", "quality"):
            self.start_analysis(self._paused_job)
        elif self._last_import_root is not None:
            self.start_import(self._last_import_root)

    def learning_text(self) -> str:
        """What this user's corrections taught the app (for the 🎓 dialog)."""
        from app.identity.cluster import ARCFACE_REID, SFACE_HSV, session_profile
        from app.learning.tuning import tune

        store = self.teacher.store
        if store is None:
            return "Không mở được dữ liệu học trên máy này; app dùng mức mặc định."
        counts = store.identity_counts()
        base = session_profile(self.project.conn) if self.project is not None else (
            ARCFACE_REID if (self._registry or ModelRegistry()).ready("identity_plus") else SFACE_HSV)
        tuning = tune(store.identity_examples(), base)
        lines = [
            "<b>Nhận diện chủ thể</b>",
            f"Đã ghi {counts['same']} cặp ảnh “cùng chủ thể” và {counts['different']} cặp “khác chủ thể” "
            "từ các lần bạn gộp / tách / bỏ ảnh.",
            tuning.describe() if tuning.applied else tuning.reason,
            "Áp dụng ở lần bấm 🧠 Nhận diện chủ thể tiếp theo.",
            "",
            "<b>Gu chọn ảnh</b>",
            f"Đã ghi {store.culling_count()} lần bạn bấm Giữ/Loại (dùng cho các bản sau).",
            "",
            "Dữ liệu học chỉ có số đo độ giống, không có ảnh, tên file hay tên chủ thể, "
            "và chỉ nằm trên máy này.",
        ]
        return "<br>".join(lines)

    def show_learning(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("AI đã học")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(self.learning_text())
        forget = box.addButton("Xoá dữ liệu học…", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
        forget.setEnabled(self.teacher.store is not None)
        box.exec()
        if box.clickedButton() is not forget or self.teacher.store is None:
            return
        sure = QMessageBox.question(
            self, "Xoá dữ liệu học",
            "Xoá mọi thứ AI đã học từ các lần bạn sửa trên máy này? App sẽ quay về mức mặc định.\n"
            "Ảnh và các thư mục đã nhập không bị ảnh hưởng.")
        if sure == QMessageBox.StandardButton.Yes:
            self.teacher.store.forget()
            self.status.setText("Đã xoá dữ liệu học. Bấm 🧠 Nhận diện chủ thể để gom lại theo mức mặc định.")

    @staticmethod
    def _learning_dir() -> Path:
        return sessions_dir().parent / "learning"

    @staticmethod
    def _open_learning() -> LearningStore | None:
        """This user's learning data (never shared with the app); optional."""
        try:
            return LearningStore(MainWindow._learning_dir())
        except Exception:  # noqa: BLE001 - the app works without it
            log.exception("learning data unavailable")
            return None

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        self.settings.setValue("geometry", self.saveGeometry())
        for dialog in self.findChildren(QDialog):  # they use the project database
            dialog.close()
        if self.import_thread is not None:
            thread, self.import_thread = self.import_thread, None
            thread.cancel()
            thread.wait(15000)  # resumable: unfinished files continue next time
        self._stop_analysis()
        self.viewer.wait_idle(5000)
        if self.project is not None:
            self.project.close()
        if self.teacher.store is not None:
            self.teacher.store.close()
            self.teacher.store = None
        super().closeEvent(event)

    # ------------------------------------------------------------ people (AI)
    def models_ready(self) -> bool:
        if self._registry is None:
            self._registry = ModelRegistry()
        return self._registry.ready("identity")

    def _step_state(self) -> tuple[int, int, int]:
        """(photos, photos with people detected, photos scored) of the current folder."""
        if self.project is None:
            return 0, 0, 0
        conn = self.project.conn
        photos = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'ok'").fetchone()[0]
        detected = conn.execute(
            "SELECT COUNT(*) FROM stage_status WHERE stage = 'detect' AND state = 'done'").fetchone()[0]
        scored = conn.execute(
            "SELECT COUNT(DISTINCT asset_id) FROM measurements WHERE extractor = 'quality'").fetchone()[0]
        return photos, detected, scored

    def _update_steps(self) -> None:
        """Enable each step only when the previous one is done and nothing is running."""
        busy = self.import_thread is not None or self.analyze_thread is not None
        photos, detected, scored = self._step_state()
        self.act_analyze.setEnabled(not busy and photos > 0)
        self.act_quality.setEnabled(not busy and detected > 0)
        self.act_select.setEnabled(not busy and scored > 0)
        self.act_quality.setToolTip(
            "Bước 3: chấm điểm từng chủ thể trong ảnh (nét ở mắt, mặt, sáng, bố cục)."
            + ("" if detected else " Hãy bấm 🧠 Nhận diện chủ thể trước."))
        self.act_select.setToolTip(
            "Bước 4: AI chọn N ảnh đẹp, khác dáng nhau; bạn xem lại rồi ⤴ Xuất ảnh."
            + ("" if scored else " Hãy bấm 📊 Phân tích ảnh trước."))

    def start_analysis(self, mode: str = "people") -> AnalyzeThread | None:
        if self.project is None or self.import_thread is not None or self.analyze_thread is not None:
            return None
        thread = AnalyzeThread(self.project.folder, mode, self._learning_dir())
        self._analysis_started = time.monotonic()
        self._run_device = None
        thread.progress.connect(self._on_analyze_progress)
        thread.succeeded.connect(self._on_analyze_done)
        title = "Nhận diện chủ thể" if mode == "people" else "Phân tích ảnh"
        thread.failed.connect(lambda msg: QMessageBox.warning(self, title, msg))
        thread.finished.connect(self._on_analyze_thread_finished)
        self.analyze_thread = thread
        self._paused_job = None
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.pause_button.setText("Tạm dừng")
        self.pause_button.setVisible(True)
        self.pause_button.setEnabled(True)
        thread.start()
        self._update_steps()
        return thread

    def _stop_analysis(self) -> None:
        """Stop and forget the analysis thread; its queued signals are ignored afterwards."""
        thread = self.analyze_thread
        if thread is None:
            return
        self.analyze_thread = None
        thread.cancel()
        thread.wait(30000)
        self._update_steps()
        if self.import_thread is None:
            self.progress.setVisible(False)
            self.pause_button.setVisible(False)

    def _on_analyze_progress(self, phase: str, done: int, total: int) -> None:
        if phase.startswith("device:"):  # where the AI runs, shown with every progress message
            self._run_device = {"cuda": "GPU NVIDIA", "directml": "GPU DirectML"}.get(phase[7:], "CPU")
            return
        label = {"load_models": "Đang nạp mô hình AI…", "detect": "Đang nhận diện chủ thể…",
                 "embed": "Đang so khuôn mặt và dáng người (ArcFace + ReID)…",
                 "quality": "Đang chấm điểm ảnh (độ nét đo trên ảnh gốc)…",
                 "group": "Đang gom ảnh theo chủ thể…"}.get(phase, phase)
        if total and phase in ("detect", "embed", "quality"):
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            where = f" [{self._run_device}]" if getattr(self, "_run_device", None) else ""
            self.status.setText(f"{label} {done}/{total}{where}")
        else:
            self.progress.setRange(0, 0)
            self.status.setText(label)

    def _on_analyze_done(self, summary: dict) -> None:
        if self.sender() is not self.analyze_thread or self.project is None:
            return  # a stopped thread (closing window / switching folder)
        if summary["cancelled"]:
            done = summary["analysed"] if summary.get("mode") != "quality" else summary["measured"]
            self.status.setText(f"Đã tạm dừng ({done} ảnh xong). Bấm “Tiếp tục” để làm tiếp.")
            return
        assert self.project is not None
        if summary.get("mode") == "quality":
            took = _duration(time.monotonic() - getattr(self, "_analysis_started", time.monotonic()))
            device = {"cuda": "GPU NVIDIA", "directml": "GPU DirectML"}.get(summary["device"], "CPU")
            parts = [f"Phân tích xong ({device}, {took}): {self._step_state()[2]} ảnh có điểm"]
            if summary.get("measure_failed"):
                parts.append(f"{summary['measure_failed']} ảnh không chấm được")
            self.status.setText(", ".join(parts) + ". Bước tiếp theo: bấm ⭐ Chọn ảnh, hoặc xếp theo điểm.")
            return
        people = self.project.conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        unknown = self.project.conn.execute(
            f"SELECT COUNT(*) FROM ({actions.UNIDENTIFIED_ASSETS})").fetchone()[0]
        review = len(merge_suggestions(self.project.conn))
        device = {"cuda": "GPU NVIDIA", "directml": "GPU DirectML"}.get(summary["device"], "CPU")
        device += f", {_duration(time.monotonic() - getattr(self, '_analysis_started', time.monotonic()))}"
        parts = [f"Nhận diện xong ({device}): {people} chủ thể", f"{unknown} ảnh chưa xác định"]
        if review:
            parts.append(f"{review} gợi ý cần xem lại")
        if summary["failed"]:
            parts.append(f"{summary['failed']} ảnh lỗi")
        note = f" ({summary['fallback_reason']})" if summary.get("fallback_reason") else ""
        if summary.get("learning"):
            note += f" {summary['learning']}"
        self.status.setText(", ".join(parts) + "." + note
                            + " Hãy kiểm tra, gộp/tách chủ thể cho đúng, rồi bấm 📊 Phân tích ảnh.")

    def _on_analyze_thread_finished(self) -> None:
        if self.sender() is not self.analyze_thread:
            return  # stopped via _stop_analysis; the window may already have closed the database
        cancelled = self.analyze_thread is not None and self.analyze_thread.cancel_requested
        mode = self.analyze_thread.mode if self.analyze_thread is not None else "people"
        self.analyze_thread = None
        self._update_steps()
        if self.import_thread is None:
            self.progress.setVisible(False)
            if cancelled and self.project is not None:
                self._paused_job = mode
                self.pause_button.setText("Tiếp tục")
                self.pause_button.setEnabled(True)
            else:
                self.pause_button.setVisible(False)
        if self.project is not None:
            self._fill_people()
            self.reload_preserving_view()
            self._show_inspector(self.current_record())

    def renumber_people(self, ask: bool = True) -> int:
        """Chủ thể 1, 2, 3 … without gaps, in shooting order (names are kept)."""
        if self.project is None:
            return 0
        if ask and QMessageBox.question(
                self, "Đánh số lại",
                "Đánh số lại các chủ thể thành 1, 2, 3… theo thời gian chụp (không còn số bị nhảy)?\n"
                "Chủ thể đã đặt tên giữ nguyên tên; ảnh và các lần sửa không bị ảnh hưởng.") != QMessageBox.StandardButton.Yes:
            return 0
        with self.project.transaction() as conn:
            changed = actions.renumber_subjects(conn)
        target = self.model.current_target
        if self.model.current_filter is Filter.SUBJECT and target in changed:
            self.model.set_filter(Filter.SUBJECT, subject_id=changed[target])  # keep showing the same person
            target = changed[target]
        self.people.blockSignals(True)
        self.people.setCurrentRow(-1)  # the old row's id may now belong to someone else
        self.people.blockSignals(False)
        self._after_people_change()
        if self.model.current_filter is Filter.SUBJECT:
            for i in range(self.people.count()):
                if self.people.item(i).data(Qt.ItemDataRole.UserRole) == ("subject", target):
                    self.people.blockSignals(True)
                    self.people.setCurrentRow(i)
                    self.people.blockSignals(False)
        self.status.setText(f"Đã đánh số lại {len(changed)} chủ thể theo thời gian chụp." if changed
                            else "Các chủ thể đã được đánh số liền nhau.")
        return len(changed)

    def _people_order(self) -> str:
        return self.people_sort.currentData() or "number"

    def _on_people_sort_changed(self) -> None:
        self.settings.setValue("people_sort", self._people_order())
        self._fill_people()

    def _fill_people(self) -> None:
        current = self.people.currentItem().data(Qt.ItemDataRole.UserRole) if self.people.currentItem() else None
        checked = set(self._checked_subjects())
        self.people.blockSignals(True)
        self.people.clear()
        if self.project is not None:
            for r in actions.subjects_summary(self.project.conn, self._people_order()):
                text = f"{r['display_name'] or f'Chủ thể {r[0]}'}  ·  {r['photos']} ảnh"
                if r["suggested"]:
                    text += f"  ·  {r['suggested']}?"
                item = QListWidgetItem(text)
                if r["avatar"]:
                    item.setIcon(QIcon(str(self.project.cache_dir / r["avatar"])))
                item.setData(Qt.ItemDataRole.UserRole, ("subject", r["id"]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if r["id"] in checked else Qt.CheckState.Unchecked)
                self.people.addItem(item)
            unknown = self.project.conn.execute(
                f"SELECT COUNT(*) FROM ({actions.UNIDENTIFIED_ASSETS})").fetchone()[0]
            if unknown:
                item = QListWidgetItem(f"❔ Chưa xác định  ·  {unknown} ảnh")
                item.setData(Qt.ItemDataRole.UserRole, ("unidentified", None))
                self.people.addItem(item)
            review = len(merge_suggestions(self.project.conn))
            if review:
                item = QListWidgetItem(f"🔎 Cần xem lại  ·  {review} gợi ý")
                item.setData(Qt.ItemDataRole.UserRole, ("review", None))
                self.people.addItem(item)
        for i in range(self.people.count()):
            if self.people.item(i).data(Qt.ItemDataRole.UserRole) == current:
                self.people.setCurrentRow(i)
        self.people.blockSignals(False)
        self._update_merge_action()

    def _on_person_changed(self, row: int) -> None:
        item = self.people.item(row)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if data is None:
            return
        kind, subject_id = data
        if kind == "review":
            self.open_review()
            return
        self.filters.blockSignals(True)
        self.filters.clearSelection()
        self.filters.setCurrentRow(-1)
        self.filters.blockSignals(False)
        if kind == "subject":
            self.model.set_filter(Filter.SUBJECT, subject_id=subject_id)
        else:
            self.model.set_filter(Filter.UNIDENTIFIED)
        self._after_filter()

    def _checked_subjects(self) -> list[int]:
        out = []
        for i in range(self.people.count()):
            item = self.people.item(i)
            kind, sid = item.data(Qt.ItemDataRole.UserRole)
            if kind == "subject" and item.checkState() == Qt.CheckState.Checked:
                out.append(sid)
        return out

    def _people_to_merge(self) -> list[int]:
        """Ticked people; without ticks, the people selected with Ctrl/Shift."""
        return self._checked_subjects() or self._selected_subjects()

    def _update_merge_action(self) -> None:
        n = len(self._people_to_merge())
        self.act_merge.setEnabled(self.project is not None and n >= 2)
        self.act_merge.setText(f"🔗 Gộp {n} chủ thể" if n >= 2 else "🔗 Gộp chủ thể")

    def _selected_subjects(self) -> list[int]:
        out = []
        for item in self.people.selectedItems():
            kind, sid = item.data(Qt.ItemDataRole.UserRole)
            if kind == "subject":
                out.append(sid)
        return out

    def rename_current_person(self) -> None:
        item = self.people.currentItem()
        if self.project is None or item is None or item.data(Qt.ItemDataRole.UserRole)[0] != "subject":
            return
        sid = item.data(Qt.ItemDataRole.UserRole)[1]
        name, ok = QInputDialog.getText(self, "Đặt tên", "Tên chủ thể này (để trống = bỏ tên):",
                                        text=actions.subject_label(self.project.conn, sid))
        if ok:
            with self.project.transaction() as conn:
                actions.rename_subject(conn, sid, name)
            self._fill_people()

    def merge_selected_people(self, ids: list[int] | None = None) -> None:
        ids = self._people_to_merge() if ids is None else ids
        if self.project is None or len(ids) < 2:
            return
        summary = {r["id"]: r for r in actions.subjects_summary(self.project.conn)}
        # Keep a named person if there is one (its name stays), otherwise the one with most photos.
        keep = max(ids, key=lambda i: (summary[i]["display_name"] is not None if i in summary else False,
                                       summary[i]["photos"] if i in summary else 0))
        names = ", ".join(actions.subject_label(self.project.conn, i) for i in ids)
        total = sum(summary[i]["photos"] for i in ids if i in summary)
        if QMessageBox.question(
                self, "Gộp chủ thể",
                f"Gộp {names} thành một chủ thể ({total} ảnh), giữ tên \"{actions.subject_label(self.project.conn, keep)}\"?\n"
                "App sẽ nhớ việc gộp này cả khi nhận diện lại.") != QMessageBox.StandardButton.Yes:
            return
        with self.project.transaction() as conn:
            for other in ids:
                if other != keep:
                    self.teacher.merged(conn, keep, other)
                actions.merge_subjects(conn, keep, other)
        self.people.blockSignals(True)
        for i in range(self.people.count()):  # merged: clear the ticks
            item = self.people.item(i)
            if item.data(Qt.ItemDataRole.UserRole)[0] == "subject":
                item.setCheckState(Qt.CheckState.Unchecked)
        self.people.blockSignals(False)
        self._after_people_change()

    def open_review(self) -> ReviewDialog | None:
        if self.project is None:
            return None
        dialog = ReviewDialog(self.project, self, teacher=self.teacher)
        dialog.changed.connect(self._after_people_change)
        dialog.show()
        return dialog

    def _after_people_change(self) -> None:
        self._fill_people()
        self.reload_preserving_view()
        self._show_inspector(self.current_record())

    def _people_context_menu(self, pos: object) -> None:
        ids = self._selected_subjects()
        if self.project is None or not ids:
            return
        menu = QMenu(self)
        rename = menu.addAction("Đặt tên…") if len(ids) == 1 else None
        merge = menu.addAction(f"Gộp {len(ids)} chủ thể này thành một") if len(ids) >= 2 else None
        different = menu.addAction("Đây là hai chủ thể khác nhau") if len(ids) == 2 else None
        menu.addSeparator()
        renumber = menu.addAction("🔢 Đánh số lại 1, 2, 3… theo thời gian chụp")
        chosen = menu.exec(self.people.mapToGlobal(pos))  # type: ignore[arg-type]
        if chosen is None:
            return
        if chosen is renumber:
            self.renumber_people()
        elif chosen is rename:
            self.rename_current_person()
        elif chosen is merge:
            self.merge_selected_people(ids)
        elif chosen is different:
            with self.project.transaction() as conn:
                self.teacher.different(conn, ids[0], ids[1])
                actions.mark_different(conn, ids[0], ids[1])
            self._fill_people()

    def _grid_context_menu(self, pos: object) -> None:
        if self.project is None:
            return
        assets = [r.id for r in self.selected_records()]
        if not assets:
            return
        menu = QMenu(self)
        flt, target = self.model.current_filter, self.model.current_target
        remove = confirm = None
        if flt is Filter.SUBJECT and target is not None:
            name = actions.subject_label(self.project.conn, target)
            confirm = menu.addAction(f"Đúng là {name}")
            remove = menu.addAction(f"Không phải {name} — bỏ khỏi chủ thể này")
        new_subject = menu.addAction("➕ Tạo chủ thể mới" + (f" từ {len(assets)} ảnh này" if len(assets) > 1 else " từ ảnh này"))
        new_subject.setToolTip("Chủ thể này chưa có trong danh sách: tạo một chủ thể riêng cho các ảnh đang chọn")
        assign_menu = menu.addMenu("Gán cho chủ thể…")
        targets = {}
        for r in actions.subjects_summary(self.project.conn, self._people_order()):  # same order as the list
            if r["id"] != target:
                targets[assign_menu.addAction(r["display_name"] or f"Chủ thể {r['id']}")] = r["id"]
        assign_menu.setEnabled(bool(targets))
        chosen = menu.exec(self.grid.viewport().mapToGlobal(pos))  # type: ignore[arg-type]
        if chosen is None:
            return
        if chosen is new_subject:
            self.create_subject_from(assets, target if flt is Filter.SUBJECT else None)
            return
        with self.project.transaction() as conn:
            if chosen is remove:
                self.teacher.removed(conn, target, assets)  # type: ignore[arg-type]
                actions.remove_photos_from_subject(conn, target, assets)  # type: ignore[arg-type]
            elif chosen is confirm:
                actions.assign_photos_to_subject(conn, target, assets)  # type: ignore[arg-type]
                self.teacher.assigned(conn, target, assets)  # type: ignore[arg-type]
            elif chosen in targets:
                actions.assign_photos_to_subject(conn, targets[chosen], assets)
                self.teacher.assigned(conn, targets[chosen], assets)
        self._after_people_change()

    def create_subject_from(self, assets: list[int], from_subject: int | None = None) -> int | None:
        """A new subject for photos of someone not in the list yet (name optional); ``from_subject``:
        the subject being viewed, which the photos leave."""
        if self.project is None or not assets:
            return None
        name, ok = QInputDialog.getText(self, "Tạo chủ thể mới",
                                        f"Tên chủ thể mới cho {len(assets)} ảnh (để trống = tự đặt số):")
        if not ok:
            return None
        with self.project.transaction() as conn:
            if from_subject is not None:
                self.teacher.removed(conn, from_subject, assets)
            subject_id = actions.create_subject(conn, assets, name, from_subject)
            self.teacher.assigned(conn, subject_id, assets)
        self._after_people_change()
        self.status.setText(f"Đã tạo {actions.subject_label(self.project.conn, subject_id)} với {len(assets)} ảnh.")
        return subject_id

    def _selection_text(self, rec: AssetRecord | None) -> str | None:
        """Why the last ⭐ selection chose this photo, or did not."""
        if rec is None or self.project is None or rec.score is None:
            return None
        try:
            if rec.pick_rank is not None:
                row = self.project.conn.execute("SELECT reason_json FROM picks WHERE asset_id = ?", (rec.id,)).fetchone()
                return "Được chọn vì: " + select.pick_reason(row[0] if row else None, rec.pick_rank)
            return select.why_not_picked(self.project.conn, rec.id)
        except Exception:  # noqa: BLE001 - an explanation must never break browsing
            log.exception("selection explanation failed")
            return None

    def _people_text(self, asset_id: int) -> str | None:
        if self.project is None:
            return None
        analysed = self.project.conn.execute(
            "SELECT 1 FROM stage_status WHERE asset_id = ? AND stage = 'detect' AND state = 'done'", (asset_id,)
        ).fetchone()
        if not analysed:
            return None
        rows = self.project.conn.execute(
            """SELECT o.subject_id, o.assignment, o.is_main FROM occurrences o WHERE o.asset_id = ?
               ORDER BY o.prominence DESC""", (asset_id,)).fetchall()
        names = [actions.subject_label(self.project.conn, r["subject_id"]) + ("?" if r["assignment"] == "suggested" else "")
                 for r in rows if r["subject_id"] is not None]
        unknown = sum(1 for r in rows if r["subject_id"] is None and r["is_main"])
        background = sum(1 for r in rows if not r["is_main"])
        parts = names + ([f"{unknown} chưa xác định"] if unknown else []) + ([f"{background} người phía sau"] if background else [])
        return ", ".join(parts) if parts else "không thấy người"

    def _show_inspector(self, rec: AssetRecord | None) -> None:
        self.inspector.show_record(rec, people=self._people_text(rec.id) if rec else None,
                                   selection=self._selection_text(rec))

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
        self.inspector.show_record(rec, people=self._people_text(rec.id) if rec else None,
                                   selection=self._selection_text(rec))
        if rec is not None and self.center.currentIndex() == 2:
            self.viewer.show_photo(rec.path, self.model.pixmap(rec), _long_side(rec))

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
        self.people.blockSignals(True)
        self.people.clearSelection()
        self.people.setCurrentRow(-1)
        self.people.blockSignals(False)
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

    # ------------------------------------------------------------ views
    def _on_view_changed(self, index: int) -> None:
        loupe = index == 2
        self.act_loupe.setChecked(loupe)
        self.act_grid_view.setChecked(not loupe)
        self.key_hints.setText(key_hints_html(loupe))

    def _toggle_key_hints(self, on: bool) -> None:
        self.settings.setValue("show_key_hints", on)
        self.key_hints.setVisible(on)

    # ------------------------------------------------------------ loupe
    def toggle_loupe(self) -> None:
        self.show_loupe(self.center.currentIndex() != 2)

    def show_loupe(self, on: bool) -> None:
        if on:
            rec = self.current_record()
            if rec is None:
                return
            self.center.setCurrentIndex(2)
            self.viewer.show_photo(rec.path, self.model.pixmap(rec), _long_side(rec))
            self.filmstrip.scrollTo(self.grid.currentIndex())
        elif self.center.currentIndex() == 2:
            self.center.setCurrentIndex(1)
            self.grid.scrollTo(self.grid.currentIndex())
            self.grid.setFocus()

    def toggle_zoom(self) -> None:
        if self.center.currentIndex() != 2:
            self.show_loupe(True)
        self.viewer.toggle_zoom()

    def zoom_step(self, direction: int) -> None:
        if self.center.currentIndex() != 2:
            self.show_loupe(True)
        (self.viewer.zoom_in if direction > 0 else self.viewer.zoom_out)()

    def zoom_to_eyes(self) -> None:
        """E: jump close to the eyes of the photo's main person (to judge focus)."""
        rec = self.current_record()
        if rec is None or self.project is None:
            return
        if self.center.currentIndex() != 2:
            self.show_loupe(True)
        row = self.project.conn.execute(
            """SELECT face_box FROM occurrences WHERE asset_id = ? AND face_box IS NOT NULL
               ORDER BY is_main DESC, prominence DESC LIMIT 1""", (rec.id,)).fetchone()
        if row is None:
            self.status.setText("Ảnh này chưa có khuôn mặt được nhận diện — dùng cuộn chuột hoặc + để phóng to.")
            return
        x, y, w, h = json.loads(row[0])
        face_px = h * max(rec.width or 0, rec.height or 0)  # upper estimate of the face height in photo pixels
        level = 2.0 if 0 < face_px < 900 else 1.0  # small faces: 200%, big close-ups: 100% is enough
        self.viewer.set_zoom(level, QPointF(x + w / 2, y + h * 0.42))

    # --------------------------------------------------------- culling
    def _targets(self) -> list[AssetRecord]:
        """Photos a K/X/U/stars key applies to: every selected photo (grid or filmstrip), else the current one."""
        selected = self.selected_records()
        current = self.current_record()
        if len(selected) > 1:
            return selected
        return [current] if current else selected

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
        self._show_inspector(self.current_record())
        self._update_counts()
        if advance and len(targets) == 1 and self.act_auto_advance.isChecked():
            self.step(1)

    def set_flag(self, flag: str | None) -> None:
        def apply(conn, rec: AssetRecord) -> None:  # noqa: ANN001
            decisions.set_flag(conn, rec.id, flag)
            if flag != rec.flag:
                self.teacher.culled(flag, rec.pick_rank, rec.score)  # numbers only, for learning your taste

        self._apply(apply, advance=flag is not None)

    def set_rating(self, rating: int) -> None:
        self._apply(lambda conn, rec: decisions.set_rating(conn, rec.id, rating))

    def toggle_favorite(self) -> None:
        targets = self._targets()
        new = not all(r.favorite for r in targets) if targets else True
        self._apply(lambda conn, rec: decisions.set_favorite(conn, rec.id, new))

    # ----------------------------------------------------------- best shots
    def _on_sort_changed(self) -> None:
        self.model.set_sort(Sort(self.sort.currentData()))
        self._after_filter()

    def set_sort(self, mode: Sort) -> None:
        self.sort.setCurrentIndex(self.sort.findData(mode.value))

    def open_select_dialog(self, accept: bool = False,
                           configure: Callable[[SelectDialog], None] | None = None) -> SelectDialog | None:
        """accept=True: run without showing the dialog, after ``configure`` set its fields (tests)."""
        if self.project is None:
            QMessageBox.information(self, "Chọn ảnh", "Hãy nhập một thư mục ảnh trước.")
            return None
        conn = self.project.conn
        people = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        in_view = [r.id for r in self.model.records() if r.status == "ok"]
        flt, target = self.model.current_filter, self.model.current_target
        view_name = (f"ảnh của {actions.subject_label(conn, target)}" if flt is Filter.SUBJECT and target is not None
                     else "danh sách đang xem")
        scored = conn.execute("SELECT COUNT(*) FROM measurements WHERE extractor = 'quality'").fetchone()[0]
        dialog = SelectDialog(self, people=people, in_view=len(in_view), view_name=view_name, scored=scored)
        if configure is not None:
            configure(dialog)
        if not accept and dialog.exec() != QDialog.DialogCode.Accepted:
            return dialog
        n = dialog.count.value()
        per_person = dialog.per_person.isChecked()
        if per_person:  # every person of the folder, whatever the grid currently shows
            picks = select.select_per_person(conn, n)
            params = {"mode": "per_person", "n": n}
        else:
            subject = target if flt is Filter.SUBJECT else None
            picks = select.select_in_view(conn, n, set(in_view), subject)
            params = {"mode": "in_view", "n": n, "subject_id": subject}
        marked = 0
        with self.project.transaction() as tx:
            select.save_run(tx, picks, params)
            if dialog.mark_keep.isChecked():
                for asset_id in {p.asset_id for p in picks}:
                    if decisions.get(tx, asset_id).flag is None:
                        decisions.set_flag(tx, asset_id, "keep")
                        marked += 1
        if per_person and self.model.current_filter is not Filter.ALL:
            self.search.clear()
            self.filters.setCurrentRow(0)  # show everyone's picks: "Tất cả ảnh"
        self.set_sort(Sort.PICKS_FIRST)  # reloads the view
        self.reload_preserving_view()
        self._update_counts()
        chosen = len({p.asset_id for p in picks})
        persons = len({p.subject_id for p in picks if p.subject_id is not None})
        self.status.setText(f"AI đã chọn {chosen} ảnh" + (f" cho {persons} chủ thể" if per_person else "")
                            + (f", đánh dấu Giữ {marked} ảnh" if marked else "")
                            + ". Ảnh được chọn ở đầu danh sách (nhãn AI) — hãy xem lại, rồi ⤴ Xuất ảnh.")
        self.grid.scrollToTop()
        return dialog

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
            "+ / −   phóng to / thu nhỏ (tới 800%),  cuộn chuột: phóng tại vị trí chuột\n"
            "E   phóng tới mắt của chủ thể chính (xem nét),  nháy đúp: 100% tại chỗ đó\n"
            "K   Giữ      X   Loại      U   bỏ đánh dấu\n"
            "1 – 5   chấm sao,  0   xoá sao\n"
            "F   Yêu thích\n"
            "Ctrl+I   nhập thư mục ảnh,  Ctrl+E   xuất ảnh\n"
            "Ctrl+F   tìm tên file,  Ctrl+L   danh sách khách chọn\n\n"
            "Trong lưới có thể chọn nhiều ảnh (Ctrl/Shift + click) rồi bấm K/X/số để áp dụng cho tất cả.",
        )
