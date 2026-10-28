"""Thumbnail grid/filmstrip cell rendering."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from app.ui import theme
from app.ui.asset_model import ROLE_RECORD, AssetRecord


def badge_text(rec: AssetRecord) -> str:
    """"K 78 · G 85": technical and taste scores; ⚠ when a hard defect caps the ranking."""
    r = rec.ranked
    if r is None or r.tech is None:
        return ""
    text = f"K {r.tech:.0f}" + (f" · G {r.taste:.0f}" if r.taste is not None else "")
    return ("⚠ " + text) if r.capped else text


class ThumbnailDelegate(QStyledItemDelegate):
    def __init__(self, cell: int, parent: QWidget | None = None, *, caption: bool = True) -> None:
        super().__init__(parent)
        self.cell = cell
        self.caption = caption

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:
        return QSize(self.cell, self.cell + (22 if self.caption else 0))

    def paint(self, p: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        rec: AssetRecord | None = index.data(ROLE_RECORD)
        if rec is None:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cell = option.rect.adjusted(3, 3, -3, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        bg = QColor(theme.RAISED if selected else theme.PANEL)
        if rec.flag == "reject":
            bg = bg.darker(130)
        path = QPainterPath()
        path.addRoundedRect(QRectF(cell), 6, 6)
        p.fillPath(path, bg)
        if selected:
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            p.drawPath(path)

        image_area = QRect(cell.left() + 6, cell.top() + 6, cell.width() - 12,
                           cell.height() - 12 - (22 if self.caption else 0))
        pm = index.data(Qt.ItemDataRole.DecorationRole)
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(image_area.size(), Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            x = image_area.left() + (image_area.width() - scaled.width()) // 2
            y = image_area.top() + (image_area.height() - scaled.height()) // 2
            if rec.flag == "reject":
                p.setOpacity(0.45)
            p.drawPixmap(x, y, scaled)
            p.setOpacity(1.0)
        else:
            p.setPen(QColor(theme.ERROR if rec.status == "error" else theme.MUTED))
            text = "Không đọc được ảnh" if rec.status == "error" else ("Đang tải…" if rec.status == "ok" else "Đang xử lý…")
            p.drawText(image_area, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

        self._badges(p, rec, image_area)
        if self.caption:
            p.setPen(QColor(theme.TEXT if selected else theme.MUTED))
            caption = QRect(cell.left() + 6, cell.bottom() - 22, cell.width() - 12, 20)
            name = rec.name + ("  +" + ",".join(n.rsplit(".", 1)[-1].upper() for n in rec.paired_with) if rec.paired_with else "")
            badge = badge_text(rec)
            badge_w = p.fontMetrics().horizontalAdvance(badge) + 8 if badge else 0
            if badge:
                p.setPen(QColor(theme.ERROR if rec.ranked and rec.ranked.capped else theme.STAR))
                p.drawText(caption, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, badge)
                p.setPen(QColor(theme.TEXT if selected else theme.MUTED))
            name_rect = QRect(caption.left(), caption.top(), caption.width() - badge_w, caption.height())
            p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, name_rect.width()))
        p.restore()

    @staticmethod
    def _badges(p: QPainter, rec: AssetRecord, area: QRect) -> None:
        font = QFont(p.font())
        font.setBold(True)
        p.setFont(font)
        if rec.flag:
            color = QColor(theme.KEEP if rec.flag == "keep" else theme.REJECT)
            badge = QRect(area.left() + 4, area.top() + 4, 22, 22)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(badge)
            p.setPen(QColor("#ffffff"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, "✓" if rec.flag == "keep" else "✕")
        if rec.favorite:
            p.setPen(QColor(theme.FAVORITE))
            p.drawText(QRect(area.right() - 26, area.top() + 2, 24, 24), Qt.AlignmentFlag.AlignCenter, "♥")
        if rec.pick_rank is not None:
            pill = QRect(area.left() + (30 if rec.flag else 4), area.top() + 4, 34, 22)
            p.setBrush(QColor(theme.STAR))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(pill, 11, 11)
            p.setPen(QColor("#1e1f22"))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, "AI")
        if rec.uncertain:
            badge = QRect(area.right() - 26, area.bottom() - 26, 22, 22)
            p.setBrush(QColor(theme.ERROR))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(badge)
            p.setPen(QColor("#1e1f22"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, "?")
        if rec.status == "error":
            p.setPen(QColor(theme.ERROR))
            p.drawText(QRect(area.right() - 26, area.bottom() - 26, 24, 24), Qt.AlignmentFlag.AlignCenter, "!")
        if rec.rating:
            p.setPen(QColor(theme.STAR))
            stars = QRect(area.left() + 4, area.bottom() - 22, area.width() - 8, 20)
            p.drawText(stars, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "★" * rec.rating)


def make_grid(parent: QWidget, cell: int) -> QListView:
    view = QListView(parent)
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


def make_filmstrip(parent: QWidget, cell: int) -> QListView:
    view = QListView(parent)
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
