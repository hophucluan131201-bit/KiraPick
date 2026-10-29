"""Main window: folders/filters | grid or loupe | inspector, plus import/export."""

from __future__ import annotations

import json
from html import escape
from datetime import date
from collections.abc import Callable
import logging
import errno
import os
import sqlite3
import time
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPointF,
    QRunnable,
    QSettings,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QGuiApplication, QIcon, QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QPlainTextEdit,
    QTextEdit,
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
    QSizePolicy,
    QToolButton,
    QSplitter,
    QStackedWidget,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.branding import APP_NAME, SETTINGS_IDS, data_dir
from app.storage import decisions, view
from app.storage.db import SchemaTooNewError
from app.storage.view import rotate_point
from app.storage.project import Project
from app.storage.sessions import delete_session, open_session, purge_old_sessions
from app.ai.models import ModelRegistry, ModelState
from app.identity import actions
from app.identity.cluster import merge_suggestions
from app.learning.store import LearningStore
from app.quality import burst, select
from app.learning.teacher import Teacher, group_key, photo_key
from app.learning import focus as focus_learning
from app.learning.taste import TasteStatus, train
from app.learning.taste_service import TasteService
from app.ai.clip_version import CLIP_VERSION
from app.quality.rank import DEFAULT_TASTE_WEIGHT
from app.storage.vectors import load_vector
from app.selection.client_list import delete_collection, list_collections
from app.ui.asset_model import ROLE_RECORD, AssetListModel, AssetRecord, Filter, Sort
from app.ui.client_list_dialog import ClientListDialog
from app.ui.collapsible import CollapsibleSection
from app.ui.compare_dialog import CompareDialog
from app.ui import update_dialog
from app.ui.update_dialog import AppUpdater
from app.updates.app_update import should_auto_check
from app.ui.people_delegate import PeopleDelegate
from app.ui.export_dialog import ExportDialog
from app.ui.grid import card_texts, make_filmstrip, make_grid
from app.ui.detail_panel import DetailPanel
from app.ui.top_bar import CELL_DEFAULT, TopBar
from app.ui.bottom_bar import BottomBar
from app.ui.layout_controller import LayoutController
from app.ui import gc_guard, shutdown
from app.ui.export_dialog import INCLUDE_PAIRS_KEY
from app.storage.stats import Counts, counts
from app.storage.workflow import STEPS, StepState, steps
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
    ("Space / Enter", "xem ảnh lớn"), ("← → ↑ ↓", "di chuyển"), ("P / K", "chọn"), ("X", "loại"), ("U", "bỏ chọn"),
    ("1–5 / 0", "sao / xoá sao"), ("F", "yêu thích"), ("Tab", "bảng chi tiết"),
    ("Q / W / R", "chấm nét"), ("Ctrl/Shift + click", "chọn nhiều ảnh"),
    ("Ctrl+A", "chọn tất cả"), ("Ctrl+F", "tìm tên file"), ("Ctrl+E", "xuất ảnh"), ("F1", "tất cả phím tắt"),
]
_KEYS_LOUPE = [
    ("Esc", "về lưới ảnh"), ("← →", "ảnh trước / sau"), ("Z", "100% ↔ vừa khung"), ("E", "phóng tới mắt"),
    ("+ / − / cuộn chuột", "phóng to / nhỏ"), ("nháy đúp", "100% tại chỗ đó"), ("kéo chuột", "di chuyển ảnh"),
    ("P / K", "chọn"), ("X", "loại"), ("U", "bỏ chọn"), ("1–5", "sao"), ("F", "yêu thích"),
    ("Q / W / R", "nét căng / hơi soft / lệch nét"),
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
        self.taste = TasteService()
        self._decisions_since_training = 0
        self._taste_pool = QThreadPool(self)
        self._gate = shutdown.Gate()  # closed while a session is released: no new worker starts
        self._retiring: list[QThread] = []  # stopped threads that did not finish in time (app.ui.shutdown)
        self._shutdown_ready = False  # every worker stopped: the next closeEvent releases everything
        self._shutdown_since: float | None = None
        self._shutdown_ask_at = 0.0
        self._shutdown_timer = QTimer(self, interval=100)
        self._shutdown_timer.timeout.connect(self._shutdown_tick)
        # Learning jobs report through these window-owned objects: a QObject created per job would be deleted by
        # the worker thread when the job ends (Qt objects must die on their own thread).
        self._taste_signals = _TasteSignals(self)
        self._taste_signals.done.connect(lambda status: self._on_taste_trained(status))
        self._focus_signals = _FocusSignals(self)
        self._focus_signals.done.connect(lambda statuses: self._on_focus_trained(statuses))
        self._tick_anchor: int | None = None
        self._import_progress: tuple[int, int] | None = None  # (done, total) while this window imports
        self._focus_labels_since_training = 0
        self.focus_status: dict[str, focus_learning.FocusStatus] = {}

        gc_guard.install(QApplication.instance())  # garbage is collected on the GUI thread only
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._build_shortcuts()
        self.layout_controller = LayoutController(
            self, body=self.body, sidebar=self.sidebar, side_slot=self.side_slot, rail=self.rail,
            drawer_button=self.drawer_button, splitter=self.splitter, grid_area=self.grid_area, grid=self.grid,
            detail=self.detail, detail_slot=self.detail_slot, strip=self.strip, top_bar=self.top_bar,
            bottom_bar=self.bottom_bar, settings=self.settings, model=self.model)
        self._update_steps()

        self._restore_geometry()
        self.layout_controller.evaluate()

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
        if not getattr(self, "_screen_watched", False) and self.windowHandle() is not None:
            self._screen_watched = True
            self.windowHandle().screenChanged.connect(self.layout_controller.on_screen_changed)
            self.layout_controller.on_screen_changed(self.screen())
        if not getattr(self, "_auto_check_scheduled", False):
            self._auto_check_scheduled = True
            QTimer.singleShot(3000, self._maybe_auto_check)  # after the window is up, never blocking it
        if getattr(self, "_maximize_on_show", False):
            self._maximize_on_show = False
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _build_toolbar(self) -> None:
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
        self.act_gpu = QAction("⚡ Dùng card đồ hoạ", self)
        self.act_gpu.setToolTip("Bật: AI chạy trên card đồ hoạ (nhanh hơn). Tắt nếu máy bị giật / “Not responding” "
                                "hoặc phân tích bị lỗi: AI chạy bằng CPU (chậm hơn nhưng ổn định).")
        self.act_gpu.setCheckable(True)
        self.act_gpu.setChecked(self.settings.value("use_gpu", True, bool))
        self.act_gpu.toggled.connect(lambda on: self.settings.setValue("use_gpu", on))
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
                    self.act_client_list, self.act_export, self.act_grid_view, self.act_loupe):
            self.addAction(act)  # keyboard shortcuts work without a toolbar
        self.act_learning = QAction("🎓 AI đã học", self)
        self.act_learning.setToolTip("Xem AI đã học gì từ các lần bạn sửa (chỉ trên máy này), hoặc xoá để học lại")
        self.act_learning.triggered.connect(self.show_learning)
        # Everything that is not a workflow step lives in ⚙, so the top bar fits a 1080p screen.
        options = QMenu(self)
        options.setToolTipsVisible(True)
        options.addAction(self.act_reset)
        options.addAction(self.act_learning)
        options.addAction(self.act_help)
        options.addSeparator()
        options.addAction(self.act_auto_advance)
        options.addAction(self.act_gpu)
        self.act_taste_weight = QAction("🎯 Mức ảnh hưởng của gu…", self)
        self.act_taste_weight.setToolTip("Điểm xếp hạng = Kỹ thuật + Hợp gu bạn; chọn tỷ lệ của phần gu")
        self.act_taste_weight.triggered.connect(self.ask_taste_weight)
        options.addAction(self.act_taste_weight)
        options.addSeparator()
        self.act_update = QAction("🔄 Cập nhật KiraPick… (cần mạng)", self)
        self.act_update.setToolTip("Tải bản KiraPick mới nhất từ GitHub (kiểm tra mã SHA-256) rồi mở bộ cài. "
                                   "Chỉ chạy khi bạn bấm; không gửi ảnh hay dữ liệu nào đi.")
        self.act_update.triggered.connect(lambda: self.start_app_update())
        options.addAction(self.act_update)
        self.act_auto_update = QAction("Tự kiểm tra bản KiraPick mới khi mở app (cần mạng)", self)
        self.act_auto_update.setCheckable(True)
        self.act_auto_update.setChecked(self.settings.value("auto_update_check", False, bool))
        self.act_auto_update.toggled.connect(lambda on: self.settings.setValue("auto_update_check", on))
        options.addAction(self.act_auto_update)
        self.options_button = QToolButton(self)
        self.options_button.setText("⚙ Tuỳ chọn")
        self.options_button.setToolTip("Làm lại, AI đã học, phím tắt, card đồ hoạ, mức gu, cập nhật")
        self.options_button.setMenu(options)
        self.options_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
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
        self.top_bar = TopBar(self.search, self.options_button)
        for key, act in (("import", self.act_import), ("people", self.act_analyze), ("quality", self.act_quality),
                         ("pick", self.act_select), ("export", self.act_export)):
            self.top_bar.bind(key, act)
        self.top_bar.size_slider.setValue(int(self.settings.value("grid_cell", CELL_DEFAULT)))
        self.top_bar.size_slider.valueChanged.connect(self.set_grid_cell)
        self.setMenuWidget(self.top_bar)

    def _build_body(self) -> None:
        # Body: [icon rail][splitter: sidebar slot | grid area | detail slot]. The sidebar and the detail panel are
        # children of the body for good; LayoutController docks them over their slot or floats them (no reparenting).
        body = QWidget()
        body.setObjectName("body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        side = QWidget(body)
        side.setObjectName("sidebar")
        side.setAutoFillBackground(True)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 6, 6, 6)
        self.sort = QComboBox()
        for label, mode in (("Xếp theo thời gian chụp", Sort.TIME), ("Xếp theo điểm kỹ thuật (K)", Sort.SCORE),
                            ("Xếp theo Hợp gu bạn (G)", Sort.TASTE), ("Xếp theo điểm xếp hạng (K + G)", Sort.RANK),
                            ("Ảnh AI chọn trước, rồi theo điểm", Sort.PICKS_FIRST)):
            self.sort.addItem(label, mode.value)
        self.sort.currentIndexChanged.connect(lambda _i: self._on_sort_changed())
        side_layout.addWidget(self.sort)
        self.sources = QListWidget()
        self.sources.setMaximumHeight(180)
        self.sources.setMinimumHeight(60)
        self.sources.currentRowChanged.connect(self._on_source_changed)
        self.filters = QListWidget()
        # Compact chips, two per row, never their own scrollbar (the list grows to fit).
        self.filters.setViewMode(QListWidget.ViewMode.ListMode)
        self.filters.setFlow(QListWidget.Flow.LeftToRight)
        self.filters.setWrapping(True)
        self.filters.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.filters.setUniformItemSizes(True)
        self.filters.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.filters.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.filters.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.filters.viewport().installEventFilter(self)
        self.filters.currentRowChanged.connect(self._on_filter_changed)
        self.filters.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.filters.customContextMenuRequested.connect(self._filter_context_menu)
        self._fill_filters()
        self.people = QListWidget()
        self.people.setIconSize(QSize(56, 56))
        self.people.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.people.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.people.setWordWrap(False)
        self.people.setItemDelegate(PeopleDelegate(self.people))
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
        self.client_list_button = QToolButton()
        self.client_list_button.setDefaultAction(self.act_client_list)
        self.client_list_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.client_list_button.setAutoRaise(True)
        filters_box = QWidget()
        filters_layout = QVBoxLayout(filters_box)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(2)
        filters_layout.addWidget(self.filters)
        filters_layout.addWidget(self.client_list_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.people_filter = QLineEdit()
        self.people_filter.setPlaceholderText("Tìm chủ thể…")
        self.people_filter.setClearButtonEnabled(True)
        self.people_filter.textChanged.connect(lambda _t: self._apply_people_filter())
        self.merge_button = QToolButton()
        self.merge_button.setDefaultAction(self.act_merge)
        self.merge_button.setAutoRaise(True)
        people_tools = QWidget()
        tools = QVBoxLayout(people_tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(2)
        self.merge_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        tools.addWidget(self.people_filter)
        tools.addWidget(self.people_sort)
        tools.addWidget(self.merge_button, 0, Qt.AlignmentFlag.AlignLeft)  # own row: its text never gets cut
        self.sections = {
            "folders": CollapsibleSection("THƯ MỤC", self.sources, "folders", self.settings),
            "filters": CollapsibleSection("LỌC", filters_box, "filters", self.settings),
            "people": CollapsibleSection("CHỦ THỂ", self.people, "people", self.settings, extra=people_tools),
        }
        side_layout.addWidget(self.sections["folders"])
        side_layout.addWidget(self.sections["filters"])
        side_layout.addWidget(self.sections["people"], 1)  # the people list takes the remaining height
        self.sections["folders"].setVisible(False)  # shown when a session has more than one folder
        side.setMinimumWidth(210)  # 56 px avatars, a short name and the count badge; fits a half-screen window
        self.sidebar = side

        self.center = QStackedWidget()
        self.empty_hint = QLabel(
            "Chưa có ảnh.\n\nBấm  “📂 Nhập ảnh”  (Ctrl+I) để bắt đầu.\n"
            "Ảnh gốc chỉ được đọc, không bao giờ bị sửa hay xoá."
        )
        self.empty_hint.setObjectName("emptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setWordWrap(True)  # long text must never set the window's minimum width
        self.grid = make_grid(self, int(self.settings.value("grid_cell", CELL_DEFAULT)))
        self.grid.setModel(self.model)
        self.model.set_display_size(cell=int(self.settings.value("grid_cell", CELL_DEFAULT)))
        self.grid.selectionModel().currentChanged.connect(self._on_current_changed)
        self.grid.doubleClicked.connect(lambda _: self.toggle_loupe())
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._grid_context_menu)
        self.grid.tick_clicked.connect(self.on_tick)
        self.grid.selectionModel().selectionChanged.connect(lambda *_a: self._marking_timer.start())

        loupe = QWidget()
        loupe_layout = QVBoxLayout(loupe)
        loupe_layout.setContentsMargins(0, 0, 0, 0)
        self.viewer = ImageViewer()
        self.viewer.status_changed.connect(lambda msg: self.status.setText(msg))
        self.filmstrip = make_filmstrip(self, 96)
        self.filmstrip.setModel(self.model)
        self.filmstrip.setSelectionModel(self.grid.selectionModel())  # one shared selection
        self.filmstrip.tick_clicked.connect(self.on_tick)
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
        self._hints_room = True
        self.key_hints.setVisible(self.act_help.isChecked())
        self.key_hints.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)  # never squeezed away
        center_box = QWidget()
        center_layout = QVBoxLayout(center_box)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        # Grid header: Lưới / Xem lớn (moved out of the old toolbar; the full header comes with the adaptive layout).
        view_row = QHBoxLayout()
        view_row.setContentsMargins(4, 2, 4, 0)
        for act in (self.act_grid_view, self.act_loupe):
            b = QToolButton()
            b.setDefaultAction(act)
            b.setAutoRaise(True)
            view_row.addWidget(b)
        view_row.addStretch(1)
        # Shown when the sidebar is not docked (NARROW / SHORT / TINY): opens it as a drawer over the photos.
        self.drawer_button = QToolButton()
        self.drawer_button.setText("☰ Bộ lọc")
        self.drawer_button.setToolTip("Thư mục, bộ lọc và chủ thể")
        self.drawer_button.setAutoRaise(True)
        self.drawer_button.clicked.connect(lambda: self.layout_controller.open_drawer())
        self.detail_button = QToolButton()
        self.detail_button.setText("▤ Chi tiết")
        self.detail_button.setToolTip("Hiện / ẩn bảng chi tiết của ảnh")
        self.detail_button.setAutoRaise(True)
        self.detail_button.clicked.connect(lambda: self.layout_controller.toggle_detail())
        view_row.insertWidget(0, self.drawer_button)
        view_row.addWidget(self.detail_button)
        center_layout.addLayout(view_row)
        # SHORT Grid Focus: one line about the current photo instead of the detail panel.
        self.strip = QLabel()
        self.strip.setObjectName("photoStrip")
        self.strip.setTextFormat(Qt.TextFormat.PlainText)
        self.strip.setContentsMargins(8, 0, 8, 0)
        self.strip.setVisible(False)
        center_layout.addWidget(self.strip)
        center_layout.addWidget(self.center, 1)
        center_layout.addWidget(self.key_hints)
        self.center.currentChanged.connect(self._on_view_changed)
        self._on_view_changed(self.center.currentIndex())

        self.detail = DetailPanel(body)
        self.detail.setAutoFillBackground(True)
        self.inspector = self.detail.inspector  # the Thông tin ảnh tab
        self.model.gate = self.viewer.gate = self.detail.score_card.histogram.gate = self._gate
        self.detail.keep_clicked.connect(lambda: self.set_flag("keep"))
        self.detail.reject_clicked.connect(lambda: self.set_flag("reject"))
        self.detail.clear_clicked.connect(lambda: self.set_flag(None))
        self.detail.rating_clicked.connect(self.set_rating)
        self.detail.favorite_clicked.connect(self.toggle_favorite)
        self.detail.neighbour_clicked.connect(self.go_to_asset)
        self.detail.open_loupe.connect(lambda: self.show_loupe(True))
        self.detail.people_menu_requested.connect(lambda pos: self._people_menu_for_current(pos))
        self.model.thumbnail_ready.connect(self._on_thumbnail_ready)
        side_slot, detail_slot = QWidget(), QWidget()
        side_slot.setMinimumWidth(side.minimumWidth())
        detail_slot.setMinimumWidth(self.detail.minimumWidth())
        detail_slot.setMinimumHeight(160)
        self.side_slot, self.detail_slot, self.grid_area = side_slot, detail_slot, center_box
        splitter.addWidget(side_slot)
        splitter.addWidget(center_box)
        splitter.addWidget(detail_slot)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        self.splitter = splitter
        # NARROW: an icon rail instead of the sidebar; each icon opens the drawer at its section.
        rail = QWidget()
        rail.setObjectName("rail")
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(2, 6, 2, 6)
        rail_layout.setSpacing(4)
        for icon, tip, section in (("📁", "Thư mục", "folders"), ("▦", "Bộ lọc", "filters"),
                                   ("👤", "Chủ thể", "people")):
            b = QToolButton()
            b.setText(icon)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _c=False, s=section: self.layout_controller.open_drawer(s))
            rail_layout.addWidget(b)
        rail_layout.addStretch(1)
        self.rail = rail
        body_layout.addWidget(rail)
        body_layout.addWidget(splitter, 1)
        self.setCentralWidget(body)
        self.body = body

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.bottom_bar = BottomBar()
        sb.addWidget(self.bottom_bar, 1)  # the bar spans the whole width under the panels
        # The window keeps its old names for the bar's parts (status messages, progress, pause).
        self.status = self.bottom_bar.status
        self.counts = self.bottom_bar.kept
        self.progress = self.bottom_bar.progress_bar
        self.pause_button = self.bottom_bar.pause_button
        self.pause_button.clicked.connect(self._pause_or_resume)
        b = self.bottom_bar
        b.keep.connect(lambda: self.set_flag("keep"))
        b.reject.connect(lambda: self.set_flag("reject"))
        b.clear.connect(lambda: self.set_flag(None))
        b.rating.connect(self.set_rating)
        b.rotate.connect(self.rotate_view)
        b.exif.connect(self.detail.open_exif)
        b.export.connect(lambda: self.open_export_dialog())
        b.export_client.connect(lambda: self.open_export_dialog(client_list=True))
        self._marking_timer = QTimer(self, singleShot=True, interval=100)  # coalesce bursts of selection changes
        self._marking_timer.timeout.connect(self._update_counts)

    def _build_shortcuts(self) -> None:
        def sc(key: str, fn: object) -> None:
            # A key without a modifier never acts on photos while the user types (search box, people filter, …).
            guarded = (lambda: None if typing_in(QApplication.focusWidget()) else fn()) if key not in UNGUARDED else fn
            QShortcut(QKeySequence(key), self, guarded, context=Qt.ShortcutContext.WindowShortcut)

        sc("P", lambda: self.set_flag("keep"))  # P (pick) and K: Chọn
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
        sc("Escape", lambda: self.layout_controller.close_floating() or self.show_loupe(False))
        sc("Z", self.toggle_zoom)
        sc("+", lambda: self.zoom_step(1))
        sc("=", lambda: self.zoom_step(1))
        sc("-", lambda: self.zoom_step(-1))
        sc("E", self.zoom_to_eyes)
        sc("Q", lambda: self.set_focus_label("sharp"))
        sc("W", lambda: self.set_focus_label("soft"))
        sc("R", lambda: self.set_focus_label("missed"))
        sc("F1", self.show_shortcuts)
        # Tab: details on/off (SHORT: Grid Focus ↔ Detail Focus); inside a text field it still moves to the next one.
        QShortcut(QKeySequence(Qt.Key.Key_Tab), self, self._on_tab, context=Qt.ShortcutContext.WindowShortcut)

    def _on_tab(self) -> None:
        if typing_in(QApplication.focusWidget()):
            self.focusNextChild()
            return
        self.layout_controller.toggle_detail()

    # ---------------------------------------------------------- sessions
    def _set_project(self, project: Project, photo_root: Path) -> None:
        if self.project is not None:
            self.project.close()
        self.project = project
        self._session_root = photo_root
        self.setWindowTitle(f"{photo_root.name or photo_root} — {APP_NAME} {__version__}")
        self.search.clear()
        self.model.set_search("")
        self.taste.load_clips(project.conn)
        self.model.set_ranker(self.taste.ranker(self.taste_weight()))
        self.model.set_project(project)
        self.retrain_taste()
        self._fill_filters()
        self._fill_people()
        self._refresh_sidebar()
        self._update_empty_state()
        self._update_steps()
        if self.model.rowCount():
            self.select_row(0)

    def _close_session(self) -> bool:
        """Close the current session once nothing reads it any more; False (session left open) if work is still
        running after SWITCH_WAIT_MS — the caller must then not switch or delete anything."""
        self._stop_analysis()
        for dialog in self.findChildren(QDialog):
            dialog.close()
        self.viewer.show_photo(None)
        self._gate.open = False
        left = shutdown.settle(self._session_work, SWITCH_WAIT_MS)
        if left:
            self._gate.open = True
            log.warning("session kept open: %s still running", ", ".join(left))
            self.status.setText(f"Chưa đổi được thư mục: {', '.join(left)} vẫn đang chạy. Thử lại sau vài giây.")
            self._on_current_changed(self.grid.currentIndex(), QModelIndex())  # show again what was dropped
            return False
        self._marking_timer.stop()
        self.detail.score_card.histogram.clear_cache()
        self.model.set_project(None)
        if self.project is not None:
            self.project.close()
        self.project = None
        self._session_root = None
        self._paused_job = None
        self._fill_people()
        self._update_steps()
        self._gate.open = True  # the next session may start work
        return True

    # ------------------------------------------------------- background work
    def _session_work(self) -> list[shutdown.Work]:
        """Everything that reads the current session (database, preview and thumbnail files)."""
        works = [
            shutdown.Work("đọc ảnh để xem", self.viewer.wait_idle, self.viewer.stop_pending),
            shutdown.Work("tạo ảnh nhỏ", self.model.wait_for_thumbnails, self.model.stop_pending),
            shutdown.Work("biểu đồ sáng", self.detail.score_card.histogram.wait,
                          self.detail.score_card.histogram.stop_pending),
        ]
        threads = [("nhập ảnh", self.import_thread), ("phân tích AI", self.analyze_thread),
                   *(("phân tích AI", t) for t in self._retiring)]
        threads += [("sao chép ảnh xuất", d.copy_thread) for d in self.findChildren(ExportDialog)]
        works += [shutdown.Work(name, t.wait, t.cancel) for name, t in threads if t is not None]
        return works

    def _all_work(self) -> list[shutdown.Work]:
        """Session work plus what only the window's lifetime depends on (learning, app update)."""
        works = self._session_work()
        works.append(shutdown.Work("học gu", self._taste_pool.waitForDone, self._taste_pool.clear))
        updater = getattr(self, "_updater", None)
        for t in (getattr(updater, "worker", None), getattr(self, "_auto_worker", None)):
            if t is not None:  # a network call cannot be cancelled; it ends with its own time limit
                works.append(shutdown.Work("kiểm tra cập nhật", t.wait, lambda: None))
        return works

    def _on_thumbnail_ready(self, asset_id: int) -> None:
        """The detail preview, its burst rows and the SHORT strip use a thumbnail as soon as it is decoded."""
        row = self.model.index_of(asset_id)
        rec = self.model.record(row) if row is not None and row.isValid() else None
        pm = self.model.pixmap(rec) if rec is not None else None
        if pm is not None:
            self.detail.update_thumbnail(asset_id, pm)

    def open_sidebar_section(self, section: str) -> None:
        """Drawer opened from the icon rail: that section unfolded (folders only when the session has several)."""
        target = self.sections.get(section)
        if target is not None and target.isVisibleTo(self.sidebar):
            target.set_collapsed(False)

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
        if not self._close_session():
            return  # still in use: nothing is deleted
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
        if self.import_thread is not None or not self._gate.open:
            return None
        self._stop_analysis()
        self._paused_job = None
        root = root.resolve()
        if self.project is None or self._session_root != root:
            # One session per photo folder: switching folders closes the current one.
            if not self._close_session():
                return None
            try:
                project, restored = open_session(sessions_dir(), root)
            except SchemaTooNewError:
                QMessageBox.warning(self, "Mở thư mục ảnh", session_too_new_text())
                return None
            except (OSError, sqlite3.Error) as exc:
                log.warning("session open failed: %s", type(exc).__name__)
                QMessageBox.warning(self, "Mở thư mục ảnh", session_open_failed_text(exc))
                return None
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
            if phase == "ingest":
                self._import_progress = (done, total)
                self.refresh_steps()
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
        if not self._gate.open:  # releasing the session: no dialog (it would run its own event loop); logged
            log.warning("import failed while closing: %s", message)
            return
        QMessageBox.critical(self, "Lỗi khi nhập ảnh", message)

    def _on_import_thread_finished(self) -> None:
        if self.sender() is not self.import_thread or self.project is None:
            return  # window closed meanwhile
        cancelled = self.import_thread is not None and self.import_thread.cancel_requested
        self.import_thread = None
        self._import_progress = None
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
            "<b>Gu chọn ảnh (Hợp gu bạn)</b>",
            f"Đã ghi {store.culling_count()} ảnh bạn đã Giữ/Loại/cho sao/❤ hoặc khách chọn.",
            self.taste.status.reason + ("" if self.taste.ready else
                                        " — cần ít nhất 60 lựa chọn (20 thích, 20 không thích) và đoán đúng "
                                        "rõ hơn đoán mò thì mới hiện điểm Hợp gu."),
            *self.taste.explain(self._prompt_vectors()),
            f"Điểm xếp hạng = {100 - round(self.taste_weight() * 100)}% Kỹ thuật + "
            f"{round(self.taste_weight() * 100)}% Hợp gu (đổi trong ⚙ Tuỳ chọn).",
            "",
            "<b>Độ nét theo máy + ống kính</b>",
            *self.focus_text(),
            "",
            "Dữ liệu học chỉ có các con số (độ giống, điểm, “dấu vân tay” CLIP của ảnh), không có ảnh, "
            "tên file hay tên chủ thể, và chỉ nằm trên máy này.",
        ]
        return "<br>".join(lines)

    def open_compare(self) -> CompareDialog | None:
        """🎓 Thích tấm nào hơn?: pairs of similar photos of one subject (needs 📊 with the CLIP model)."""
        if self.project is None or self.teacher.store is None:
            return None
        conn = self.project.conn
        subjects = {r[0]: r[1] for r in conn.execute(
            "SELECT asset_id, subject_id FROM occurrences WHERE subject_id IS NOT NULL AND is_main = 1")}
        recs = {r.id: r for r in self.model.records()}
        if not recs or not self.taste.clips:
            QMessageBox.information(self, "So sánh ảnh", "Cần bấm 📊 Phân tích ảnh (có mô hình CLIP) trước, "
                                                         "và mở danh sách có ảnh.")
            return None
        ranked = {i: r.ranked.value for i, r in recs.items() if r.ranked is not None and r.ranked.value is not None}
        session = self._session_key()

        def answer(winner: int, loser: int) -> None:
            parts = {i: dict(recs[i].score.parts) if recs.get(i) and recs[i].score else {} for i in (winner, loser)}
            groups = {i: group_key(session, (recs[i].capture_time or "")[:10]) if recs.get(i) else ""
                      for i in (winner, loser)}
            self.teacher.preferred(session, winner, loser, self.taste.clips, parts, groups)
            self._decisions_since_training += 1
            if self._decisions_since_training >= RETRAIN_EVERY:
                self.retrain_taste()

        dialog = CompareDialog(self, {k: v for k, v in subjects.items() if k in recs}, self.taste.clips, ranked,
                               lambda i: self.model.pixmap(recs[i]) if i in recs else None, answer)
        dialog.show()
        return dialog

    def focus_text(self) -> list[str]:
        if not self.focus_status:
            return ["Chưa có ảnh nào được chấm nét. Bấm Q (nét căng), W (hơi soft), R (lệch nét / rung) khi rà ảnh; "
                    f"mỗi máy + ống kính cần ít nhất {focus_learning.MIN_EACH} tấm nét căng và "
                    f"{focus_learning.MIN_EACH} tấm hơi soft / lệch nét. Trong lúc đó độ nét được so với các tấm "
                    "nét nhất của cùng máy trong buổi chụp."]
        return [f"{escape(camera)}: {escape(st.reason)}" for camera, st in sorted(self.focus_status.items())]

    def _prompt_vectors(self) -> dict:
        """Style prompt embeddings (to put the learnt taste into words); empty without the CLIP model files."""
        try:
            import numpy as np

            with np.load((self._registry or ModelRegistry()).require("clip_prompts")) as data:
                return dict(zip([str(i) for i in data["ids"]], data["vectors"], strict=True))
        except Exception:  # noqa: BLE001 - only the explanation is lost
            return {}

    def show_learning(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("AI đã học")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(self.learning_text())
        compare = box.addButton("So sánh ảnh…", QMessageBox.ButtonRole.ActionRole)
        compare.setToolTip("Chọn tấm thích hơn trong từng cặp ảnh giống nhau, để app học gu bạn nhanh hơn")
        forget = box.addButton("Xoá dữ liệu học…", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
        forget.setEnabled(self.teacher.store is not None)
        compare.setEnabled(self.teacher.store is not None and self.project is not None)
        box.exec()
        if box.clickedButton() is compare:
            self.open_compare()
            return
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
        """Stop every worker, then release the session (order and fallbacks: app.ui.shutdown)."""
        if self._shutdown_since is not None and not self._shutdown_ready:  # already waiting for workers
            event.ignore()
            return
        if not self._shutdown_ready:
            self.settings.setValue("geometry", self.saveGeometry())
            for dialog in self.findChildren(QDialog):  # they use the project database
                dialog.close()
            if self.import_thread is not None:  # resumable: unfinished files continue next time
                self.import_thread.cancel()
        self._gate.open = False  # stays closed: the window is going away
        left = shutdown.settle(self._all_work, 0 if self._shutdown_ready else CLOSE_WAIT_MS)
        if left:
            self._shutdown_ready = False
            event.ignore()
            self._wait_then_close(left)
            return
        self._shutdown_timer.stop()
        self._marking_timer.stop()  # it would read the database after it is closed
        if self.project is not None:
            self.project.close()
            self.project = None  # a late signal must find no session, not a closed one
        if self.teacher.store is not None:
            self.teacher.store.close()
            self.teacher.store = None
        super().closeEvent(event)

    def _wait_then_close(self, left: list[str]) -> None:
        """Workers still run: keep everything open, wait on a GUI timer (the window stays responsive)."""
        log.warning("closing waits for: %s", ", ".join(left))
        self._shutdown_since = time.monotonic()
        self._shutdown_ask_at = self._shutdown_since + HUNG_AFTER_S
        # Nothing new may start (the window itself stays enabled: the "Thoát ngay?" question is its child).
        for widget in (self.menuWidget(), self.centralWidget(), self.bottom_bar):
            widget.setEnabled(False)
        for action in self.findChildren(QAction):
            action.setEnabled(False)
        for shortcut in self.findChildren(QShortcut):
            shortcut.setEnabled(False)
        self.status.setText(f"Đang đợi {', '.join(left)} dừng hẳn rồi mới đóng…")
        self._shutdown_timer.start()

    def _shutdown_tick(self) -> None:
        left = shutdown.still_running(self._all_work())
        if not left:
            self._shutdown_timer.stop()
            self._shutdown_ready = True
            self.close()
            return
        if time.monotonic() >= self._shutdown_ask_at:
            self._shutdown_timer.stop()  # no tick while the question is open
            if self._ask_quit_anyway(left):
                self._quit_now(left)
                return
            self._shutdown_ask_at = time.monotonic() + HUNG_AFTER_S
            self._shutdown_timer.start()

    def _ask_quit_anyway(self, left: list[str]) -> bool:
        return QMessageBox.question(self, "Đang đóng KiraPick", quit_anyway_text(left)) == QMessageBox.StandardButton.Yes

    def _quit_now(self, left: list[str]) -> None:
        """A worker hangs: end the process WITHOUT tearing down objects or connections it may still use."""
        log.warning("quit while still running: %s", ", ".join(left))
        self.settings.sync()
        logging.shutdown()
        self._hard_exit(EXIT_ABANDONED)

    _hard_exit = staticmethod(os._exit)  # replaced in tests

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

    def refresh_steps(self) -> None:
        """✓ / ◐ of the five workflow steps in the top bar (app.storage.workflow); cheap COUNT queries."""
        if self.project is None:
            self.top_bar.set_states({k: StepState(False, None) for k in STEPS})
            return
        self.top_bar.set_states(steps(self.project.conn, importing=self._import_progress))

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
        self.refresh_steps()

    def start_analysis(self, mode: str = "people") -> AnalyzeThread | None:
        if (self.project is None or self.import_thread is not None or self.analyze_thread is not None
                or not self._gate.open):
            return None
        thread = AnalyzeThread(self.project.folder, mode, self._learning_dir(), self.act_gpu.isChecked())
        self._analysis_started = time.monotonic()
        self._run_device = None
        self._gpu_name = None
        thread.progress.connect(self._on_analyze_progress)
        thread.succeeded.connect(self._on_analyze_done)
        title = "Nhận diện chủ thể" if mode == "people" else "Phân tích ảnh"
        thread.failed.connect(lambda msg: QMessageBox.warning(self, title, msg) if self._gate.open
                              else log.warning("analysis failed while closing: %s", msg))
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
        if not thread.wait(ANALYSIS_STOP_MS):  # still finishing a photo: keep it referenced until it ends
            self._retire(thread)
        self._update_steps()
        if self.import_thread is None:
            self.progress.setVisible(False)
            self.pause_button.setVisible(False)

    def _retire(self, thread: QThread) -> None:
        """A stopped thread that has not ended: Qt aborts the process if a running QThread is destroyed."""
        self._retiring.append(thread)
        thread.finished.connect(lambda t=thread: t in self._retiring and self._retiring.remove(t))

    def _on_analyze_progress(self, phase: str, done: int, total: int) -> None:
        if phase.startswith("gpu_name:"):  # the graphics card the speed check picked
            self._gpu_name = phase[len("gpu_name:"):]
            return
        if phase.startswith("device:"):  # where the AI runs, shown with every progress message
            device = phase[len("device:"):]
            name = getattr(self, "_gpu_name", None)
            self._run_device = ("CPU" if device == "cpu" else f"GPU {name}" if name
                                else {"cuda": "GPU NVIDIA", "directml": "GPU DirectML", "openvino": "OpenVINO"}.get(device, "GPU"))
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
            device = {"cuda": "GPU NVIDIA", "directml": "GPU DirectML", "openvino": "OpenVINO"}.get(summary["device"], "CPU")
            parts = [f"Phân tích xong ({device}, {took}): {self._step_state()[2]} ảnh có điểm"]
            if summary.get("measure_failed"):
                parts.append(f"{summary['measure_failed']} ảnh không chấm được ({self._main_error('quality')})")
            note = f" ({summary['fallback_reason']})" if summary.get("fallback_reason") else ""
            self.status.setText(", ".join(parts) + "." + note + " Bước tiếp theo: bấm ⭐ Chọn ảnh, hoặc xếp theo điểm.")
            self.status.setToolTip(summary.get("gpu_check") or "")
            self.taste.load_clips(self.project.conn)  # new CLIP vectors: the taste score can cover them
            self.retrain_taste()
            return
        people = self.project.conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        unknown = self.project.conn.execute(
            f"SELECT COUNT(*) FROM ({actions.UNIDENTIFIED_ASSETS})").fetchone()[0]
        review = len(merge_suggestions(self.project.conn))
        device = {"cuda": "GPU NVIDIA", "directml": "GPU DirectML", "openvino": "OpenVINO"}.get(summary["device"], "CPU")
        device += f", {_duration(time.monotonic() - getattr(self, '_analysis_started', time.monotonic()))}"
        parts = [f"Nhận diện xong ({device}): {people} chủ thể", f"{unknown} ảnh chưa xác định"]
        if review:
            parts.append(f"{review} gợi ý cần xem lại")
        if summary["failed"]:
            parts.append(f"{summary['failed']} ảnh lỗi")
        note = f" ({summary['fallback_reason']})" if summary.get("fallback_reason") else ""
        if summary.get("learning"):
            note += f" {summary['learning']}"
        self.status.setToolTip(summary.get("gpu_check") or "")
        self.status.setText(", ".join(parts) + "." + note
                            + " Hãy kiểm tra, gộp/tách chủ thể cho đúng, rồi bấm 📊 Phân tích ảnh.")

    def _main_error(self, stage: str) -> str:
        """The most frequent error of a stage, shortened, for the status bar (details are in the log)."""
        row = self.project.conn.execute(
            """SELECT error, COUNT(*) FROM stage_status WHERE stage = ? AND state = 'failed' AND error IS NOT NULL
               GROUP BY error ORDER BY 2 DESC LIMIT 1""", (stage,)).fetchone() if self.project else None
        if row is None:
            return "xem file log"
        hint = " — thử tắt ⚡ Dùng card đồ hoạ rồi bấm lại" if self.act_gpu.isChecked() else ""
        return f"lỗi: {row[0][:120]}{hint}"

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
        self._apply_people_filter()
        self._update_merge_action()

    def _apply_people_filter(self) -> None:
        """Hide people whose name does not contain the typed text (the special rows stay visible)."""
        needle = self.people_filter.text().strip().casefold()
        for i in range(self.people.count()):
            item = self.people.item(i)
            kind = (item.data(Qt.ItemDataRole.UserRole) or ("", None))[0]
            item.setHidden(bool(needle) and kind == "subject" and needle not in item.text().casefold())

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
        """Right-click in the grid: acts on every marked photo (batch)."""
        self._people_menu_at(self.grid.viewport().mapToGlobal(pos),  # type: ignore[arg-type]
                             [r.id for r in self.selected_records()])

    def _people_menu_for_current(self, global_pos: object) -> None:
        """Chủ thể tab of the detail panel: acts on the photo shown there only, whatever is marked in the grid."""
        rec = self.current_record()
        if rec is not None:
            self._people_menu_at(global_pos, [rec.id])

    @staticmethod
    def _run_menu(menu: QMenu, global_pos: object) -> object:
        return menu.exec(global_pos)  # type: ignore[arg-type]  # tests replace this to pick an entry

    def _people_menu_at(self, global_pos: object, assets: list[int]) -> None:
        """People actions for exactly these photos — one menu and one behaviour for the grid and the panel."""
        if self.project is None or not assets:
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
        chosen = self._run_menu(menu, global_pos)
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
        """Fill the detail panel for this photo (score card, info, burst, people)."""
        neighbours: list[AssetRecord] = []
        if rec is not None and self.project is not None:
            # The burst as recorded, limited to photos in the current view (a filter may hide some). Looked up
            # through the model's id -> row map: no pass over all records on every Chọn / sao / ♥.
            for i in burst.neighbours(self.project.conn, rec.id):
                other = self.model.record(self.model.index_of(i))
                if other is not None:
                    neighbours.append(other)
        self.detail.show_record(
            rec, taste=self.taste.status, people=self._people_text(rec.id) if rec else None, neighbours=neighbours,
            pixmap=self.model.pixmap(rec) if rec else None, selection=self._selection_text(rec),
            neighbour_pixmaps={n.id: pm for n in neighbours if (pm := self.model.pixmap(n)) is not None})
        self.strip.setText(strip_text(rec))

    def go_to_asset(self, asset_id: int) -> None:
        """Make this photo the current one (Ảnh tương tự)."""
        idx = self.model.index_of(asset_id)
        if idx.isValid():
            self.select_row(idx.row())

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
        self._show_inspector(rec)
        if rec is not None and self.center.currentIndex() == 2:
            self.viewer.show_photo(rec.path, self.model.pixmap(rec), _long_side(rec), rec.rotation)

    def _on_source_changed(self, row: int) -> None:
        item = self.sources.item(row)
        if item is not None:
            self.model.set_filter(self.model.current_filter, source_id=item.data(Qt.ItemDataRole.UserRole))
            self._after_filter()

    def _fit_filters(self) -> None:
        """Two chips per row; the list is exactly as tall as its rows (no scrollbar of its own)."""
        width = max(120, self.filters.viewport().width())
        cell = QSize((width - 4) // 2, 28)
        self.filters.setGridSize(cell)
        for i in range(self.filters.count()):
            item = self.filters.item(i)
            if item.toolTip() == "":
                item.setToolTip(item.text())
            item.setSizeHint(QSize(cell.width() - 4, 26))
        rows = (self.filters.count() + 1) // 2
        self.filters.setFixedHeight(rows * cell.height() + 2 * self.filters.frameWidth() + 4)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if obj is self.filters.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._fit_filters)
        return super().eventFilter(obj, event)

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
        self._fit_filters()

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
        self._learn_client_picks(collection_id)
        self.search.clear()
        self.model.set_search("")
        self._fill_filters(select_collection=collection_id)
        self._on_filter_changed(self.filters.currentRow())
        self.grid.selectAll()
        self.status.setText(f"Đã tạo danh sách khách: {self.model.rowCount()} ảnh. Bấm “Xuất ảnh” để chép.")

    def _after_filter(self) -> None:
        self._tick_anchor = None  # filter, sort or search changed: a Shift+tick range starts again
        self._update_counts()
        self._update_empty_state()
        if self.model.rowCount():
            self.select_row(0)
        else:
            self._show_inspector(None)

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
        self.sections["folders"].setVisible(self.sources.count() > 2)  # "all" + 2 or more folders
        self._update_counts()

    def _update_counts(self) -> None:
        """Bottom bar: photos Chọn / Loại / undecided, export size (follows "Kèm JPEG"), marking (app.storage.stats)."""
        include_pairs = self.settings.value(INCLUDE_PAIRS_KEY, True, bool)
        if self.project is None:
            self.bottom_bar.set_counts(Counts(0, 0, 0, 0, 0, 0), include_pairs, 0)
            return
        self.bottom_bar.set_counts(counts(self.project.conn, include_pairs), include_pairs,
                                   len(self.selected_records()))

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
        self.key_hints.setVisible(on and self._hints_room)

    def set_key_hints_room(self, room: bool) -> None:
        """SHORT / TINY layouts have no height to spare: the key cheat sheet hides (the ⚙ choice is kept)."""
        self._hints_room = room
        self.key_hints.setVisible(self.act_help.isChecked() and room)

    # ------------------------------------------------------------ loupe
    def toggle_loupe(self) -> None:
        self.show_loupe(self.center.currentIndex() != 2)

    def show_loupe(self, on: bool) -> None:
        if on:
            rec = self.current_record()
            if rec is None:
                return
            self.center.setCurrentIndex(2)
            self.viewer.show_photo(rec.path, self.model.pixmap(rec), _long_side(rec), rec.rotation)
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
        cx, cy = rotate_point(x + w / 2, y + h * 0.42, rec.rotation)  # face boxes are in file coordinates
        self.viewer.set_zoom(level, QPointF(cx, cy))

    # --------------------------------------------------------- culling
    def _targets(self) -> list[AssetRecord]:
        """Photos a K/X/U/stars key applies to: every selected photo (grid or filmstrip), else the current one."""
        selected = self.selected_records()
        current = self.current_record()
        if len(selected) > 1:
            return selected
        return [current] if current else selected

    def rotate_view(self) -> None:
        """Xoay xem: turn the marked photos (or the current one) 90° clockwise on screen. Display only — the file,
        the AI measurements and exported copies never change."""
        if self.project is None:
            return
        targets = self._targets()
        if not targets:
            return
        with self.project.transaction() as conn:
            turns = {rec.id: view.rotate(conn, rec.id) for rec in targets}
        for asset_id, t in turns.items():
            self.model.set_rotation(asset_id, t)
        current = self.current_record()
        if current is not None and current.id in turns and self.center.currentIndex() == 2:
            if not self.viewer.set_rotation(current.rotation):  # nothing loaded yet: show it again, turned
                self.viewer.show_photo(current.path, self.model.pixmap(current), _long_side(current), current.rotation)

    def set_grid_cell(self, size: int) -> None:
        """Thumbnail size slider: card size of the grid (remembered)."""
        self.settings.setValue("grid_cell", size)
        if self.layout_controller.set_cell(size):  # SHORT Detail Focus: applied when the grid wraps again
            return
        delegate = self.grid.itemDelegate()
        delegate.cell = size  # type: ignore[attr-defined]
        self.model.set_display_size(cell=size)  # larger cards: sharper thumbnails (cell × screen ratio)
        self.grid.doItemsLayout()
        self.grid.viewport().update()

    def on_tick(self, asset_id: int, shift: bool) -> None:
        """Tick box: Chọn ↔ not chosen for that card only (never the current photo or the marking).
        Shift: Chọn on every card from the last tick box clicked to this one, in the order shown."""
        records = self.model.records()
        order = [r.id for r in records]
        if asset_id not in order:
            return
        anchor = self._tick_anchor
        if shift and anchor in order:
            lo, hi = sorted((order.index(anchor), order.index(asset_id)))
            self._apply_to(records[lo:hi + 1], lambda conn, rec: decisions.set_flag(conn, rec.id, "keep"))
        else:
            rec = records[order.index(asset_id)]
            new = None if rec.flag == "keep" else "keep"
            self._apply_to([rec], lambda conn, r: decisions.set_flag(conn, r.id, new))
        self._tick_anchor = asset_id

    def _apply(self, fn: object, *, advance: bool = False) -> None:
        if self.project is None:
            return
        targets = self._targets()
        if not targets:
            return
        self._apply_to(targets, fn)
        if advance and len(targets) == 1 and self.act_auto_advance.isChecked():
            self.step(1)

    def _apply_to(self, targets: list[AssetRecord], fn: object) -> None:
        """Change decisions of these photos in one transaction, teach taste, repaint (keys, buttons, tick boxes)."""
        if self.project is None or not targets:
            return
        with self.project.transaction() as conn:
            for rec in targets:
                fn(conn, rec)  # type: ignore[operator]
        self._learn_taste(targets)
        for rec in targets:
            self.model.refresh_record(rec.id)
        self._show_inspector(self.current_record())
        self._update_counts()
        self.refresh_steps()

    def _session_key(self) -> str:
        assert self.project is not None
        row = self.project.conn.execute("SELECT name, created_at FROM project").fetchone()
        return f"{row[0]}|{row[1]}"

    def _learn_taste(self, targets: list[AssetRecord]) -> None:
        """Each changed photo's latest Keep/Reject/stars/❤ becomes one taste example (numbers only)."""
        if self.project is None or self.teacher.store is None:
            return
        session = self._session_key()
        conn = self.project.conn
        for rec in targets:
            clip = load_vector(conn, rec.id, "clip", CLIP_VERSION)
            parts = dict(rec.score.parts) if rec.score is not None else {}
            self.teacher.decided(photo_key(session, rec.id), decisions.get(conn, rec.id), parts, clip,
                                 group_key(session, (rec.capture_time or "")[:10]))
        self._decisions_since_training += len(targets)
        if self._decisions_since_training >= RETRAIN_EVERY:
            self.retrain_taste()

    # ------------------------------------------------------- AI updates
    def _registry_or_default(self) -> ModelRegistry:
        return self._registry or ModelRegistry()

    def start_app_update(self, **kw) -> AppUpdater:  # noqa: ANN003 - test doubles for network/disk
        updater = AppUpdater(self, gate=self._gate, **kw)
        self._updater = updater
        updater.check()
        return updater

    def _maybe_auto_check(self) -> None:
        """Opt-in (off by default): at most once a day, read only the release list in the background."""
        today = date.today().isoformat()
        if not should_auto_check(enabled=self.act_auto_update.isChecked(),
                                 last_check=self.settings.value("last_update_check", None), today=today):
            return
        self.settings.setValue("last_update_check", today)
        worker = update_dialog.auto_check_worker(self)
        worker.done.connect(lambda release: release and self.status.setText(
            f"Có KiraPick {release.version} — vào ⚙ Tuỳ chọn → 🔄 Cập nhật KiraPick để cài."))
        worker.failed.connect(lambda msg: log.info("automatic update check: %s", msg))  # silent when offline
        self._auto_worker = worker
        worker.start()

    # ------------------------------------------------------------- taste
    def taste_weight(self) -> float:
        return max(0.0, min(1.0, float(self.settings.value("taste_weight", DEFAULT_TASTE_WEIGHT))))

    def set_taste_weight(self, w: float) -> None:
        self.settings.setValue("taste_weight", max(0.0, min(1.0, w)))
        self.model.set_ranker(self.taste.ranker(self.taste_weight()))
        if self.project is not None:
            self.reload_preserving_view()
            self._show_inspector(self.current_record())

    def ask_taste_weight(self) -> None:
        value, ok = QInputDialog.getInt(
            self, "Mức ảnh hưởng của gu",
            "Điểm xếp hạng = Kỹ thuật và Hợp gu bạn.\nPhần Hợp gu chiếm bao nhiêu % (0 = chỉ kỹ thuật)?",
            round(self.taste_weight() * 100), 0, 100, 10)
        if ok:
            self.set_taste_weight(value / 100)

    def retrain_taste(self, wait: bool = False) -> None:
        """Train the taste model from the learning store in the background (never on the Qt thread)."""
        store = self.teacher.store
        self._decisions_since_training = 0
        if store is None:
            return
        self.retrain_focus(wait)
        clip = self._registry_or_default().status("clip_l14_image")
        if clip.state is not ModelState.READY:
            self._on_taste_trained(TasteStatus(False, "Chưa có mô hình CLIP nên chưa học được gu "
                                                      f"({clip.state.value}: {clip.path.name})"))
            return
        try:
            examples = store.taste_examples(CLIP_VERSION)
        except Exception:  # noqa: BLE001 - learning is optional
            log.exception("could not read taste examples")
            return
        job = _TasteJob(examples, self._taste_signals)
        if self._gate.open:
            self._taste_pool.start(job)
        if wait:
            self._taste_pool.waitForDone(30000)
            QCoreApplication.processEvents()

    def _on_taste_trained(self, status: TasteStatus) -> None:
        was_ready = self.taste.ready
        self.taste.set_status(status)
        log.info("taste model: %s", status.reason)
        if self.project is not None and (was_ready or self.taste.ready):
            self.reload_preserving_view()
        if self.project is not None:
            self._show_inspector(self.current_record())

    def _learn_client_picks(self, collection_id: int) -> None:
        """Client picks teach a little (they show the client's taste, not always the best photo)."""
        if self.project is None or self.teacher.store is None:
            return
        session = self._session_key()
        conn = self.project.conn
        recs = {r.id: r for r in self.model.records()}
        for (asset_id,) in conn.execute("SELECT asset_id FROM collection_items WHERE collection_id = ?",
                                        (collection_id,)).fetchall():
            rec = recs.get(asset_id)
            parts = dict(rec.score.parts) if rec is not None and rec.score is not None else {}
            day = (rec.capture_time or "")[:10] if rec is not None else ""
            self.teacher.client_picked(photo_key(session, asset_id, "client:"), parts,
                                       load_vector(conn, asset_id, "clip", CLIP_VERSION), group_key(session, day))

    def set_flag(self, flag: str | None) -> None:
        self._apply(lambda conn, rec: decisions.set_flag(conn, rec.id, flag), advance=flag is not None)

    def set_focus_label(self, label: str) -> None:
        """Q / W / R: the user's sharpness label (pressing the same key again clears it); teaches the focus model."""
        if self.project is None:
            return
        targets = self._targets()
        if not targets:
            return
        new = None if all(r.focus == label for r in targets) else label
        session = self._session_key()
        unmeasured = 0
        with self.project.transaction() as conn:
            for rec in targets:
                decisions.set_focus(conn, rec.id, new)
        conn = self.project.conn
        for rec in targets:
            measured = focus_learning.photo_focus(conn, rec.id)
            key = photo_key(session, rec.id, "focus:")
            if measured is None:
                unmeasured += 1
                self.teacher.focus_labeled(key, "", "", None, {})
                continue
            camera, features = measured
            self.teacher.focus_labeled(key, camera, group_key(session, (rec.capture_time or "")[:10]), new, features)
        for rec in targets:
            self.model.refresh_record(rec.id)
        self._show_inspector(self.current_record())
        if new is not None and unmeasured:
            self.status.setText(f"{unmeasured} ảnh chưa được 📊 Phân tích nên chưa dùng để học độ nét "
                                "(nhãn vẫn được lưu).")
        self._focus_labels_since_training += len(targets)
        if self._focus_labels_since_training >= FOCUS_RETRAIN_EVERY:
            self.retrain_focus()
        if new is not None and len(targets) == 1 and self.act_auto_advance.isChecked():
            self.step(1)

    def retrain_focus(self, wait: bool = False) -> None:
        """Train the per-camera sharpness models in the background (never on the Qt thread)."""
        store = self.teacher.store
        self._focus_labels_since_training = 0
        if store is None:
            return
        try:
            examples = store.focus_examples()
        except Exception:  # noqa: BLE001 - learning is optional
            log.exception("could not read sharpness examples")
            return
        job = _FocusJob(examples, self._focus_signals)
        if self._gate.open:
            self._taste_pool.start(job)
        if wait:
            self._taste_pool.waitForDone(30000)
            QCoreApplication.processEvents()

    def _on_focus_trained(self, statuses: dict) -> None:
        ready = lambda d: {c: (st.ready, st.model.accuracy if st.model else None) for c, st in d.items()}  # noqa: E731
        changed = ready(statuses) != ready(self.focus_status) or any(st.ready for st in statuses.values())
        self.focus_status = statuses
        focus_learning.use_models(statuses)
        log.info("focus models: %d cameras, %d ready", len(statuses), sum(st.ready for st in statuses.values()))
        if self.project is not None and changed:
            self.reload_preserving_view()
            self._show_inspector(self.current_record())

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
            picks = select.select_per_person(conn, n, ranker=self.taste.ranker(self.taste_weight()))
            params = {"mode": "per_person", "n": n}
        else:
            subject = target if flt is Filter.SUBJECT else None
            picks = select.select_in_view(conn, n, set(in_view), subject, ranker=self.taste.ranker(self.taste_weight()))
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
    def open_export_dialog(self, client_list: bool = False) -> ExportDialog | None:
        """``client_list``: start on "Danh sách khách" (the bottom bar's "Xuất theo danh sách khách…")."""
        if self.project is None:
            QMessageBox.information(self, "Xuất ảnh", "Hãy nhập một thư mục ảnh trước.")
            return None
        item = self.filters.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        collection_id = data[1] if data and data[0] is Filter.COLLECTION else None
        if client_list and collection_id is None:  # ask which list; never pick one for the user
            lists = list_collections(self.project.conn)
            if not lists:
                QMessageBox.information(self, "Xuất theo danh sách khách",
                                        "Chưa có danh sách khách nào. Bấm 📋 Khách chọn để dán danh sách của khách trước.")
                return None
            names = [f"{c['name']} ({c['n']} ảnh)" for c in lists]
            name, ok = QInputDialog.getItem(self, "Xuất theo danh sách khách", "Danh sách:", names, 0, False)
            if not ok or name not in names:
                return None
            collection_id = lists[names.index(name)]["id"]
        dialog = ExportDialog(self.project, [r.id for r in self.selected_records()], self, collection_id=collection_id,
                              settings=self.settings)
        dialog.gate = self._gate
        dialog.run_recorded.connect(self.refresh_steps)  # ✓ Xuất ảnh as soon as an export is recorded
        dialog.include_pairs.toggled.connect(lambda _on: self._update_counts())  # size follows "Kèm JPEG"
        dialog.show()
        return dialog

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self, "Phím tắt",
            "← / →   ảnh trước / sau (↑ ↓ trong lưới)\n"
            "Space / Enter   xem lớn ↔ lưới,  Esc   về lưới (hoặc đóng bộ lọc / bảng chi tiết đang mở ra)\n"
            "Z   zoom 100% (ảnh độ phân giải đầy đủ) ↔ vừa khung\n"
            "+ / −   phóng to / thu nhỏ (tới 800%),  cuộn chuột: phóng tại vị trí chuột\n"
            "E   phóng tới mắt của chủ thể chính (xem nét),  nháy đúp: 100% tại chỗ đó\n"
            "P / K   Chọn      X   Loại      U   Bỏ chọn\n"
            "Tab   hiện / ẩn bảng chi tiết (cửa sổ thấp: lưới ↔ chi tiết)\n"
            "1 – 5   chấm sao,  0   xoá sao\n"
            "F   Yêu thích\n"
            "Q   nét căng,  W   hơi soft,  R   lệch nét / rung (bấm lại để bỏ) — app học độ nét theo máy + ống kính\n"
            "Ctrl+I   nhập thư mục ảnh,  Ctrl+E   xuất ảnh\n"
            "Ctrl+F   tìm tên file,  Ctrl+L   danh sách khách chọn\n\n"
            "Trong lưới có thể đánh dấu nhiều ảnh (ô tick, Ctrl/Shift + click) rồi bấm P/X/số để áp dụng cho tất cả.\n"
            "Khi đang gõ trong ô tìm kiếm, các phím chữ và số chỉ để gõ — không chấm ảnh.",
        )


UNGUARDED = {"Escape", "F1"}  # work even while typing: close a drawer / sheet, open the key list


def typing_in(widget: QWidget | None) -> bool:
    """A text field (or an editable box) has the keyboard: plain keys are for typing, not for culling."""
    if isinstance(widget, QComboBox):
        return widget.isEditable()
    return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox))


