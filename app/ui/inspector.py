"""Thông tin ảnh tab: file facts and culling state; full EXIF folded away until asked for.

``explain_html`` (the long text version of the scores) is kept for the selection dialog and tests."""

from __future__ import annotations

from datetime import datetime
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from app.ui import theme
from app.learning.taste import TasteStatus
from app.quality.rank import Ranked
from app.learning.focus import KEYS, LABELS as FOCUS_LABELS, NAMES as FOCUS_NAMES
from app.quality.score import LABELS, WEIGHTS, Score
from app.ui.asset_model import AssetRecord
from app.ui.collapsible import CollapsibleSection

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


def _bar(value: float) -> str:
    filled = int(round(value / 10))
    return "█" * filled + "░" * (10 - filled)


def explain_html(score: Score, ranked: Ranked | None = None, taste: TasteStatus | None = None,
                 pick_rank: int | None = None, selection: str | None = None) -> str:
    """Technical score and taste score, one bar + reason per criterion, then what was not judged."""
    tech = f"<b>Kỹ thuật {score.total:.0f}/100</b>" if score.total is not None else "<b>Kỹ thuật: chưa chấm được</b>"
    if ranked is not None and ranked.taste is not None:
        gu = f"<b>Hợp gu bạn {ranked.taste:.0f}/100</b>"
    else:
        gu = f"Hợp gu bạn: chưa có – {escape(taste.reason)}" if taste is not None else "Hợp gu bạn: chưa có"
    head = f"{tech} · {gu}"
    if pick_rank is not None:
        head += f"<br>⭐ AI chọn (thứ {pick_rank})"
    if selection:
        head += f"<br><i>{escape(selection)}</i>"
    rows = []  # plain wrapped lines (no table): readable in a narrow, half-screen window
    for key in WEIGHTS:
        value = score.parts.get(key)
        reason = escape(score.reasons.get(key, ""))
        if value is None:
            rows.append(f"<b>{LABELS[key]}</b> <span style='color:{theme.MUTED}'>{reason}</span>")
        else:
            rows.append(f"<b>{LABELS[key]} {value:.0f}</b> <tt>{_bar(value)}</tt>"
                        f"<br><span style='color:{theme.MUTED}'>{reason}</span>")
    body = "<br>" + "<br>".join(rows)
    if ranked is not None and ranked.taste is not None and taste is not None:
        body += f"<br><span style='color:{theme.MUTED}'>Hợp gu: {escape(taste.reason)}</span>"
    if ranked is not None and ranked.artistic:
        body += "<br>🎨 ngoại lệ nghệ thuật: ảnh cố ý mềm/tối và hợp gu bạn nên không bị trừ điểm"
    elif ranked is not None and ranked.capped:
        body += "<br>Lỗi nặng (mắt nhắm / thiếu nét) nên điểm xếp hạng không vượt điểm kỹ thuật"
    if score.weaknesses:
        body += f"<br><span style='color:{theme.REJECT}'><b>⚠ Điểm yếu chính:</b> {escape(score.weaknesses[0])}</span>"
    if score.not_rated:
        lines = "".join(f"<br>• {escape(i)}" for i in score.not_rated)
        body += f"<br><span style='color:{theme.MUTED}'><b>Chưa đánh giá</b></span>{lines}"
    return head + body


def breakable_path(path: str) -> str:
    """Let a long folder path wrap after each separator (a QLabel cannot break inside a word)."""
    return path.replace("\\", "\\\u200b").replace("/", "/\u200b")


class Inspector(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(220)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        self.fields: dict[str, QLabel] = {}
        for title, keys in (
            ("ẢNH", ["Tên file", "Chụp lúc", "Máy", "Ống kính", "Cặp RAW+JPEG", "Thư mục", "Kích thước"]),
            ("CHỌN LỌC", ["Đánh dấu", "Sao", "Yêu thích", "Bạn chấm nét"]),
            ("HIỂN THỊ", ["Nguồn ảnh"]),
        ):
            header = QLabel(title)
            header.setObjectName("sectionTitle")
            outer.addWidget(header)
            outer.addLayout(self._form(keys))
        exif_body = QWidget()
        exif_layout = QVBoxLayout(exif_body)
        exif_layout.setContentsMargins(0, 0, 0, 0)
        exif_layout.addLayout(self._form(["Thông số"]))
        self.exif_all = QLabel()
        self.exif_all.setWordWrap(True)
        self.exif_all.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.exif_all.setStyleSheet(f"color: {theme.MUTED};")
        exif_layout.addWidget(self.exif_all)
        self.exif_section = CollapsibleSection("Thông số EXIF", exif_body, "exif", None)  # never remembered
        outer.addWidget(self.exif_section)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {theme.ERROR};")
        outer.addWidget(self.error)
        outer.addStretch(1)
        self.show_record(None)

    def _form(self, keys: list[str]) -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for key in keys:
            value = QLabel("—")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(QLabel(key), value)
            self.fields[key] = value
        return form

    def show_record(self, rec: AssetRecord | None, view_source: str | None = None) -> None:
        f = self.fields
        if rec is None:
            for label in f.values():
                label.setText("—")
            self.exif_all.clear()
            self.error.clear()
            return
        f["Tên file"].setText(rec.name)
        f["Thư mục"].setText(breakable_path(str(rec.path.parent)))
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
        f["Bạn chấm nét"].setText(f"{FOCUS_NAMES[FOCUS_LABELS[rec.focus]]} ({KEYS[rec.focus]})" if rec.focus
                                  else "chưa — Q nét căng · W hơi soft · R lệch nét")
        self.exif_all.setText("\n".join(f"{k}: {v}" for k, v in sorted(rec.exif.items()) if v not in (None, ""))
                              or "không có dữ liệu EXIF")
        source = view_source or rec.preview_source
        f["Nguồn ảnh"].setText(_SOURCE_VI.get(source or "", source or "—"))
        self.error.setText(f"Lỗi: {rec.error}" if rec.error else "")
