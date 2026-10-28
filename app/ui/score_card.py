"""Phân tích AI tab: score ring, suggestion, histogram, one bar per criterion, taste and focus rows.

Every number comes from app.ui.score_style, so the ring always shows exactly what the grid badge shows.
Criteria the AI could not measure are written as such; they never get a bar (no fake 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, QRectF, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.learning.focus import KEYS, LABELS as FOCUS_LABELS, NAMES as FOCUS_NAMES
from app.learning.taste import TasteStatus
from app.quality.histogram import Histogram, histogram
from app.quality.score import LABELS, WEIGHTS
from app.ui import theme
from app.ui.asset_model import AssetRecord
from app.ui.score_style import COLORS, band, chip_for, display_band, display_value, shown


class Ring(QWidget):
    """The big score number in a coloured ring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(84, 84)
        self.text, self.color, self.fraction = "—", COLORS["none"], 0.0

    def set(self, text: str, color: str, fraction: float) -> None:
        self.text, self.color, self.fraction = text, color, fraction
        self.update()

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(6, 6, 72, 72)
        p.setPen(QPen(QColor(theme.RAISED), 7))
        p.drawEllipse(box)
        if self.fraction > 0:
            p.setPen(QPen(QColor(self.color), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(box, 90 * 16, int(-360 * 16 * self.fraction))
        font = p.font()
        font.setPointSize(18)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(theme.TEXT))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.text)


class _HistSignals(QObject):
    done = Signal(int, object)  # token, Histogram | None


class _HistTask(QRunnable):
    def __init__(self, token: int, path: Path, signals: _HistSignals) -> None:
        super().__init__()
        self.token, self.path, self.signals = token, path, signals

    def run(self) -> None:
        try:
            with Image.open(self.path) as im:  # the preview as the app shows it, never with Xoay xem applied
                rgb = np.asarray(im.convert("RGB"))
            result: Histogram | None = histogram(rgb)
        except Exception:  # noqa: BLE001 - only the histogram is lost
            result = None
        self.signals.done.emit(self.token, result)


class HistogramWidget(QWidget):
    """Brightness curve of the preview, computed in a thread pool; a late result for another photo is dropped."""

    CACHE = 512

    def __init__(self, parent: QWidget | None = None, pool: QThreadPool | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(QSize(120, 46))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.data: Histogram | None = None
        self.token = 0
        # Keyed by the preview FILE (unique per session folder), not the asset id: ids restart at 1 in every session.
        self._key: Path | None = None
        self._cache: dict[Path, Histogram] = {}
        self._pool = pool or QThreadPool.globalInstance()
        self._signals = _HistSignals()
        self._signals.done.connect(self.deliver)

    def request(self, asset_id: int | None, preview: Path | None) -> None:
        self.token += 1
        self._key = preview if asset_id is not None else None
        self.data = self._cache.get(self._key) if self._key is not None else None
        if self.data is None and self._key is not None:
            self._pool.start(_HistTask(self.token, self._key, self._signals))
        self.update()

    def clear_cache(self) -> None:
        """A session was closed: its preview files may be deleted and their names reused."""
        self._cache.clear()

    def deliver(self, token: int, result: Histogram | None) -> None:
        if token != self.token:  # the user moved on to another photo
            return
        self.data = result
        if result is not None and self._key is not None:
            self._cache[self._key] = result
            while len(self._cache) > self.CACHE:
                self._cache.pop(next(iter(self._cache)))
        self.update()

    def wait(self, msecs: int = 5000) -> bool:
        return self._pool.waitForDone(msecs)

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(theme.RAISED), 1))
        p.drawRect(r)
        if self.data is None:
            return
        bins = self.data.bins
        path = QPainterPath()
        path.moveTo(r.left(), r.bottom())
        for i, v in enumerate(bins):
            path.lineTo(r.left() + r.width() * i / (len(bins) - 1), r.bottom() - r.height() * float(v))
        path.lineTo(r.right(), r.bottom())
        path.closeSubpath()
        fill = QColor(theme.MUTED)
        fill.setAlphaF(0.6)
        p.fillPath(path, fill)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORS["poor"]))
        if self.data.shadows >= 0.01:  # clipped shadows / highlights: small red end marks
            p.drawRect(QRectF(r.left(), r.top(), 3, r.height()))
        if self.data.highlights >= 0.01:
            p.drawRect(QRectF(r.right() - 3, r.top(), 3, r.height()))


class Bar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setMinimumWidth(60)
        self.value, self.color = 0.0, COLORS["none"]

    def set(self, value: float, color: str) -> None:
        self.value, self.color = value, color
        self.update()

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.RAISED))
        p.drawRoundedRect(r, 4, 4)
        p.setBrush(QColor(self.color))
        p.drawRoundedRect(QRectF(r.left(), r.top(), r.width() * self.value / 100, r.height()), 4, 4)


@dataclass
class Row:
    name: QLabel
    value: QLabel
    bar: Bar
    reason: QLabel