def strip_text(rec: AssetRecord | None) -> str:
    """SHORT Grid Focus: the current photo in one line (the detail panel is hidden there)."""
    if rec is None:
        return ""
    badge, chip = card_texts(rec)
    parts = [rec.name] + ([badge] if badge and badge != "—" else []) + ([chip] if chip else [])
    if rec.rating:
        parts.append("★" * rec.rating)
    if rec.favorite:
        parts.append("♥")
    return "  ·  ".join(p for p in parts if p) + "     —  ▤ Chi tiết: xem phân tích và thông tin ảnh"


SWITCH_WAIT_MS = 10000  # switching folder: how long to wait for workers before refusing
CLOSE_WAIT_MS = 3000  # closing: blocking wait; afterwards a non-blocking one (GUI timer)
HUNG_AFTER_S = 15.0  # closing: ask whether to quit at once after this long
ANALYSIS_STOP_MS = 30000
EXIT_ABANDONED = 3  # "Thoát ngay" with work unfinished: not a clean exit (0), not a crash either


def quit_anyway_text(left: list[str]) -> str:
    """The question asked when background work does not stop; says exactly what may be left unfinished."""
    lines = [f"{', '.join(left).capitalize()} chưa dừng sau {HUNG_AFTER_S:.0f} giây.", "",
             "Thoát ngay?",
             "• Các lựa chọn Chọn/Loại, sao và yêu thích đã được lưu.",
             "• Ảnh gốc không bị ảnh hưởng."]
    if "nhập ảnh" in left or "phân tích AI" in left:
        lines.append("• Phần nhập ảnh / phân tích AI dở dang sẽ chạy tiếp ở lần mở sau.")
    if "sao chép ảnh xuất" in left:
        lines.append("• Việc xuất ảnh đang chép dở: file cuối cùng trong thư mục xuất có thể bị thiếu dữ liệu và "
                     "danh sách ảnh đã chép (CSV) chưa được ghi. Hãy xuất lại vào một thư mục mới.")
    lines += ["", "Bấm No để chờ thêm."]
    return "\n".join(lines)

