"""Right-hand detail panel: the photo's name and marks (read-only), preview, then four tabs.

Tabs: Phân tích AI (score card), Thông tin ảnh (file facts; full EXIF folded away until asked for),
Ảnh tương tự (photos taken within ±3 s of the same person — a time burst, not a visual comparison),
Chủ thể (who is in the photo, with the same actions as the grid's right-click menu).
The panel only shows and asks; MainWindow does the work (decisions, learning, people changes).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy,
    QTabWidget, QVBoxLayout, QWidget,
)

from app.learning.taste import TasteStatus
from app.ui import icons, theme
from app.ui.asset_model import AssetRecord
from app.ui.grid import card_texts
from app.ui.inspector import Inspector
from app.ui.score_card import ScoreCard

TABS = ("Phân tích AI", "Thông tin ảnh", "Ảnh tương tự", "Chủ thể")
TABS_SHORT = ("AI", "Thông tin", "Tương tự", "Chủ thể")  # narrow panel: full titles in the tooltips
TABS_ICONS = ("sparkles", "info", "images", "user")  # narrowest panel: Lucide icons only (app.ui.icons)
BURST_ROW = 72  # one fixed row height in "Ảnh tương tự", with or without the thumbnail yet
TOP_MAX_W = 300  # SHORT (horizontal) layout: preview and buttons column
PREVIEW_MIN_H = 80
PREVIEW_HIDE_H = 40  # SHORT layout: below this the preview is hidden (title and tabs stay)
QWIDGETSIZE_MAX = 16777215
_PLACEHOLDER: QIcon | None = None


def _placeholder() -> QIcon:
    """Grey square shown in a burst row until its thumbnail arrives."""
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        pm = QPixmap(64, 64)
        pm.fill(QColor(theme.RAISED))
        _PLACEHOLDER = QIcon(pm)
    return _PLACEHOLDER
def marks_html(rec: AssetRecord | None) -> str:
    """"✓ Giữ ★★★ ♥" in the marks' colours; empty for no photo or no mark."""
    if rec is None:
        return ""
    parts = []
    if rec.flag == "keep":
        parts.append(f"<span style='color:{theme.KEEP}'>✓ Giữ</span>")
    elif rec.flag == "reject":
        parts.append(f"<span style='color:{theme.REJECT_ON_BUTTON}'>✕ Loại</span>")
    if rec.rating:
        parts.append(f"<span style='color:{theme.STAR}'>{'★' * rec.rating}</span>")
    if rec.favorite:
        parts.append(f"<span style='color:{theme.FAVORITE}'>♥</span>")
    return " ".join(parts)


BURST_HEADER = ("Ảnh chụp liền nhau (±3 giây, cùng chủ thể) — chỉ theo giờ chụp, "
                "không so sánh dáng hay nội dung ảnh")


class _Preview(QLabel):
    clicked = Signal()
    resized = Signal()

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)  # type: ignore[arg-type]
        self.resized.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


def _scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return area


