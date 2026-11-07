"""Media parts used by the event window (app.ui.media_event_window.EventWindow, the Chụp cá nhân 3.0.0 window):
the grid model with the Media filters, the card badges, the analysis thread and the 🕒 camera clock dialog.

Never imports the personal-mode analysis (Media models go through MediaRegistry only, in app.media.analysis, run in
a child process). AI labels show "(thử nghiệm)".
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QRect, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.media import browse, clock
from app.media import cameras as cam
from app.media import labels as lb
from app.media.browse import MediaFilter
from app.media.event import MediaEvent
from app.ui import theme
from app.ui.asset_model import _FILTER_SQL, AssetListModel, AssetRecord
from app.ui.grid import ThumbnailDelegate

log = logging.getLogger(__name__)

SAMPLE_HELP = ("Dán nhãn mẫu (để chấm AI, không đổi nhãn làm việc): Alt+T/U/C cỡ cảnh · Alt+1–5 nội dung · Q nét · "
               "W out nét · R trật nét · B ảnh này bắt đầu khoảnh khắc mới · Alt+0 chưa đánh giá. Bấm lại để bỏ.")


# ----------------------------------------------------------------------------------------------- model / cards
class MediaAssetModel(AssetListModel):
    """The personal-mode list model with Media filters and corrected-time order."""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.media_filter = MediaFilter()
        self.info: dict[int, browse.CardInfo] = {}

    def set_media_filter(self, f: MediaFilter) -> None:
        self.media_filter = f
        self.reload()

    def reload(self) -> None:
        """The 3.0.0 filters (Tất cả / Chưa chọn / Giữ / Loại / Yêu thích / sao / lỗi, folder, file name) and the
        Media filters together; corrected-time order."""
        rows: list[AssetRecord] = []
        if self._project is not None:
            params: dict = {"min_rating": self._min_rating, "target_id": self._target_id}
            extra = _FILTER_SQL.get(self._filter, "")
            if self._source_id is not None:
                extra += " AND a.source_id = :source_id"
                params["source_id"] = self._source_id
            sql, media_params = browse.filter_sql(self.media_filter)
            params.update(media_params)
            rows = self._load_rows(extra + sql, params, search=True)
            order = browse.time_order(self._project.conn)
            rows.sort(key=lambda r: order.get(r.id, len(order)))
            self.info = browse.card_info(self._project.conn)
        self.beginResetModel()
        self._rows = rows
        self._row_of = {rec.id: i for i, rec in enumerate(rows)}
        self.endResetModel()

    def refresh_info(self) -> None:
        if self._project is not None:
            self.info = browse.card_info(self._project.conn)
            if self._rows:
                self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1))


class MediaDelegate(ThumbnailDelegate):
    """Cards without a score badge: shot size, focus warnings, ⏳ and ⚠ lệch giờ instead."""

    def _badges(self, p: QPainter, rec: AssetRecord, pic: QRect) -> None:  # type: ignore[override]
        model = self.parent().model() if self.parent() is not None else None
        info = model.info.get(rec.id) if isinstance(model, MediaAssetModel) else None
        if info is None:
            return
        font = QFont(p.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() * 0.9))
        p.setFont(font)
        fm = p.fontMetrics()
        y = pic.bottom() - 4
        for text in reversed(info.lines()):
            w = min(pic.width() - 8, fm.horizontalAdvance(text) + 10)
            box = QRect(pic.left() + 4, y - 18, w, 18)
            p.setPen(Qt.PenStyle.NoPen)
            warn = text.startswith("⚠")
            p.setBrush(QColor(theme.ERROR if warn else "#000000") if warn else QColor(0, 0, 0, 160))
            p.drawRoundedRect(box, 9, 9)
            p.setPen(QColor("#ffffff"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, fm.elidedText(text, Qt.TextElideMode.ElideRight, w - 6))
            y -= 21


class MediaAnalysisThread(QThread):
    progress = Signal(int, int)
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, event_folder: Path, prefer_gpu: bool = True, runner=None) -> None:  # noqa: ANN001
        super().__init__()
        self.event_folder, self.prefer_gpu = event_folder, prefer_gpu
        self._cancel = threading.Event()
        self._runner = runner  # tests: run in this process

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            if self._runner is not None:
                summary = self._runner(self.event_folder, self.progress.emit, self._cancel.is_set)
            else:
                from app.media.analysis_process import run_in_child

                summary = run_in_child(self.event_folder, self.prefer_gpu, self.progress.emit, self._cancel.is_set)
            self.succeeded.emit(summary)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


# ------------------------------------------------------------------------------------------------ dialogs
class ClockDialog(QDialog):
    """🕒 Máy ảnh & giờ: one offset per source, in seconds; or computed from two photos of the same moment."""

    def __init__(self, event: MediaEvent, selected: list[int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🕒 Máy ảnh & giờ")
        self.media_event = event
        self.spins: dict[int, QDoubleSpinBox] = {}
        form = QFormLayout()
        for c in cam.cameras(event.conn):
            spin = QDoubleSpinBox()
            spin.setRange(-86400 * 3, 86400 * 3)
            spin.setDecimals(0)
            spin.setSuffix(" giây")
            spin.setValue(clock.offset(event.conn, c["id"]))
            self.spins[c["id"]] = spin
            form.addRow(f"{c['display_name']} ({c['photos']} ảnh)", spin)
        box = QVBoxLayout(self)
        box.addWidget(QLabel("Giờ đã chỉnh = giờ chụp gốc + độ lệch. Ảnh gốc và EXIF không bị sửa."))
        box.addLayout(form)
        self.pair_button = QPushButton("Tính từ 2 ảnh đang chọn (cùng một lúc, hai máy)")
        self.pair_button.setEnabled(len(selected) == 2)
        self.pair_button.clicked.connect(lambda: self._from_pair(selected))
        box.addWidget(self.pair_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Bỏ qua")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def _from_pair(self, selected: list[int]) -> None:
        a, b = selected
        try:
            seconds = clock.offset_from_pair(self.media_event.conn, a, b)
        except ValueError as exc:
            QMessageBox.warning(self, "Máy ảnh & giờ", str(exc))
            return
        b_cam = cam.camera_of(self.media_event.conn, b)
        if b_cam in self.spins:
            self.spins[b_cam].setValue(seconds)  # the whole offset that makes both photos show the same time

    def changes(self) -> dict[int, float]:
        return {c: s.value() for c, s in self.spins.items() if s.value() != clock.offset(self.media_event.conn, c)}
