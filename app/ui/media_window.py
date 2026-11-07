"""The Media event view (plan Mốc 1 M8): grid of one event, the three Mốc 1 filter groups (shot size, content, focus
warnings) + source / moment / state / P-X, keys, the moment strip, 🕒 camera clocks, 🧠 analysis, Ctrl+Z.

Reuses the Chụp cá nhân grid, thumbnails and large viewer; never imports the personal-mode analysis (Media models go
through MediaRegistry only, in app.media.analysis, run in a child process). AI labels show "(thử nghiệm)".

Keys (not while typing): P / K chọn, X loại, Backspace bỏ P/X, F ❤, Alt+0…5 sao, T / U / C cỡ cảnh Toàn / Trung / Cận,
1–5 nội dung (bấm lại để bỏ), Space ảnh lớn, ← → ảnh trước / sau, Ctrl+Z hoàn tác.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.media import analysis, browse, clock, moments
from app.media import cameras as cam
from app.media import labels as lb
from app.media.browse import MediaFilter
from app.media.event import MediaEvent
from app.media.undo import EventUndo
from app.ui import theme
from app.ui.asset_model import AssetListModel, AssetRecord
from app.ui.grid import FOOTER, ThumbnailDelegate, make_grid
from app.ui.viewer import ImageViewer

log = logging.getLogger(__name__)

CELL = 200
KEY_HELP = ("P chọn · X loại · Backspace bỏ · F ❤ · Alt+0…5 sao · T/U/C cỡ cảnh · 1–5 nội dung · Space ảnh lớn · "
            "Ctrl+Z hoàn tác")


def typing_in(widget: QWidget | None) -> bool:
    if isinstance(widget, QComboBox):
        return widget.isEditable()
    return isinstance(widget, QLineEdit)


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
        rows: list[AssetRecord] = []
        if self._project is not None:
            sql, params = browse.filter_sql(self.media_filter)
            params.update(min_rating=1, target_id=None)
            rows = self._load_rows(sql, params, search=False)
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


# ------------------------------------------------------------------------------------------------- threads
class MediaImportThread(QThread):
    progress = Signal(str, int, int)
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, event_folder: Path, root: Path) -> None:
        super().__init__()
        self.event_folder, self.root = event_folder, root
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        from dataclasses import asdict

        from app.storage.project import Project

        try:
            with Project.open(self.event_folder) as event:
                summary = cam.import_folder(event, self.root, progress=lambda p: self.progress.emit(p.phase, p.done,
                                                                                                    p.total),
                                            should_cancel=self._cancel.is_set)
            self.succeeded.emit(asdict(summary))
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("media import failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")


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


# ------------------------------------------------------------------------------------------------ the view
class EventView(QWidget):
    leave = Signal()  # back to the event list (the event is closed by the caller)

    def __init__(self, event: MediaEvent, parent: QWidget | None = None, *, analysis_runner=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.media_event = event
        self.undo = EventUndo(event)
        self._analysis_runner = analysis_runner
        self.import_thread: MediaImportThread | None = None
        self.analysis_thread: MediaAnalysisThread | None = None
        self._last_summary: dict | None = None

        # top bar
        self.back_button = QPushButton("⟵ Sự kiện")
        self.title = QLabel(event.event_name)
        bold = QFont(self.title.font())
        bold.setBold(True)
        bold.setPointSizeF(bold.pointSizeF() * 1.3)
        self.title.setFont(bold)
        self.import_button = QPushButton("📂 Nhập ảnh")
        self.clock_button = QPushButton("🕒 Máy ảnh & giờ")
        self.analyse_button = QPushButton("🧠 Phân tích sự kiện")
        self.export_button = QPushButton("⤴ Xuất ảnh")
        self.undo_button = QPushButton("↶ Hoàn tác")
        top = QHBoxLayout()
        for w in (self.back_button, self.title):
            top.addWidget(w)
        top.addStretch(1)
        for w in (self.import_button, self.clock_button, self.analyse_button, self.export_button, self.undo_button):
            top.addWidget(w)

        # filters
        self.shot_filter = self._combo([("Cỡ cảnh: tất cả", None), *((v, k) for k, v in lb.SHOT.items()),
                                        ("Chưa xác định", lb.UNKNOWN)])
        self.content_filter = self._combo([("Nội dung: tất cả", None), *((v, k) for k, v in lb.CONTENT.items()),
                                           ("Chưa gán nội dung", "none")])
        self.focus_filter = self._combo([("Lỗi nét: tất cả", None), *((v, k) for k, v in lb.FOCUS.items()),
                                         ("Không cảnh báo", "none"), ("Không đo được", lb.UNKNOWN)])
        self.state_filter = self._combo([("Trạng thái: tất cả", None), ("⏳ Đang phân tích", "waiting"),
                                         (f"AI gợi ý {lb.EXPERIMENTAL}", "suggested"), ("Đã xác nhận", "confirmed")])
        self.flag_filter = self._combo([("P/X: tất cả", None), ("P đã chọn", "keep"), ("X đã loại", "reject"),
                                        ("Chưa chọn", "unflagged")])
        self.camera_filter = QComboBox()
        self.moment_filter = QComboBox()
        filters = QHBoxLayout()
        for w in (self.shot_filter, self.content_filter, self.focus_filter, self.camera_filter, self.moment_filter,
                  self.state_filter, self.flag_filter):
            filters.addWidget(w)
            w.currentIndexChanged.connect(self._apply_filter)
        filters.addStretch(1)

        # moment strip
        self.moment_strip = QListWidget()
        self.moment_strip.setFlow(QListWidget.Flow.LeftToRight)
        self.moment_strip.setWrapping(False)
        self.moment_strip.setFixedHeight(64)
        self.moment_strip.itemClicked.connect(self._moment_clicked)
        self.split_button = QPushButton("✂ Tách tại đây")
        self.merge_button = QPushButton("⊕ Gộp với khoảnh khắc trước")
        self.rename_button = QPushButton("✎ Đổi tên")
        self.move_button = QPushButton("⚠ Chuyển")
        self.keep_button = QPushButton("⚠ Giữ")
        moment_row = QHBoxLayout()
        moment_row.addWidget(self.moment_strip, 1)
        for w in (self.split_button, self.merge_button, self.rename_button, self.move_button, self.keep_button):
            moment_row.addWidget(w)

        # grid / large view
        self.model = MediaAssetModel(self)
        self.grid = make_grid(self, CELL)
        self.grid.setItemDelegate(MediaDelegate(CELL, self.grid))
        self.grid.setModel(self.model)
        self.grid.setGridSize(QSize(CELL + 6, CELL + FOOTER + 6))
        self.viewer = ImageViewer(self)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.grid)
        self.stack.addWidget(self.viewer)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setMinimumWidth(240)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        middle = QHBoxLayout()
        middle.addWidget(self.stack, 1)
        middle.addWidget(self.details)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.TEXT};")
        keys = QLabel(KEY_HELP)
        keys.setStyleSheet(f"color: {theme.MUTED};")

        box = QVBoxLayout(self)
        box.addLayout(top)
        box.addLayout(filters)
        box.addLayout(moment_row)
        box.addLayout(middle, 1)
        box.addWidget(self.status)
        box.addWidget(keys)

        self.back_button.clicked.connect(self.request_leave)
        self.import_button.clicked.connect(self.choose_import)
        self.clock_button.clicked.connect(self.open_clock)
        self.analyse_button.clicked.connect(self.toggle_analysis)
        self.export_button.clicked.connect(self.open_export)
        self.undo_button.clicked.connect(self.undo_last)
        self.split_button.clicked.connect(self.split_here)
        self.merge_button.clicked.connect(self.merge_with_previous)
        self.rename_button.clicked.connect(self.rename_moment)
        self.move_button.clicked.connect(lambda: self._warning_action(True))
        self.keep_button.clicked.connect(lambda: self._warning_action(False))
        self.grid.selectionModel().currentChanged.connect(lambda *_: self._show_details())
        self.grid.doubleClicked.connect(lambda *_: self.toggle_large())
        self._build_shortcuts()
        self.model.set_project(event)
        self.refresh(keep_filter=False)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _combo(items: list[tuple[str, object]]) -> QComboBox:
        c = QComboBox()
        for text, data in items:
            c.addItem(text, data)
        return c

    def _build_shortcuts(self) -> None:
        def sc(key: str, fn) -> None:  # noqa: ANN001
            QShortcut(QKeySequence(key), self, lambda: None if typing_in(QApplication.focusWidget()) else fn(),
                      context=Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc("P", lambda: self.set_flag("keep"))
        sc("K", lambda: self.set_flag("keep"))
        sc("X", lambda: self.set_flag("reject"))
        sc("Backspace", lambda: self.set_flag(None))
        sc("F", self.toggle_favorite)
        for n in range(6):
            sc(f"Alt+{n}", lambda n=n: self.set_rating(n))
        for key, value in lb.SHOT_KEYS.items():
            sc(key, lambda v=value: self.set_shot(v))
        for key in lb.CONTENT_KEYS:
            sc(key, lambda k=key: self.toggle_content(k))
        sc("Space", self.toggle_large)
        sc("Right", lambda: self.step(1))
        sc("Left", lambda: self.step(-1))
        sc("Escape", lambda: self.stack.currentWidget() is self.viewer and self.toggle_large())
        QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), self, self.undo_last,
                  context=Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def selected_ids(self) -> list[int]:
        rows = sorted(i.row() for i in self.grid.selectionModel().selectedIndexes())
        ids = [self.model.records()[r].id for r in rows if r < len(self.model.records())]
        if not ids:
            cur = self.current_id()
            ids = [cur] if cur is not None else []
        return ids

    def current_id(self) -> int | None:
        rec = self.model.record(self.grid.currentIndex())
        return rec.id if rec is not None else None

    def select(self, asset_ids: list[int]) -> None:
        sm = self.grid.selectionModel()
        sm.clearSelection()
        first = True
        for a in asset_ids:
            idx = self.model.index_of(a)
            if idx.isValid():
                if first:
                    self.grid.setCurrentIndex(idx)
                    first = False
                sm.select(idx, sm.SelectionFlag.Select)

    def say(self, text: str) -> None:
        self.status.setText(text)

    # ------------------------------------------------------------------ refresh
    def refresh(self, keep_filter: bool = True) -> None:
        current, selected = self.current_id(), self.selected_ids()
        self._fill_sources()
        self._fill_moments()
        self.model.reload()
        if keep_filter and (current is not None or selected):
            self.select(selected or [current])
        elif self.model.rowCount():
            self.grid.setCurrentIndex(self.model.index(0))
        self.clock_button.setVisible(len(cam.cameras(self.media_event.conn)) >= 2)
        self._update_undo()
        self._show_details()
        p = analysis.progress_of(self.media_event.conn)
        if self.analysis_thread is None and not self.status.text():
            self.say(f"{p['total']} ảnh · đã phân tích {p['done']} · ⏳ {p['waiting']}")

    def _fill_sources(self) -> None:
        keep = self.camera_filter.currentData()
        self.camera_filter.blockSignals(True)
        self.camera_filter.clear()
        self.camera_filter.addItem("Nguồn máy: tất cả", None)
        for c in cam.cameras(self.media_event.conn):
            self.camera_filter.addItem(f"{c['display_name']} ({c['photos']})", c["id"])
        i = self.camera_filter.findData(keep)
        self.camera_filter.setCurrentIndex(max(0, i))
        self.camera_filter.blockSignals(False)

    def _fill_moments(self) -> None:
        keep = self.moment_filter.currentData()
        ms = moments.moments(self.media_event.conn)
        warnings = moments.warnings(self.media_event.conn)
        self.moment_filter.blockSignals(True)
        self.moment_filter.clear()
        self.moment_filter.addItem("Khoảnh khắc: tất cả", None)
        self.moment_strip.clear()
        for m in ms:
            pin = "📌 " if m.pinned else ""
            warn = sum(1 for a in m.assets if a in warnings)
            cover = lb.shot_coverage(self.media_event.conn, m.id)
            cover_text = " ".join(f"{lb.SHOT[k]}{'✓' if ok else '✗'}" for k, ok in cover.items())
            text = f"{pin}{m.name} · {len(m.assets)} ảnh" + (f" · ⚠{warn}" if warn else "") + f"\n{cover_text}"
            self.moment_filter.addItem(f"{pin}{m.name} ({len(m.assets)})", m.id)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self.moment_strip.addItem(item)
        i = self.moment_filter.findData(keep)
        self.moment_filter.setCurrentIndex(max(0, i))
        self.moment_filter.blockSignals(False)

    def _apply_filter(self) -> None:
        f = MediaFilter(shot=self.shot_filter.currentData(), content=self.content_filter.currentData(),
                        focus=self.focus_filter.currentData(), camera_id=self.camera_filter.currentData(),
                        moment_id=self.moment_filter.currentData(), state=self.state_filter.currentData(),
                        flag=self.flag_filter.currentData())
        self.model.set_media_filter(f)
        if self.model.rowCount():
            self.grid.setCurrentIndex(self.model.index(0))
        self._show_details()

    def _moment_clicked(self, item: QListWidgetItem) -> None:
        i = self.moment_filter.findData(item.data(Qt.ItemDataRole.UserRole))
        self.moment_filter.setCurrentIndex(i if i != self.moment_filter.currentIndex() else 0)

    def _show_details(self) -> None:
        a = self.current_id()
        if a is None:
            self.details.setText("")
            return
        conn = self.media_event.conn
        rec = self.model.record(self.grid.currentIndex())
        lines = [f"<b>{rec.name}</b>" if rec else ""]
        cam_id = cam.camera_of(conn, a)
        names = {c["id"]: c["display_name"] for c in cam.cameras(conn)}
        lines.append(f"Nguồn: {names.get(cam_id, cam.UNKNOWN_CAMERA)}")
        t = clock.corrected_times(conn).get(a)
        if t is not None:
            from datetime import datetime

            lines.append(f"Giờ đã chỉnh: {datetime.fromtimestamp(t).strftime('%H:%M:%S')}")
        m = moments.moment_of(conn, a)
        mname = next((x.name for x in moments.moments(conn) if x.id == m), None)
        if mname:
            lines.append(f"Khoảnh khắc: {mname}")
        info = self.model.info.get(a)
        if info is not None and info.waiting:
            lines.append("⏳ Đang phân tích (chưa có kết quả)")
        for grp, title in (("shot", "Cỡ cảnh"), ("content", "Nội dung"), ("focus", "Cảnh báo nét")):
            values = lb.labels_of(conn, a).get(grp, [])
            texts = []
            for value, state, _ in values:
                name = "Chưa xác định" if value == lb.UNKNOWN else lb.GROUPS[grp][value]
                if grp == "focus" and value == lb.UNKNOWN:
                    name = "không đo được"
                texts.append(name + (f" {lb.EXPERIMENTAL}" if state == "suggested" else " ✓" if state == "confirmed"
                                     else ""))
            lines.append(f"{title}: {', '.join(texts) if texts else '—'}")
        booth = lb.booth_of(conn, a)
        if booth:
            lines.append(f"Booth: {booth[0]}" + (" (gợi ý)" if booth[1] == "suggested" else ""))
        warn = moments.warnings(conn).get(a)
        if warn is not None:
            lines.append("⚠ lệch giờ: có thể thuộc khoảnh khắc khác (⚠ Chuyển / ⚠ Giữ)")
        self.details.setText("<br>".join(lines))
        if self.stack.currentWidget() is self.viewer and rec is not None:
            self.viewer.show_photo(rec.path)

    def _update_undo(self) -> None:
        label = self.undo.next_label()
        self.undo_button.setEnabled(label is not None)
        self.undo_button.setToolTip(f"Hoàn tác: {label}" if label else "")

    def _after_action(self, text: str | None = None) -> None:
        self.refresh()
        if text:
            self.say(text)

    # ------------------------------------------------------------------ decisions
    def set_flag(self, flag: str | None) -> None:
        ids = self.selected_ids()
        if ids:
            self.undo.set_flag(ids, flag)
            for a in ids:
                self.model.refresh_record(a)
            self._update_undo()

    def set_rating(self, n: int) -> None:
        ids = self.selected_ids()
        if ids:
            self.undo.set_rating(ids, n)
            for a in ids:
                self.model.refresh_record(a)
            self._update_undo()

    def toggle_favorite(self) -> None:
        ids = self.selected_ids()
        if ids:
            rec = self.model.record(self.grid.currentIndex())
            self.undo.set_favorite(ids, not (rec.favorite if rec else False))
            for a in ids:
                self.model.refresh_record(a)
            self._update_undo()

    # ------------------------------------------------------------------ labels
    def set_shot(self, value: str) -> None:
        ids = self.selected_ids()
        if ids:
            self.undo.media(lb.confirm, ids, "shot", value)
            self.model.refresh_info()
            self._after_action(f"Đã gán {lb.SHOT[value]} cho {len(ids)} ảnh.")

    def toggle_content(self, key: str) -> None:
        ids = self.selected_ids()
        if ids:
            self.undo.media(lb.toggle_content, ids, key)
            self.model.refresh_info()
            self._after_action(f"{lb.CONTENT[lb.CONTENT_KEYS[key]]}: {len(ids)} ảnh.")

    # ------------------------------------------------------------------ moments
    def split_here(self) -> None:
        a = self.current_id()
        if a is None:
            return
        try:
            self.undo.media(moments.split_here, a)
        except ValueError as exc:
            self.say(str(exc))
            return
        self._after_action("Đã tách khoảnh khắc (📌).")

    def merge_with_previous(self) -> None:
        a = self.current_id()
        m = moments.moment_of(self.media_event.conn, a) if a is not None else None
        ms = [x.id for x in moments.moments(self.media_event.conn)]
        if m is None or ms.index(m) == 0:
            self.say("Không có khoảnh khắc trước để gộp.")
            return
        self.undo.media(moments.merge, ms[ms.index(m) - 1], m)
        self._after_action("Đã gộp với khoảnh khắc trước (📌).")

    def rename_moment(self, name: str | None = None) -> None:
        a = self.current_id()
        m = moments.moment_of(self.media_event.conn, a) if a is not None else None
        if m is None:
            return
        if name is None:
            name, ok = QInputDialog.getText(self, "Đổi tên khoảnh khắc", "Tên mới:")
            if not ok:
                return
        if name.strip():
            self.undo.media(moments.rename, m, name.strip())
            self._after_action("Đã đổi tên khoảnh khắc (📌).")

    def _warning_action(self, move: bool) -> None:
        warned = [a for a in self.selected_ids() if a in moments.warnings(self.media_event.conn)]
        if not warned:
            self.say("Chọn ảnh có ⚠ lệch giờ trước.")
            return
        for a in warned:
            self.undo.media(moments.accept_warning if move else moments.keep_warning, a)
        self._after_action(("Đã chuyển " if move else "Đã giữ ") + f"{len(warned)} ảnh.")

    # ------------------------------------------------------------------ undo
    def undo_last(self) -> None:
        if typing_in(QApplication.focusWidget()):
            return
        done = self.undo.undo()
        if done is None:
            self.say("Không còn gì để hoàn tác.")
            return
        text = f"Đã hoàn tác: {done.label}."
        if done.notice:
            text += " " + done.notice
        if done.kind == "decision":
            for a in done.assets:
                self.model.refresh_record(a)
            self._update_undo()
            self.say(text)
        else:
            self._after_action(text)

    # ------------------------------------------------------------------ view
    def toggle_large(self) -> None:
        if self.stack.currentWidget() is self.grid:
            rec = self.model.record(self.grid.currentIndex())
            if rec is None:
                return
            self.stack.setCurrentWidget(self.viewer)
            self.viewer.show_photo(rec.path)
        else:
            self.stack.setCurrentWidget(self.grid)
            self.grid.setFocus()

    def step(self, delta: int) -> None:
        row = self.grid.currentIndex().row() + delta
        if 0 <= row < self.model.rowCount():
            self.grid.setCurrentIndex(self.model.index(row))
            self.grid.selectionModel().clearSelection()

    # ------------------------------------------------------------------ import / clock / analysis / export
    def choose_import(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục ảnh của sự kiện")
        if folder:
            self.start_import(Path(folder))

    def start_import(self, folder: Path) -> MediaImportThread:
        if self.import_thread is not None:
            self.say("Đang nhập ảnh, chờ xong rồi nhập thư mục tiếp.")
            return self.import_thread
        t = MediaImportThread(self.media_event.folder, folder)
        t.progress.connect(lambda phase, done, total: self.say(f"Đang nhập ảnh: {done}/{total}"))
        t.succeeded.connect(self._import_done)
        t.failed.connect(lambda msg: self._import_done(None, msg))
        self.import_thread = t
        self.import_button.setEnabled(False)
        t.start()
        return t

    def _import_done(self, summary: dict | None, error: str | None = None) -> None:
        if self.import_thread is not None:
            self.import_thread.wait()
        self.import_thread = None
        self.import_button.setEnabled(True)
        self.say(f"Nhập ảnh lỗi: {error}" if error else "Đã nhập ảnh. Ảnh xếp theo giờ đã chỉnh.")
        self.refresh(keep_filter=False)
        if error is None and len(cam.cameras(self.media_event.conn)) >= 2:
            self.say("Đã nhập ảnh từ nhiều máy: bấm 🕒 Máy ảnh & giờ để chỉnh giờ (hoặc bỏ qua).")

    def open_clock(self) -> None:
        dialog = ClockDialog(self.media_event, self.selected_ids(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_clock(dialog.changes())

    def apply_clock(self, changes: dict[int, float]) -> None:
        for camera_id, seconds in changes.items():
            self.undo.media(moments.set_clock, camera_id, seconds)
        if changes:
            n = len(moments.warnings(self.media_event.conn))
            self._after_action("Đã chỉnh giờ." + (f" {n} ảnh ⚠ lệch giờ cần xem." if n else ""))

    def toggle_analysis(self) -> None:
        if self.analysis_thread is not None:
            self.analysis_thread.cancel()
            self.say("Đang tạm dừng phân tích… phần đã xong được giữ.")
            return
        self.start_analysis()

    def start_analysis(self, prefer_gpu: bool = True) -> MediaAnalysisThread:
        t = MediaAnalysisThread(self.media_event.folder, prefer_gpu, self._analysis_runner)
        t.progress.connect(self._analysis_progress)
        t.succeeded.connect(self._analysis_done)
        t.failed.connect(lambda msg: self._analysis_done(None, msg))
        self.analysis_thread = t
        self.analyse_button.setText("⏸ Tạm dừng")
        self.say("Đang phân tích sự kiện… vẫn duyệt ảnh được; nhãn hiện dần.")
        t.start()
        return t

    def _analysis_progress(self, done: int, total: int) -> None:
        self.say(f"Đang phân tích: {done}/{total} ảnh")
        if done % 20 == 0 or done == total:
            self.model.refresh_info()

    def _analysis_done(self, summary: dict | None, error: str | None = None) -> None:
        if self.analysis_thread is not None:
            self.analysis_thread.wait()
        self.analysis_thread = None
        self._last_summary = summary
        self.analyse_button.setText("🧠 Phân tích sự kiện")
        self.refresh()
        if error:
            self.say(f"Phân tích lỗi: {error}")
        elif summary is not None and summary.get("unavailable"):
            self.say(summary["unavailable"])
        elif summary is not None:
            text = (f"Đã phân tích {summary['analysed']} ảnh" + (f", {summary['failed']} ảnh lỗi" if summary["failed"]
                                                               else "")
                    + (". Đã tạm dừng: bấm lại để chạy tiếp." if summary["cancelled"]
                       else f". {summary['moments']} khoảnh khắc.") + f" Nhãn AI là {lb.EXPERIMENTAL}.")
            self.say(text)

    def open_export(self) -> None:
        from app.ui.media_export import MediaExportDialog

        MediaExportDialog(self.media_event, self).exec()

    # ------------------------------------------------------------------ leaving
    def busy(self) -> bool:
        return self.import_thread is not None or self.analysis_thread is not None

    def request_leave(self) -> None:
        if self.busy():
            self.say("Đang nhập hoặc phân tích: bấm ⏸ Tạm dừng và chờ dừng hẳn rồi quay lại.")
            return
        self.viewer.stop_pending()
        self.model.stop_pending()
        self.leave.emit()

    def stop_all(self, msecs: int = 30000) -> None:
        for t in (self.import_thread, self.analysis_thread):
            if t is not None:
                t.cancel()
                t.wait(msecs)
        self.viewer.stop_pending()
        self.model.stop_pending()