def session_too_new_text() -> str:
    """A folder last opened by a newer KiraPick: its session database is never touched by this one."""
    return ("Thư mục này đã được mở bằng một phiên bản KiraPick mới hơn, nên bản này không mở được phần đã nhớ "
            "(lựa chọn, sao, kết quả AI).\n\nHãy cập nhật KiraPick (⚙ Tuỳ chọn → Cập nhật KiraPick).\n"
            "Ảnh gốc và dữ liệu đã nhớ không bị thay đổi.")


def session_open_failed_text(exc: BaseException) -> str:
    """Opening (or upgrading) a folder's session failed: a full disk gets its own advice."""
    if (isinstance(exc, OSError) and exc.errno == errno.ENOSPC) or "disk is full" in str(exc).lower():
        cause = "Ổ đĩa chứa dữ liệu của KiraPick đã đầy. Hãy giải phóng vài GB rồi mở lại thư mục."
    else:
        cause = f"Không mở được dữ liệu đã nhớ của thư mục này ({type(exc).__name__}). Hãy thử lại."
    return cause + "\nẢnh gốc không bị ảnh hưởng."


RETRAIN_EVERY = 20  # decisions between two trainings of the taste model
FOCUS_RETRAIN_EVERY = 5  # Q/W/R labels between two trainings of the sharpness models (small and fast)


class _FocusSignals(QObject):
    done = Signal(object)


class _FocusJob(QRunnable):
    """Runs in the pool; reports through the window's own signal object (never one the worker would delete)."""

    def __init__(self, examples: list, signals: _FocusSignals) -> None:
        super().__init__()
        self.examples = examples
        self.signals = signals

    def run(self) -> None:
        try:
            statuses = focus_learning.train_focus(self.examples)
        except Exception:  # noqa: BLE001 - never crash the app over learning
            log.exception("sharpness training failed")
            statuses = {}
        self.signals.done.emit(statuses)


class _TasteSignals(QObject):
    done = Signal(object)


class _TasteJob(QRunnable):
    """Runs in the pool; reports through the window's own signal object (never one the worker would delete)."""

    def __init__(self, examples: list, signals: _TasteSignals) -> None:
        super().__init__()
        self.examples = examples
        self.signals = signals

    def run(self) -> None:
        try:
            status = train(self.examples)
        except Exception as exc:  # noqa: BLE001 - never crash the app over learning
            log.exception("taste training failed")
            status = TasteStatus(False, f"Không học được gu ({type(exc).__name__})")
        self.signals.done.emit(status)
