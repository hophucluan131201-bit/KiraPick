"""People list rows: avatar, name (elided, full name in the tooltip) and the photo count as a badge."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from app.ui import theme

SEPARATOR = "  ·  "


def split_label(text: str) -> tuple[str, str]:
    """"Chủ thể 1  ·  5 ảnh  ·  2?" -> ("Chủ thể 1", "5 ảnh · 2?")."""
    name, sep, rest = text.partition(SEPARATOR)
    return (name, rest.replace(SEPARATOR, " · ")) if sep else (text, "")


class PeopleDelegate(QStyledItemDelegate):
    def paint(self, p: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        name, count = split_label(str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        count = count.replace(" ảnh", "").replace(" gợi ý", "")  # the badge is just the number: names get the room
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        badge_w = 0
        if count:
            badge_w = opt.fontMetrics.horizontalAdvance(count) + 14
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, p, opt.widget)
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget) if style else opt.rect
        text_rect = QRect(text_rect.left(), text_rect.top(), max(0, text_rect.width() - badge_w), text_rect.height())
        p.save()
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   opt.fontMetrics.elidedText(name, Qt.TextElideMode.ElideRight, text_rect.width()))
        if count:
            badge = QRect(opt.rect.right() - badge_w, opt.rect.center().y() - 10, badge_w - 4, 20)
            p.setPen(Qt.PenStyle.NoPen)
            fill = QColor(theme.MUTED)
            fill.setAlpha(60)
            p.setBrush(fill)
            p.drawRoundedRect(badge, 9, 9)
            p.setPen(QColor(theme.TEXT))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, count)
        p.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(min(hint.width(), 120), max(hint.height(), 60))  # never wider than the panel needs
