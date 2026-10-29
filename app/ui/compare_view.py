"""Compare mode (UI part 2): 2–4 marked photos side by side. Each tile is a part 1 ImageViewer (fit, true 100 %,
async full resolution, Xoay xem), zoomed on its own; the tile under the mouse pointer is the active photo
(spec: docs/superpowers/specs/2026-10-29-kirapick-compare-design.md)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.asset_model import AssetRecord
from app.ui.grid import card_texts
from app.ui.viewer import ImageViewer


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
        self.header = QLabel()
        self.header.setObjectName("compareHeader")
        self.header.setTextFormat(Qt.TextFormat.PlainText)
        self.viewer = ImageViewer(pool=pool, full_pool=full_pool, full_cache=1)
        self.viewer.back_button.hide()  # Compare has its own way back
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
