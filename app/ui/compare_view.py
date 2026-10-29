"""Compare mode (UI part 2): 2–4 marked photos side by side. Each tile is a part 1 ImageViewer (fit, true 100 %,
async full resolution, Xoay xem), zoomed on its own; the tile under the mouse pointer is the active photo
(spec: docs/superpowers/specs/2026-10-29-kirapick-compare-design.md)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from app.ui.asset_model import AssetRecord
from app.ui.compare_layout import MAX_PHOTOS, Arrangement, Mode, arrange, turned_size
from app.ui.grid import card_texts
from app.ui.layout_modes import DEBOUNCE_MS
from app.ui.viewer import ImageViewer

PANEL_DELAY_MS = 150  # the detail panel follows the active photo after the pointer rests this long
REARRANGE_MS = DEBOUNCE_MS  # resizing: re-arrange once the size settled (part 1's debounce)
GAP = 6


class CompareTile(QWidget):
    """One compared photo: a header line (number, name, Chọn / Loại, stars, ♥, note), the viewer, the AI line."""

    hovered = Signal(int)  # asset id, as soon as the pointer enters (the action target; no delay)

    def __init__(self, parent: QWidget | None = None, *, pool: QThreadPool | None = None,
                 full_pool: QThreadPool | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("compareTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # the active frame is a stylesheet border
        self.asset_id: int | None = None
        self._record: AssetRecord | None = None
        self._number = 0
        self._note = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)  # sizes come from arrange()
        self.header = QLabel()
        self.header.setObjectName("compareHeader")
        self.header.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # never widens a tile
        self.header.setTextFormat(Qt.TextFormat.PlainText)
        self.viewer = ImageViewer(pool=pool, full_pool=full_pool, full_cache=1)
        self.viewer.back_button.hide()  # Compare has its own way back
        # A tile is resized whenever the page or the arrangement changes: the photo point at its centre stays.
        self.viewer.setResizeAnchor(ImageViewer.ViewportAnchor.AnchorViewCenter)
        self.ai_label = QLabel(self.viewer)
        self.ai_label.setObjectName("compareAi")
        self.ai_label.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addWidget(self.header)
        layout.addWidget(self.viewer, 1)

    # ------------------------------------------------------------ public
    def show_record(self, rec: AssetRecord, pixmap: QPixmap | None) -> None:
        """Show this photo (``pixmap``: the grid's thumbnail, shown until the preview arrives)."""
        self.asset_id = rec.id
        self._note = ""
        self.viewer.set_zoom(None)
        self.viewer.show_photo(rec.path, pixmap, max(rec.width or 0, rec.height or 0) or None, rec.rotation)
        self.update_record(rec)

    def update_record(self, rec: AssetRecord) -> None:
        """New decision, stars, ♥ (or Xoay xem) of the same photo: header and rotation only, no reload."""
        self._record = rec
        if rec.rotation != self.viewer._rotation and not self.viewer.set_rotation(rec.rotation):
            self.viewer.show_photo(rec.path, None, max(rec.width or 0, rec.height or 0) or None, rec.rotation)
        self._refresh_header()

    def set_number(self, n: int) -> None:
        self._number = n
        self._refresh_header()

    def set_active(self, on: bool) -> None:
        if self.property("active") is on:
            return
        self.setProperty("active", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_note(self, text: str) -> None:
        self._note = text
        self._refresh_header()

    def set_ai_text(self, text: str | None) -> None:
        self.ai_label.setVisible(text is not None)
        if text is not None:
            self.ai_label.setText(text)
            self.ai_label.adjustSize()
            self._place_ai()

    # ------------------------------------------------------------ Qt
    def enterEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().enterEvent(event)  # type: ignore[arg-type]
        if self.asset_id is not None:
            self.hovered.emit(self.asset_id)

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._place_ai()

    # ------------------------------------------------------------ helpers
    def _place_ai(self) -> None:
        self.ai_label.move(8, max(0, self.viewer.height() - self.ai_label.height() - 8))

    def _refresh_header(self) -> None:
        rec = self._record
        if rec is None:
            self.header.setText("")
            return
        _badge, chip = card_texts(rec)
        parts = [str(self._number) if self._number else "", rec.name, chip or "",
                 "★" * rec.rating, "♥" if rec.favorite else "", self._note]
        self.header.setText("   ".join(p for p in parts if p))


class CompareView(QWidget):
    """The Compare page: up to four tiles (created once, reused) on two single-thread decode pools.
    ``active_changed`` fires as soon as the pointer enters a tile (the action target); ``panel_photo_changed`` fires
    PANEL_DELAY_MS later, or at once when the pointer leaves the tiles."""

    active_changed = Signal(int)
    panel_photo_changed = Signal(int)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview_pool = QThreadPool(self)
        self.preview_pool.setMaxThreadCount(1)
        self.full_pool = QThreadPool(self)  # one full-resolution decode at a time (spec: Viewer resources)
        self.full_pool.setMaxThreadCount(1)
        self.back_button = QToolButton()
        self.back_button.setObjectName("backToGrid")
        self.back_button.setText("◀  Về lưới ảnh  (Esc)")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.back_requested.emit)
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.back_button)
        bar.addStretch(1)
        self.toolbar = bar
        self.page = QWidget()  # the tiles' area: its own size is what arrange() gets
        self.page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.page.installEventFilter(self)
        self.grid = QGridLayout(self.page)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(GAP)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(bar)
        layout.addWidget(self.page, 1)
        self.tiles: tuple[CompareTile, ...] = tuple(
            CompareTile(self.page, pool=self.preview_pool, full_pool=self.full_pool) for _ in range(MAX_PHOTOS))
        for tile in self.tiles:
            tile.hovered.connect(self._on_hovered)
            tile.hide()
        self._records: list[AssetRecord] = []
        self.active_id: int | None = None
        self._mode: Mode = "auto"
        self.arrangement: Arrangement | None = None
        self._panel_timer = QTimer(self)
        self._panel_timer.setSingleShot(True)
        self._panel_timer.setInterval(PANEL_DELAY_MS)
        self._panel_timer.timeout.connect(self._emit_panel)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(REARRANGE_MS)
        self._resize_timer.timeout.connect(self._rearrange)

    # ------------------------------------------------------------ public
    def show_records(self, records: list[AssetRecord], pixmaps: dict[int, QPixmap], active_id: int) -> None:
        """Show these 2–4 photos (tile order = list order); ``active_id`` starts as the active photo."""
        self.clear()
        self._records = list(records)
        for n, (tile, rec) in enumerate(zip(self.tiles, self._records, strict=False), start=1):
            tile.set_number(n)
            tile.show_record(rec, pixmaps.get(rec.id))
        self._rearrange()
        for tile in self.tiles[:len(self._records)]:
            tile.show()
        self._set_active(active_id)
        self._emit_panel()

    def clear(self) -> None:
        """Leave Compare: tiles hidden and emptied (their tokens change, so late results are dropped)."""
        self._panel_timer.stop()
        self._resize_timer.stop()
        for tile in self.tiles:
            tile.hide()
            tile.set_active(False)
            tile.asset_id = None
            tile.viewer.show_photo(None)
        self.preview_pool.clear()
        self.full_pool.clear()
        self._records = []
        self.active_id = None
        self.arrangement = None

    def tile(self, asset_id: int) -> CompareTile | None:
        return next((t for t in self.tiles if t.asset_id == asset_id and t.isVisibleTo(self)), None)

    def records(self) -> list[AssetRecord]:
        return list(self._records)

    def update_record(self, rec: AssetRecord) -> None:
        """A compared photo changed (decision, stars, ♥, Xoay xem): its tile updates; a turned size re-arranges."""
        index = next((i for i, r in enumerate(self._records) if r.id == rec.id), None)
        if index is None:
            return
        old = self._records[index]
        self._records[index] = rec
        self.tiles[index].update_record(rec)
        if turned_size(old.width, old.height, old.rotation) != turned_size(rec.width, rec.height, rec.rotation):
            self._rearrange()

    def set_arrangement(self, mode: Mode) -> None:
        self._mode = mode
        if self._records:
            self._rearrange()

    @property
    def mode(self) -> Mode:
        return self._mode

    # ------------------------------------------------------------ Qt
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if obj is self.page:
            if event.type() == QEvent.Type.Leave and self._panel_timer.isActive():
                self._panel_timer.stop()
                self._emit_panel()  # the pointer is on its way to the panel: show the active photo there now
            elif event.type() == QEvent.Type.Resize and self._records:
                self._resize_timer.start()
        return False

    # ------------------------------------------------------------ helpers
    def _on_hovered(self, asset_id: int) -> None:
        if asset_id != self.active_id:
            self._set_active(asset_id)
            self._panel_timer.start()

    def _set_active(self, asset_id: int) -> None:
        self.active_id = asset_id
        for tile in self.tiles:
            tile.set_active(tile.asset_id == asset_id and tile.asset_id is not None)
        self.active_changed.emit(asset_id)

    def _emit_panel(self) -> None:
        if self.active_id is not None:
            self.panel_photo_changed.emit(self.active_id)

    def _rearrange(self) -> None:
        """Place the tiles from arrange() on the page's own size; zoomed tiles keep their level and centre point."""
        n = len(self._records)
        if not n:
            return
        kept = {}
        for tile in self.tiles[:n]:
            v = tile.viewer
            w, h = v.pixmap_size()
            if v.zoom is not None and w and h:
                c = v.mapToScene(v.viewport().rect().center())
                kept[tile] = (v.zoom, QPointF(c.x() / w, c.y() / h))
        sizes = [turned_size(r.width, r.height, r.rotation) for r in self._records]
        size = self.page.size()
        self.arrangement = arrange(sizes, (size.width(), size.height()), self._mode, gap=GAP)
        for tile in self.tiles:
            self.grid.removeWidget(tile)
        for i in range(MAX_PHOTOS):
            self.grid.setRowStretch(i, 0)
            self.grid.setColumnStretch(i, 0)
        for tile, cell in zip(self.tiles, self.arrangement.cells, strict=False):
            self.grid.addWidget(tile, cell.row, cell.col, cell.row_span, cell.col_span)
        for r in range(self.arrangement.rows):
            self.grid.setRowStretch(r, 1)
        for c in range(self.arrangement.cols):
            self.grid.setColumnStretch(c, 1)
        self.grid.activate()
        for tile, (zoom, point) in kept.items():
            tile.viewer.set_zoom(zoom, point)