class DetailPanel(QWidget):
    neighbour_clicked = Signal(int)  # asset id
    open_loupe = Signal()
    people_menu_requested = Signal(QPoint)  # global position for the people actions menu

    def __init__(self, parent: QWidget | None = None, pool: QThreadPool | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(240)
        self._box = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._box.setContentsMargins(6, 6, 6, 6)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("—")
        self.title.setStyleSheet("font-weight: bold;")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)  # never takes the preview's room
        self.preview = _Preview()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(PREVIEW_MIN_H)  # sized from the panel in _size_preview
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview.setToolTip("Bấm để xem lớn (Space)")
        self.preview.clicked.connect(self.open_loupe)
        self.preview.resized.connect(self._fit_preview)
        self._pixmap: QPixmap | None = None
        # The photo's marks, read-only: Giữ / Loại, stars and ♥ are set with the keys or the bottom bar (one set of
        # marking buttons in the window: UX-2, owner approval 2026-11-13)
        self.marks = QLabel()
        self.marks.setTextFormat(Qt.TextFormat.RichText)
        # one line, fixed height: a rich-text label asks for height-for-width, and the block above the tabs then
        # laid the preview out over them
        self.marks.setFixedHeight(self.title.sizeHint().height())
        self.marks.setToolTip("Đánh dấu bằng phím P / X / U, 1–5, F hoặc các nút ở thanh dưới")
        title_row = QHBoxLayout()
        title_row.addWidget(self.title, 1)
        title_row.addWidget(self.marks)
        top_layout.addLayout(title_row)
        top_layout.addWidget(self.preview)
        self.top = top

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.score_card = ScoreCard(pool=pool)
        self.inspector = Inspector()
        self.exif_section = self.inspector.exif_section
        burst_page = QWidget()
        burst_layout = QVBoxLayout(burst_page)
        self.burst_header = QLabel(BURST_HEADER)
        self.burst_header.setWordWrap(True)
        self.burst_header.setStyleSheet(f"color: {theme.MUTED};")
        self.burst = QListWidget()
        self.burst.setIconSize(QSize(64, 64))
        self.burst.setUniformItemSizes(True)  # one row height, thumbnail or not
        self.burst.itemClicked.connect(lambda item: self.neighbour_clicked.emit(int(item.data(0x0100))))
        burst_layout.addWidget(self.burst_header)
        burst_layout.addWidget(self.burst, 1)
        people_page = QWidget()
        people_layout = QVBoxLayout(people_page)
        self.people_label = QLabel("—")
        self.people_label.setWordWrap(True)
        self.people_button = QPushButton("Sửa chủ thể của ảnh này…")
        self.people_button.setToolTip("Đúng chủ thể / bỏ khỏi chủ thể / gán sang chủ thể khác / tạo chủ thể mới "
                                      "(giống menu chuột phải trên ảnh)")
        self.people_button.clicked.connect(lambda: self.people_menu_requested.emit(
            self.people_button.mapToGlobal(self.people_button.rect().bottomLeft())))
        people_layout.addWidget(self.people_label)
        people_layout.addWidget(self.people_button)
        people_layout.addStretch(1)
        for page, name in zip((_scroll(self.score_card), _scroll(self.inspector), burst_page, people_page), TABS,
                              strict=True):
            self.tabs.addTab(page, name)

        self._shown_id: int | None = -1  # photo shown last (to tell a refresh from a change of photo)
        self._box.addWidget(top, 0)
        self._box.addWidget(self.tabs, 1)
        self.show_record(None, taste=None, people=None, neighbours=[])

    # ------------------------------------------------------------------ API
    @property
    def shown_id(self) -> int | None:
        """The photo the panel shows now (its buttons act on this one)."""
        return self._shown_id if self._shown_id != -1 else None

    def show_record(self, rec: AssetRecord | None, *, taste: TasteStatus | None, people: str | None,
                    neighbours: list[AssetRecord], pixmap: QPixmap | None = None, selection: str | None = None,
                    neighbour_pixmaps: dict[int, QPixmap] | None = None) -> None:
        self.title.setText(rec.name if rec is not None else "—")
        self._pixmap = pixmap
        self._fit_preview()
        self.marks.setText(marks_html(rec))
        self.people_button.setEnabled(rec is not None)
        self.score_card.show_record(rec, taste, selection)
        self.inspector.show_record(rec)
        shown_id = rec.id if rec is not None else None
        if shown_id != self._shown_id:  # another photo: EXIF folds again; a refresh of the same photo keeps it open
            self.exif_section.set_collapsed(True)
            self._shown_id = shown_id
        self.people_label.setText(people or ("chưa nhận diện — bấm Nhận diện chủ thể" if rec is not None else "—"))
        self.burst.clear()
        for other in neighbours:
            badge, chip = card_texts(other)
            item = QListWidgetItem(f"{other.name}  ·  {badge}" + (f"  ·  {chip}" if chip else ""))
            item.setData(0x0100, other.id)
            pm = (neighbour_pixmaps or {}).get(other.id)
            item.setIcon(QIcon(pm) if pm is not None else _placeholder())  # the thumbnail replaces it on arrival
            item.setSizeHint(QSize(0, BURST_ROW))
            self.burst.addItem(item)
        if rec is not None and not neighbours:
            empty = QListWidgetItem("Không có ảnh nào chụp liền trước/sau (±3 giây)")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.burst.addItem(empty)

    def update_thumbnail(self, asset_id: int, pixmap: QPixmap) -> None:
        """A thumbnail finished loading: the preview (if it is the photo shown) and its burst row use it."""
        if asset_id == self._shown_id:
            self._pixmap = pixmap
            self._fit_preview()
        for i in range(self.burst.count()):
            item = self.burst.item(i)
            if item.data(0x0100) == asset_id:
                item.setIcon(QIcon(pixmap))

    def open_exif(self) -> None:
        self.tabs.setCurrentIndex(TABS.index("Thông tin ảnh"))
        self.exif_section.set_collapsed(False)

    def set_horizontal(self, on: bool) -> None:
        """SHORT layouts: preview beside the tabs instead of above them (no widget is moved to another parent)."""
        self._box.setDirection(QBoxLayout.Direction.LeftToRight if on else QBoxLayout.Direction.TopToBottom)
        self.top.setMaximumWidth(TOP_MAX_W if on else QWIDGETSIZE_MAX)  # the tabs keep most of the width
        self._horizontal = on
        self._size_preview()

    def _size_preview(self) -> None:
        """An explicit preview height, so the block above the tabs always gets the room it needs (nothing in it
        overlaps) and the preview never takes the tabs' room: ≤ 35 % of the panel height, ~3:2 of the width."""
        spacing = max(0, self.top.layout().spacing())
        rest = self.title.sizeHint().height() + spacing  # the title row
        if getattr(self, "_horizontal", False):  # SHORT: very low windows hide the preview, never the title
            h = self.height() - rest - 12
            self.preview.setVisible(h >= PREVIEW_HIDE_H)
            self.preview.setFixedHeight(max(PREVIEW_HIDE_H, h))
            return
        self.preview.setVisible(True)
        h = min(int(self.width() * 0.66), int(self.height() * 0.35))
        self.preview.setFixedHeight(max(PREVIEW_MIN_H, h))
    def _fit_tabs(self) -> None:
        """Tab titles never need scroll arrows: short titles (full ones in tooltips) when the panel is narrow."""
        bar = self.tabs.tabBar()
        for i, name in enumerate(TABS):
            bar.setTabText(i, name)
            bar.setTabIcon(i, QIcon())
            bar.setTabToolTip(i, "")
        for titles in (TABS_SHORT, TABS_ICONS):
            if bar.sizeHint().width() <= self.tabs.width():
                return
            for i, (name, short) in enumerate(zip(TABS, titles, strict=True)):
                if titles is TABS_ICONS:
                    bar.setTabIcon(i, icons.icon(short))
                    bar.setTabText(i, "")
                else:
                    bar.setTabText(i, short)
                bar.setTabToolTip(i, name)

    # ------------------------------------------------------------- helpers
    def _fit_preview(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("")
            return
        size = self.preview.size()
        self.preview.setPixmap(self._pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._fit_tabs()
        self._size_preview()
        self._fit_preview()