class ScoreCard(QWidget):
    def __init__(self, parent: QWidget | None = None, pool: QThreadPool | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        self.ring = Ring()
        top.addWidget(self.ring)
        head = QVBoxLayout()
        self.suggestion = QLabel()
        self.suggestion.setObjectName("suggestion")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.subtitle = QLabel()
        self.subtitle.setStyleSheet(f"color: {theme.MUTED};")
        for w in (self.suggestion, self.summary, self.subtitle):
            head.addWidget(w)
        head.addStretch(1)
        top.addLayout(head, 1)
        outer.addLayout(top)
        self.histogram = HistogramWidget(pool=pool)
        self.histogram_label = QLabel("Biểu đồ sáng tối (theo ảnh xem trước, không phải dữ liệu RAW)")
        self.histogram_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        self.histogram_label.setWordWrap(True)
        outer.addWidget(self.histogram)
        outer.addWidget(self.histogram_label)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(line)
        grid = QGridLayout()
        grid.setColumnStretch(2, 1)
        self.rows: dict[str, Row] = {}
        for i, key in enumerate(WEIGHTS):
            name, value, bar, reason = QLabel(LABELS[key].capitalize()), QLabel("—"), Bar(), QLabel()
            reason.setWordWrap(True)
            reason.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
            grid.addWidget(name, 2 * i, 0)
            grid.addWidget(value, 2 * i, 1, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(bar, 2 * i, 2)
            grid.addWidget(reason, 2 * i + 1, 0, 1, 3)
            self.rows[key] = Row(name, value, bar, reason)
        outer.addLayout(grid)
        self.taste_row = QLabel()
        self.taste_row.setWordWrap(True)
        self.focus_row = QLabel()
        self.focus_row.setWordWrap(True)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        self.notes.setTextFormat(Qt.TextFormat.RichText)
        for w in (self.taste_row, self.focus_row, self.notes):
            outer.addWidget(w)
        outer.addStretch(1)
        self.value_text = "—"
        self.ring_color = COLORS["none"]

    def show_record(self, rec: AssetRecord | None, taste: TasteStatus | None, selection: str | None = None) -> None:
        value = display_value(rec.ranked) if rec is not None else None
        self.value_text = "—" if value is None else str(value)
        self.ring_color = COLORS[display_band(rec.ranked if rec is not None else None)]
        self.ring.set(self.value_text, self.ring_color, (value or 0) / 100)
        self.histogram.request(rec.id if rec else None, rec.thumb_file if rec else None)
        chip = chip_for(rec.flag, rec.pick_rank is not None, rec.score, rec.ranked, rec.uncertain) if rec else None
        self.suggestion.setText({"suggested": "⭐ Đề xuất giữ", "review": "⚠ Xem lại", "keep": "✅ Bạn đã Chọn",
                                 "reject": "❌ Bạn đã Loại"}.get(chip.kind, "") if chip else "")
        self.suggestion.setStyleSheet(f"color: {chip.color}; font-weight: bold;" if chip else "")
        r = rec.ranked if rec is not None else None
        self.subtitle.setText(f"Kỹ thuật {shown(r.tech)} · Hợp gu {shown(r.taste)}"
                              if r is not None and r.taste is not None and r.tech is not None else "")
        s = rec.score if rec is not None else None
        if s is None:
            self.summary.setText("Chưa chấm — bấm 📊 Phân tích AI" if rec is not None else "")
        else:
            self.summary.setText(s.weaknesses[0].capitalize() if s.weaknesses else
                                 (s.strengths[0].capitalize() if s.strengths else ""))
        for key, row in self.rows.items():
            part = s.parts.get(key) if s is not None else None
            reason = s.reasons.get(key, "") if s is not None else ""
            if part is None:
                row.value.setText("— chưa đo được" if s is not None else "—")
                row.bar.setVisible(False)
            else:
                row.value.setText(str(shown(part)))
                row.bar.set(part, COLORS[band(part)])
                row.bar.setVisible(True)
            row.reason.setText(reason)
            row.reason.setVisible(bool(reason))
        if r is not None and r.taste is not None:
            self.taste_row.setText(f"Hợp gu cá nhân: {shown(r.taste)}/100")
        else:
            self.taste_row.setText(f"Hợp gu cá nhân: {taste.reason if taste is not None else 'chưa có'}")
        focus = rec.focus if rec is not None else None
        self.focus_row.setText("Bạn chấm nét: " + (f"{FOCUS_NAMES[FOCUS_LABELS[focus]]} ({KEYS[focus]})" if focus
                                                    else "chưa — Q nét căng · W hơi soft · R lệch nét"))
        notes = []
        if selection:
            notes.append(f"<i>{escape(selection)}</i>")
        if r is not None and r.artistic:
            notes.append("🎨 ngoại lệ nghệ thuật: ảnh cố ý mềm/tối và hợp gu bạn nên không bị trừ điểm")
        elif r is not None and r.capped:
            notes.append("Lỗi nặng (mắt nhắm / thiếu nét) nên điểm xếp hạng không vượt điểm kỹ thuật")
        if s is not None and s.not_rated:
            notes.append(f"<span style='color:{theme.MUTED}'><b>Chưa đánh giá:</b> "
                         + "; ".join(escape(i) for i in s.not_rated) + "</span>")
        self.notes.setText("<br>".join(notes))

    def text(self) -> str:
        """Everything the card says, as plain text (for tests and accessibility)."""
        parts = [self.suggestion.text(), self.value_text, self.subtitle.text(), self.summary.text()]
        for key, row in self.rows.items():
            parts.append(f"{LABELS[key]} {row.value.text()} {row.reason.text()}")
        parts += [self.taste_row.text(), self.focus_row.text(), self.notes.text()]
        return "\n".join(p for p in parts if p)
