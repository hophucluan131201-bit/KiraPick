"""Right-hand panel: file facts, culling state, and honest AI status."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from app.ui import theme
from app.ui.asset_model import AssetRecord

_SOURCE_VI = {
    "embedded_jpeg": "ảnh nhúng trong RAW",
    "embedded_bitmap": "ảnh nhúng trong RAW",
    "demosaic_half": "giải mã RAW (½)",
    "demosaic_full": "giải mã RAW",
    "raster": "file ảnh",
}


def _exposure(exif: dict) -> str:
    parts = []
    t = exif.get("exposure_time_s")
    if t:
        parts.append(f"1/{round(1 / t)}s" if t < 1 else f"{t:g}s")
    if exif.get("f_number"):
        parts.append(f"f/{exif['f_number']:g}")
    if exif.get("iso"):
        parts.append(f"ISO {exif['iso']}")
    if exif.get("focal_length_mm"):
        parts.append(f"{exif['focal_length_mm']:g}mm")
    return "  ".join(parts) or "—"


class Inspector(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        self.fields: dict[str, QLabel] = {}
        for title, keys in (
            ("ẢNH", ["Tên file", "Thư mục", "Cặp RAW+JPEG", "Chụp lúc", "Kích thước"]),
            ("MÁY ẢNH", ["Máy", "Ống kính", "Thông số"]),
            ("CHỌN LỌC", ["Đánh dấu", "Sao", "Yêu thích"]),
            ("PHÂN TÍCH AI", ["Chủ thể", "Điểm chất lượng"]),
            ("HIỂN THỊ", ["Nguồn ảnh"]),
        ):
            header = QLabel(title)
            header.setObjectName("sectionTitle")
            outer.addWidget(header)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            for key in keys:
                value = QLabel("—")
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow(QLabel(key), value)
                self.fields[key] = value
            outer.addLayout(form)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {theme.ERROR};")
        outer.addWidget(self.error)
        outer.addStretch(1)
        self.show_record(None)

    def show_record(self, rec: AssetRecord | None, view_source: str | None = None) -> None:
        f = self.fields
        if rec is None:
            for label in f.values():
                label.setText("—")
            self.error.clear()
            return
        f["Tên file"].setText(rec.name)
        f["Thư mục"].setText(str(rec.path.parent))
        f["Cặp RAW+JPEG"].setText(", ".join(rec.paired_with) or "—")
        when = rec.capture_time
        f["Chụp lúc"].setText(datetime.fromisoformat(when).strftime("%d/%m/%Y %H:%M:%S") if when else "không có")
        f["Kích thước"].setText(f"{rec.width}×{rec.height}" if rec.width else "—")
        f["Máy"].setText(rec.camera or "—")
        f["Ống kính"].setText(rec.lens or "—")
        f["Thông số"].setText(_exposure(rec.exif))
        flag = {"keep": "Giữ ✓", "reject": "Loại ✕"}.get(rec.flag or "", "chưa chọn")
        f["Đánh dấu"].setText(flag)
        f["Sao"].setText("★" * rec.rating if rec.rating else "chưa chấm")
        f["Yêu thích"].setText("♥ có" if rec.favorite else "không")
        # Honest status: these engines are not installed yet (milestones M2/M3).
        f["Chủ thể"].setText("chưa cài mô hình nhận diện (M2)")
        f["Điểm chất lượng"].setText("chưa có — chưa cài bộ phân tích (M3)")
        source = view_source or rec.preview_source
        f["Nguồn ảnh"].setText(_SOURCE_VI.get(source or "", source or "—"))
        self.error.setText(f"Lỗi: {rec.error}" if rec.error else "")
