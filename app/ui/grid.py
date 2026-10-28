"""Thumbnail grid/filmstrip cards: tick box (= Chọn), one score, one status chip, stars, ❤, file name.

Three different looks never share a visual: the current photo has a thick accent frame, photos marked for a
batch action (the UI selection) a light-blue tint, and a kept photo a filled green tick box.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPersistentModelIndex, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from app.ui import theme
from app.ui.asset_model import ROLE_RECORD, AssetRecord
from app.ui.score_style import COLORS, band, chip_for, display_value, hard_defect

TICK = 20  # tick box size in the grid (16 in the filmstrip)
FOOTER = 40  # stars/❤ row + file name under the picture


def card_texts(rec: AssetRecord) -> tuple[str, str | None]:
    """(score badge, status chip) exactly as painted: "75" / "⚠ 20" / "—", and e.g. "✅ Chọn" or None."""
    value = display_value(rec.ranked)
    badge = "—" if value is None else (("⚠ " if hard_defect(rec.score, rec.ranked) else "") + str(value))
    chip = chip_for(rec.flag, rec.pick_rank is not None, rec.score, rec.ranked, rec.uncertain)
    return badge, chip.text if chip is not None else None


class GridView(QListView):
    """A list view whose cards have a tick box; a click on it emits ``tick_clicked`` and nothing else."""

    tick_clicked = Signal(int, bool)  # asset id, Shift held

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        kinds = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick)
        if obj is self.viewport() and event.type() in kinds and isinstance(event, QMouseEvent) \
                and event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            idx = self.indexAt(pos)
            delegate = self.itemDelegate()
            if idx.isValid() and isinstance(delegate, ThumbnailDelegate) \
                    and delegate.tick_rect(self.visualRect(idx)).contains(pos):
                # Swallow press, release and double-click: the current photo and the marking stay as they were.
                if event.type() == QEvent.Type.MouseButtonPress:
                    rec = idx.data(ROLE_RECORD)
                    if rec is not None:
                        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                        self.tick_clicked.emit(rec.id, shift)
                return True
        return super().eventFilter(obj, event)


class ThumbnailDelegate(QStyledItemDelegate):
    def __init__(self, cell: int, parent: QWidget | None = None, *, caption: bool = True) -> None:
        super().__init__(parent)
        self.cell = cell
        self.caption = caption

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:
        return QSize(self.cell, self.cell + (FOOTER if self.caption else 0))

    def _picture(self, cell: QRect) -> QRect:
        return QRect(cell.left() + 6, cell.top() + 6, cell.width() - 12,
                     cell.height() - 12 - (FOOTER if self.caption else 0))

    def tick_rect(self, item: QRect) -> QRect:
        """Where the tick box is drawn inside an item rect (also the click target)."""
        size = TICK if self.caption else 16
        pic = self._picture(item.adjusted(3, 3, -3, -3))
        return QRect(pic.left() + 4, pic.top() + 4, size, size)

    def paint(self, p: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        rec: AssetRecord | None = index.data(ROLE_RECORD)
        if rec is None:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cell = option.rect.adjusted(3, 3, -3, -3)
        marked = bool(option.state & QStyle.StateFlag.State_Selected)
        view = self.parent()
        current = isinstance(view, QListView) and view.currentIndex().row() == index.row()
        path = QPainterPath()
        path.addRoundedRect(QRectF(cell), 6, 6)
        p.fillPath(path, QColor(theme.PANEL))
        if marked:  # UI selection: tint + thin outline
            tint = QColor(COLORS["accent"])
            tint.setAlphaF(0.25)
            p.fillPath(path, tint)
            p.setPen(QPen(QColor(COLORS["accent"]), 1))
            p.drawPath(path)
        if current:  # the photo shown in the detail panel: thick frame
            p.setPen(QPen(QColor(COLORS["accent"]), 3))
            p.drawPath(path)

        pic = self._picture(cell)
        pm = index.data(Qt.ItemDataRole.DecorationRole)
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(pic.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = pic.left() + (pic.width() - scaled.width()) // 2
            y = pic.top() + (pic.height() - scaled.height()) // 2
            p.setOpacity(0.45 if rec.flag == "reject" else 1.0)
            p.drawPixmap(x, y, scaled)
            p.setOpacity(1.0)
        else:
            p.setPen(QColor(theme.ERROR if rec.status == "error" else theme.MUTED))
            text = "Không đọc được ảnh" if rec.status == "error" else ("Đang tải…" if rec.status == "ok" else "Đang xử lý…")
            p.drawText(pic, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

        self._tick(p, rec, self.tick_rect(option.rect))
        self._badges(p, rec, pic)
        if self.caption:
            self._footer(p, rec, cell, current)
        p.restore()

    @staticmethod
    def _tick(p: QPainter, rec: AssetRecord, box: QRect) -> None:
        keep = rec.flag == "keep"
        p.setPen(QPen(QColor("#ffffff" if not keep else COLORS["good"]), 1.5))
        p.setBrush(QColor(COLORS["good"]) if keep else QColor(0, 0, 0, 110))
        p.drawRoundedRect(box, 4, 4)
        if keep:
            p.setPen(QColor("#ffffff"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, "✓")

    @staticmethod
    def _badges(p: QPainter, rec: AssetRecord, pic: QRect) -> None:
        bold = QFont(p.font())
        bold.setBold(True)
        p.setFont(bold)
        fm = p.fontMetrics()
        badge, chip_text = card_texts(rec)
        bw = fm.horizontalAdvance(badge) + 12
        badge_box = QRect(pic.right() - bw - 4, pic.bottom() - 26, bw, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORS[band(display_value(rec.ranked))]))
        p.drawRoundedRect(badge_box, 11, 11)
        p.setPen(QColor("#ffffff"))
        p.drawText(badge_box, Qt.AlignmentFlag.AlignCenter, badge)
        chip = chip_for(rec.flag, rec.pick_rank is not None, rec.score, rec.ranked, rec.uncertain)
        if chip is not None and chip_text and pic.width() >= 120:
            cw = fm.horizontalAdvance(chip_text) + 14
            chip_box = QRect(pic.right() - cw - 4, pic.top() + 4, cw, 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(chip.color))
            p.drawRoundedRect(chip_box, 11, 11)
            p.setPen(QColor("#1e1f22"))
            p.drawText(chip_box, Qt.AlignmentFlag.AlignCenter, chip_text)
        if rec.status == "error":
            p.setPen(QColor(theme.ERROR))
            p.drawText(QRect(pic.left() + 4, pic.bottom() - 26, 24, 24), Qt.AlignmentFlag.AlignCenter, "!")

    @staticmethod
    def _footer(p: QPainter, rec: AssetRecord, cell: QRect, current: bool) -> None:
        p.setFont(QFont(p.font().family(), p.font().pointSize()))
        row = QRect(cell.left() + 8, cell.bottom() - FOOTER + 2, cell.width() - 16, 18)
        stars = "★" * rec.rating
        p.setPen(QColor(theme.STAR))
        p.drawText(row, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, stars)
        p.setPen(QColor(theme.MUTED))  # the empty stars must not read as a rating
        empty = row.adjusted(p.fontMetrics().horizontalAdvance(stars), 0, 0, 0)
        p.drawText(empty, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "☆" * (5 - rec.rating))
        p.setPen(QColor(theme.FAVORITE if rec.favorite else theme.MUTED))
        p.drawText(row, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "♥" if rec.favorite else "♡")
        name = rec.name + ("  +" + ",".join(n.rsplit(".", 1)[-1].upper() for n in rec.paired_with)
                           if rec.paired_with else "")
        caption = QRect(cell.left() + 8, cell.bottom() - 21, cell.width() - 16, 20)
        p.setPen(QColor(theme.TEXT if current else theme.MUTED))
        p.drawText(caption, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, caption.width()))


def make_grid(parent: QWidget, cell: int) -> GridView:
    view = GridView(parent)
    view.setViewMode(QListView.ViewMode.IconMode)
    view.setResizeMode(QListView.ResizeMode.Adjust)
    view.setMovement(QListView.Movement.Static)
    view.setUniformItemSizes(True)
    view.setSpacing(2)
    view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
    view.setItemDelegate(ThumbnailDelegate(cell, view))
    view.setLayoutMode(QListView.LayoutMode.Batched)  # stays responsive with thousands of items
    view.setBatchSize(200)
    return view


def make_filmstrip(parent: QWidget, cell: int) -> GridView:
    view = GridView(parent)
    view.setFlow(QListView.Flow.LeftToRight)
    view.setWrapping(False)
    view.setViewMode(QListView.ViewMode.IconMode)
    view.setMovement(QListView.Movement.Static)
    view.setUniformItemSizes(True)
    view.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
    view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)  # Ctrl/Shift+click also under the loupe
    view.setItemDelegate(ThumbnailDelegate(cell, view, caption=False))
    view.setFixedHeight(cell + 24)
    return view
