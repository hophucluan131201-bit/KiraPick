"""The Media event window: the Chụp cá nhân 3.0.0 window (app.ui.main_window.MainWindow) opened on an event.

Review 2026-11-07: Media uses the same interface language and the same components as Chụp cá nhân — top bar, grid
and cards with the tick box, large view with filmstrip, Compare, detail panel, bottom bar (Chọn / Loại / Bỏ chọn,
stars, So sánh, Xoay xem, EXIF, Xuất bản sao), menus, every 3.0.0 key, Ctrl+Z, search, card size. What only Media
has lives in the sidebar (event, cameras & clock, event filters, moments) and in the grid's right-click menu, plus
Alt keys for labels (Alt+T/U/C cỡ cảnh, Alt+1–5 nội dung). Q / W / R keep their 3.0.0 meaning (nét / soft / lệch nét)
and set the Media focus labels. The 🧠 step runs "Phân tích sự kiện" (MediaRegistry models only, child process).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME
from app.media import analysis, browse, moments
from app.media import cameras as cam
from app.media import labels as lb
from app.media.browse import MediaFilter
from app.media.event import MediaEvent
from app.media.undo import EventUndo
from app.storage.workflow import StepState, steps
from app.ui.asset_model import AssetRecord, Filter
from app.ui.collapsible import CollapsibleSection
from app.ui.detail_panel import TABS
from app.ui.main_window import MainWindow, typing_in
from app.ui.media_window import (
    SAMPLE_HELP,
    ClockDialog,
    MediaAnalysisThread,
    MediaAssetModel,
    MediaDelegate,
)

log = logging.getLogger(__name__)

SHOT_ALT = {f"Alt+{k}": v for k, v in lb.SHOT_KEYS.items()}  # Alt+T Toàn, Alt+U Trung, Alt+C Cận
CONTENT_ALT = {f"Alt+{k}": k for k in lb.CONTENT_KEYS}  # Alt+1…5 nội dung
FOCUS_OF = {"sharp": None, "soft": "out_net", "missed": "trat_net"}  # 3.0.0 Q / W / R → Media focus labels
SAMPLE_FOCUS = {"sharp": "net", "soft": "out_net", "missed": "trat_net"}
MEDIA_KEYS_TEXT = (
    "\n\nChỉ có ở Media sự kiện:\n"
    "Alt+T / Alt+U / Alt+C   cỡ cảnh Toàn / Trung / Cận\n"
    "Alt+1 … Alt+5   nội dung: Sân khấu, Booth / Gian hàng, Decor, Sản phẩm, Merch (bấm lại để bỏ)\n"
    "Q / W / R   nét / Out nét / Trật nét (Q bỏ cảnh báo nét)\n"
    "Chuột phải trên ảnh   cỡ cảnh, nội dung, khoảnh khắc (tách / chuyển), tên booth\n\n" + SAMPLE_HELP)


class MediaUndo(EventUndo):
    """EventUndo with the interface MainWindow's Ctrl+Z, P / X and stars use (app.undo.manager.UndoManager)."""

    restored_subject_entries = 0

    def push_decisions(self, label: str, before: dict) -> None:
        self._stack.append(("decision", (label, before)))
        self._trim()

    def clear_subject_history(self, conn) -> None:  # noqa: ANN001 - no subject history in an event
        pass

    def subject_action(self, label: str, fn) -> bool:  # noqa: ANN001
        with self.event.transaction() as conn:
            fn(conn)
        return True


class EventWindow(MainWindow):
    def __init__(self, event: MediaEvent, settings: QSettings | None = None, *, analysis_runner=None) -> None:  # noqa: ANN001
        self.media_event = event
        self._analysis_runner = analysis_runner
        self.sampling = False
        super().__init__(settings)
        self._adapt_to_media()
        self._set_project(event, event.folder)
        self.enable_mode_switch()

    # ------------------------------------------------------------------ construction
    def _make_model(self) -> MediaAssetModel:
        return MediaAssetModel(self)

    def _adapt_to_media(self) -> None:
        # Top bar: same steps; 🧠 runs the event analysis; quality / pick do not exist in Media Mốc 1
        self.top_bar.step_labels["people"] = ("🧠", "Phân tích sự kiện")
        self.act_analyze.setText("🧠 Phân tích sự kiện")
        self.act_analyze.setToolTip("Cỡ cảnh, cảnh báo nét, khoảnh khắc (nhãn AI là thử nghiệm). Tạm dừng / chạy tiếp được.")
        for key in ("quality", "pick"):
            self.top_bar.buttons[key].setVisible(False)
        # 📋 Khách chọn (Ctrl+L) stays: a client's list works on an event as on a folder (REG-1)
        for act in (self.act_quality, self.act_select, self.act_merge, self.act_learning, self.act_taste_weight,
                    self.act_reset):
            act.setVisible(False)
        self.act_switch_mode.setText("⟵ Danh sách sự kiện / Đổi chế độ…")
        # Sidebar: P/X filters and folders as 3.0.0; people → event, cameras, event filters, moments
        self.sections["people"].setVisible(False)
        self.sort.setVisible(False)  # time order (corrected per camera); score sorts need the personal models
        layout: QVBoxLayout = self.sidebar.layout()  # type: ignore[assignment]
        self.sections["event"] = CollapsibleSection("SỰ KIỆN", self._event_box(), "media_event", self.settings)
        self.sections["media_filters"] = CollapsibleSection("LỌC SỰ KIỆN", self._filter_box(), "media_filters",
                                                            self.settings)
        self.sections["moments"] = CollapsibleSection("KHOẢNH KHẮC", self._moment_list(), "media_moments",
                                                      self.settings, extra=self._moment_tools())
        layout.insertWidget(0, self.sections["event"])
        layout.insertWidget(layout.indexOf(self.sections["filters"]) + 1, self.sections["media_filters"])
        layout.addWidget(self.sections["moments"], 1)
        # Cards: shot size, focus warnings, ⏳ and ⚠ lệch giờ instead of the score badge
        self.grid.setItemDelegate(MediaDelegate(self.grid.itemDelegate().cell, self.grid))  # type: ignore[attr-defined]
        # Detail panel: the personal "Phân tích AI" tab has no data here; a Media block takes its place
        self.media_info = QLabel()
        self.media_info.setWordWrap(True)
        self.media_info.setTextFormat(Qt.TextFormat.RichText)
        self.detail.layout().insertWidget(0, self.media_info)
        tabs = self.detail.tabs
        for name in ("Phân tích AI", "Chủ thể"):  # by position: a narrow panel shortens the titles; people: not Mốc 1
            tabs.setTabVisible(TABS.index(name), False)
        self._media_shortcuts()

    def _event_box(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        self.event_name = QLabel()
        self.event_name.setWordWrap(True)
        self.clock_button = QPushButton("🕒 Máy ảnh && giờ")  # && shows one & (a single & marks a shortcut key)
        self.clock_button.clicked.connect(self.open_clock)
        self.sample_button = QPushButton("🏷 Dán nhãn mẫu")
        self.sample_button.setCheckable(True)
        self.sample_button.setToolTip(SAMPLE_HELP)
        self.sample_button.toggled.connect(self._sample_mode)
        self.events_button = QPushButton("⟵ Danh sách sự kiện")
        self.events_button.clicked.connect(lambda: self.request_mode_change())
        for w in (self.event_name, self.clock_button, self.sample_button, self.events_button):
            v.addWidget(w)
        return box

    def _filter_box(self) -> QWidget:
        def combo(items: list[tuple[str, object]]) -> QComboBox:
            c = QComboBox()
            for text, data in items:
                c.addItem(text, data)
            c.currentIndexChanged.connect(self._apply_media_filter)
            return c

        self.shot_filter = combo([("Cỡ cảnh: tất cả", None), *((v, k) for k, v in lb.SHOT.items()),
                                  ("Chưa xác định", lb.UNKNOWN)])
        self.content_filter = combo([("Nội dung: tất cả", None), *((v, k) for k, v in lb.CONTENT.items()),
                                     ("Chưa gán nội dung", "none")])
        self.focus_filter = combo([("Lỗi nét: tất cả", None), *((v, k) for k, v in lb.FOCUS.items()),
                                   ("Không cảnh báo", "none"), ("Không đo được", lb.UNKNOWN)])
        self.state_filter = combo([("Nhãn: tất cả", None), ("⏳ Đang phân tích", "waiting"),
                                   (f"AI gợi ý {lb.EXPERIMENTAL}", "suggested"), ("Đã xác nhận", "confirmed")])
        self.camera_filter = QComboBox()
        self.camera_filter.currentIndexChanged.connect(self._apply_media_filter)
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        for w in (self.shot_filter, self.content_filter, self.focus_filter, self.camera_filter, self.state_filter):
            v.addWidget(w)
        return box

    def _moment_list(self) -> QListWidget:
        self.moment_list = QListWidget()
        self.moment_list.setWordWrap(True)
        self.moment_list.currentRowChanged.connect(lambda _r: self._apply_media_filter())
        return self.moment_list

    def _moment_tools(self) -> QWidget:
        box = QWidget()
        g = QGridLayout(box)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(2)
        # words, not bare symbols: some Windows fonts draw ⚠ / ⊕ as boxes or triangles
        for i, (text, tip, fn) in enumerate((
                ("✂ Tách", "Tách tại đây (ảnh đang chọn bắt đầu khoảnh khắc mới)", self.split_here),
                ("Gộp", "Gộp với khoảnh khắc trước", self.merge_with_previous),
                ("Đổi tên", "Đổi tên khoảnh khắc", lambda: self.rename_moment()),
                ("Lệch giờ: Chuyển", "Chuyển ảnh lệch giờ sang khoảnh khắc gợi ý", lambda: self._warning_action(True)),
                ("Lệch giờ: Giữ", "Giữ ảnh lệch giờ ở khoảnh khắc hiện tại", lambda: self._warning_action(False)))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            if i < 3:
                g.addWidget(b, 0, i * 2, 1, 2)
            else:
                g.addWidget(b, 1, (i - 3) * 3, 1, 3)
        return box

    def _media_shortcuts(self) -> None:
        def sc(key: str, fn) -> None:  # noqa: ANN001
            QShortcut(QKeySequence(key), self, lambda: None if typing_in(QApplication.focusWidget()) else fn(),
                      context=Qt.ShortcutContext.WindowShortcut)

        for key, value in SHOT_ALT.items():
            sc(key, lambda v=value: self._sample("shot", v) if self.sampling else self.set_shot(v))
        for key, digit in CONTENT_ALT.items():
            sc(key, lambda k=digit: self._sample("content", lb.CONTENT_KEYS[k]) if self.sampling
               else self.toggle_content(k))
        sc("B", lambda: self.sampling and self._sample("boundary", "start"))
        sc("Alt+0", lambda: self.sampling and self._sample("skip", "1"))

    # ------------------------------------------------------------------ session / import
    def _set_project(self, project, photo_root: Path) -> None:  # noqa: ANN001
        super()._set_project(project, photo_root)
        self.undo = MediaUndo(project)
        self._update_undo_action()
        self.setWindowTitle(f"{self.media_event.event_name} — Media sự kiện — {APP_NAME}")
        self.event_name.setText(f"<b>{self.media_event.event_name}</b>")
        self._refresh_media_sidebar()

    def _open_session_for(self, root: Path) -> bool:
        """An event takes photos from several folders: the event stays open and the folder is added to it."""
        return self.project is not None

    def _on_import_done(self, summary: dict) -> None:
        super()._on_import_done(summary)
        if self.project is not None:
            cam.refresh_sources(self.project)
            self._refresh_media_sidebar()
            if len(cam.cameras(self.project.conn)) >= 2:
                self.status.setText(self.status.text() + "  Nhiều máy ảnh: bấm 🕒 Máy ảnh & giờ để chỉnh giờ.")

    def reload_preserving_view(self) -> None:
        super().reload_preserving_view()
        self.model.refresh_info()

    def mode_change_text(self) -> str:
        text = ("P / X, sao, ❤, nhãn, khoảnh khắc và giờ đã chỉnh đều đã được lưu trong sự kiện.\n"
                "Ctrl+Z vẫn hoàn tác được thao tác Media (nhãn, khoảnh khắc, giờ) khi mở lại; P / X / sao thì không.")
        if self.analyze_thread is not None:
            text += "\n\nPhân tích đang chạy sẽ dừng; lần sau bấm 🧠 để chạy tiếp từ chỗ dừng."
        return text

    def _ask_leave_mode(self) -> bool:
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(QMessageBox.Icon.Question, "Rời sự kiện", "Về danh sách sự kiện?", parent=self)
        box.setInformativeText(self.mode_change_text())
        stay = box.addButton("Ở lại", QMessageBox.ButtonRole.RejectRole)
        leave = box.addButton("Về danh sách", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(stay)
        box.setEscapeButton(stay)
        box.exec()
        return box.clickedButton() is leave

    # ------------------------------------------------------------------ steps
    def _update_steps(self) -> None:
        busy = self.import_thread is not None or self.analyze_thread is not None
        photos = self.model.rowCount() if self.project is not None else 0
        self.act_analyze.setEnabled(not busy and photos > 0)
        self.refresh_steps()

    def refresh_steps(self) -> None:
        if self.project is None:
            return super().refresh_steps()
        states = steps(self.project.conn, importing=self._import_progress)
        p = analysis.progress_of(self.project.conn)
        if not p["total"] or p["waiting"] == p["total"]:
            states["people"] = StepState(False, None)
        elif p["waiting"]:
            states["people"] = StepState(False, f"{p['done'] + p['failed']}/{p['total']}")
        else:
            states["people"] = StepState(True, None)
        self.top_bar.set_states(states)

    # ------------------------------------------------------------------ analysis (🧠)
    def start_analysis(self, mode: str = "people"):  # noqa: ANN201
        if mode != "people" or self.project is None or self.import_thread is not None \
                or self.analyze_thread is not None or not self._gate.open:
            return None
        t = MediaAnalysisThread(self.media_event.folder, self.act_gpu.isChecked(), self._analysis_runner)
        t.progress.connect(self._analysis_progress)
        t.succeeded.connect(self._analysis_done)
        t.failed.connect(lambda msg: self._analysis_done(None, msg))
        self.analyze_thread = t
        self._paused_job = None
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.pause_button.setText("Tạm dừng")
        self.pause_button.setVisible(True)
        self.pause_button.setEnabled(True)
        self.status.setText("Đang phân tích sự kiện… vẫn duyệt ảnh được; nhãn hiện dần.")
        t.start()
        self._update_steps()
        return t

    def _analysis_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.status.setText(f"Đang phân tích sự kiện: {done}/{total} ảnh")
        if done % 20 == 0 or done == total:
            self.model.refresh_info()
            self.refresh_steps()

    def _analysis_done(self, summary: dict | None, error: str | None = None) -> None:
        t = self.analyze_thread
        if t is not None:
            t.wait()
        self.analyze_thread = None
        self.progress.setVisible(False)
        self.pause_button.setVisible(False)
        self.reload_preserving_view()
        self._refresh_media_sidebar()
        self._update_steps()
        if error:
            self.status.setText(f"Phân tích lỗi: {error}")
        elif summary is not None and summary.get("unavailable"):
            self.status.setText(summary["unavailable"])
        elif summary is not None:
            self.status.setText(
                f"Đã phân tích {summary['analysed']} ảnh" + (f", {summary['failed']} ảnh lỗi" if summary["failed"] else "")
                + (". Đã tạm dừng: bấm 🧠 để chạy tiếp." if summary["cancelled"] else f". {summary['moments']} khoảnh khắc.")
                + f" Nhãn AI là {lb.EXPERIMENTAL}.")

    # ------------------------------------------------------------------ export, undo, people menu
    def _learn_client_picks(self, collection_id: int) -> None:
        """A client's list in an event never teaches the personal taste (Media data stays in the event)."""

    def open_export_dialog(self, client_list: bool = False):  # noqa: ANN201
        from app.ui.media_export import MediaExportDialog

        marked = [r.id for r in self.selected_records()] if len(self.selected_records()) > 1 else []
        flt, target = self.model.current_filter, self.model.current_target
        collection = target if flt is Filter.COLLECTION else None
        dialog = MediaExportDialog(self.media_event, self, marked=marked, collection_id=collection)
        dialog.show()
        return dialog

    def _after_people_change(self) -> None:
        """Called by Ctrl+Z for a Media action (labels, moments, clock): repaint everything Media shows."""
        self.reload_preserving_view()
        self._refresh_media_sidebar()
        self._show_inspector(self.view_record())

    def undo_last(self) -> None:
        notice = self.undo.notice() if isinstance(self.undo, MediaUndo) else None
        super().undo_last()
        if notice:
            self.status.setText(self.status.text() + "  " + notice)

    def _people_menu_at(self, global_pos: object, assets: list[int]) -> None:
        """Right-click on photos: Media labels and moments (people & roles are Mốc 2)."""
        if self.project is None or not assets:
            return
        menu = QMenu(self)
        shot = menu.addMenu("Cỡ cảnh")
        for key, name in lb.SHOT.items():
            shot.addAction(f"{name}  (Alt+{next(k for k, v in lb.SHOT_KEYS.items() if v == key)})",
                           lambda v=key: self.set_shot(v, assets))
        content = menu.addMenu("Nội dung")
        for digit, key in lb.CONTENT_KEYS.items():
            content.addAction(f"{lb.CONTENT[key]}  (Alt+{digit})", lambda d=digit: self.toggle_content(d, assets))
        menu.addAction("Tên booth / nhà tài trợ…", lambda: self.assign_booth(assets))
        menu.addSeparator()
        menu.addAction("✂ Tách tại đây (bắt đầu khoảnh khắc mới)", self.split_here)
        move = menu.addMenu("Chuyển sang khoảnh khắc")
        for m in moments.moments(self.project.conn):
            move.addAction(m.name, lambda mid=m.id: self._move_to_moment(assets, mid))
        self._run_menu(menu, global_pos)

    # ------------------------------------------------------------------ Media labels
    def _ids(self, assets: list[int] | None = None) -> list[int]:
        return assets if assets is not None else [r.id for r in self._action_records()]

    def _media_action(self, fn, *args, text: str = "") -> None:  # noqa: ANN001
        self.undo.media(fn, *args)
        self._update_undo_action()
        self.model.refresh_info()
        self._refresh_media_sidebar()
        self._show_inspector(self.view_record())
        if text:
            self.status.setText(text)

    def set_shot(self, value: str, assets: list[int] | None = None) -> None:
        ids = self._ids(assets)
        if ids:
            self._media_action(lb.confirm, ids, "shot", value, text=f"Đã gán {lb.SHOT[value]} cho {len(ids)} ảnh.")

    def toggle_content(self, digit: str, assets: list[int] | None = None) -> None:
        ids = self._ids(assets)
        if ids:
            self._media_action(lb.toggle_content, ids, digit,
                               text=f"{lb.CONTENT[lb.CONTENT_KEYS[digit]]}: {len(ids)} ảnh.")

    def set_focus_label(self, label: str) -> None:
        """Q / W / R as in 3.0.0 (nét / soft / lệch nét) → the Media focus labels; in sample mode, the answers."""
        if self.sampling:
            self._sample("focus", SAMPLE_FOCUS[label])
            return
        ids = self._ids()
        if not ids or self.project is None:
            return
        value = FOCUS_OF[label]
        if value is None:
            shown = sorted({v for a in ids for v, st, _ in lb.labels_of(self.project.conn, a).get("focus", [])
                            if v != lb.UNKNOWN})
            for v in shown:
                self.undo.media(lb.remove, ids, "focus", v)
            self._media_action(lambda _e: None, text=("Đã đánh dấu nét (bỏ cảnh báo nét)" if shown
                                                      else "Ảnh không có cảnh báo nét") + f": {len(ids)} ảnh.")
        else:
            self._media_action(lb.confirm, ids, "focus", value, text=f"Đã gán {lb.FOCUS[value]}: {len(ids)} ảnh.")

    def assign_booth(self, assets: list[int]) -> None:
        name, ok = QInputDialog.getText(self, "Tên booth / nhà tài trợ", "Tên:")
        if ok and name.strip():
            self._media_action(lb.assign_booth, assets, name.strip(), text=f"Booth “{name.strip()}”: {len(assets)} ảnh.")

    # ------------------------------------------------------------------ moments
    def split_here(self) -> None:
        rec = self.current_record()
        if rec is None:
            return
        try:
            self._media_action(moments.split_here, rec.id, text="Đã tách khoảnh khắc (📌).")
        except ValueError as exc:
            self.status.setText(str(exc))

    def merge_with_previous(self) -> None:
        rec = self.current_record()
        if rec is None or self.project is None:
            return
        m = moments.moment_of(self.project.conn, rec.id)
        ms = [x.id for x in moments.moments(self.project.conn)]
        if m is None or ms.index(m) == 0:
            self.status.setText("Không có khoảnh khắc trước để gộp.")
            return
        self._media_action(moments.merge, ms[ms.index(m) - 1], m, text="Đã gộp với khoảnh khắc trước (📌).")

    def rename_moment(self, name: str | None = None) -> None:
        rec = self.current_record()
        m = moments.moment_of(self.project.conn, rec.id) if rec is not None and self.project is not None else None
        if m is None:
            return
        if name is None:
            name, ok = QInputDialog.getText(self, "Đổi tên khoảnh khắc", "Tên mới:")
            if not ok:
                return
        if name.strip():
            self._media_action(moments.rename, m, name.strip(), text="Đã đổi tên khoảnh khắc (📌).")

    def _move_to_moment(self, assets: list[int], moment_id: int) -> None:
        self._media_action(moments.move_photos, assets, moment_id, text=f"Đã chuyển {len(assets)} ảnh (📌).")

    def _warning_action(self, move: bool) -> None:
        if self.project is None:
            return
        warned = [a for a in self._ids() if a in moments.warnings(self.project.conn)]
        if not warned:
            self.status.setText("Chọn ảnh có ⚠ lệch giờ trước.")
            return
        for a in warned:
            self.undo.media(moments.accept_warning if move else moments.keep_warning, a)
        self._media_action(lambda _e: None, text=("Đã chuyển " if move else "Đã giữ ") + f"{len(warned)} ảnh.")

    def open_clock(self) -> None:
        if self.project is None:
            return
        dialog = ClockDialog(self.media_event, [r.id for r in self._action_records()], self)
        if dialog.exec():
            self.apply_clock(dialog.changes())

    def apply_clock(self, changes: dict[int, float]) -> None:
        for camera_id, seconds in changes.items():
            self.undo.media(moments.set_clock, camera_id, seconds)
        if changes:
            n = len(moments.warnings(self.project.conn))
            self._media_action(lambda _e: None, text="Đã chỉnh giờ." + (f" {n} ảnh ⚠ lệch giờ cần xem." if n else ""))

    # ------------------------------------------------------------------ sidebar, filters, details
    def _refresh_media_sidebar(self) -> None:
        if self.project is None:
            return
        conn = self.project.conn
        keep = self.camera_filter.currentData()
        self.camera_filter.blockSignals(True)
        self.camera_filter.clear()
        self.camera_filter.addItem("Nguồn máy: tất cả", None)
        for c in cam.cameras(conn):
            self.camera_filter.addItem(f"{c['display_name']} ({c['photos']})", c["id"])
        self.camera_filter.setCurrentIndex(max(0, self.camera_filter.findData(keep)))
        self.camera_filter.blockSignals(False)
        self.clock_button.setEnabled(len(cam.cameras(conn)) >= 2)
        current = self.moment_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.moment_list.currentItem() else None
        warnings = moments.warnings(conn)
        self.moment_list.blockSignals(True)
        self.moment_list.clear()
        all_item = QListWidgetItem("Tất cả khoảnh khắc")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.moment_list.addItem(all_item)
        for m in moments.moments(conn):
            warn = sum(1 for a in m.assets if a in warnings)
            cover = " ".join(f"{lb.SHOT[k]}{'✓' if ok else '✗'}" for k, ok in lb.shot_coverage(conn, m.id).items())
            item = QListWidgetItem(f"{'📌 ' if m.pinned else ''}{m.name} · {len(m.assets)} ảnh"
                                   + (f" · ⚠{warn}" if warn else "") + f"\n{cover}")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self.moment_list.addItem(item)
        row = next((i for i in range(self.moment_list.count())
                    if self.moment_list.item(i).data(Qt.ItemDataRole.UserRole) == current), 0)
        self.moment_list.setCurrentRow(row)
        self.moment_list.blockSignals(False)

    def media_filter(self) -> MediaFilter:
        item = self.moment_list.currentItem()
        return MediaFilter(shot=self.shot_filter.currentData(), content=self.content_filter.currentData(),
                           focus=self.focus_filter.currentData(), camera_id=self.camera_filter.currentData(),
                           moment_id=item.data(Qt.ItemDataRole.UserRole) if item is not None else None,
                           state=self.state_filter.currentData())

    def _apply_media_filter(self) -> None:
        if not hasattr(self, "moment_list"):
            return
        self.model.set_media_filter(self.media_filter())
        if self.model.rowCount():
            self.select_row(0)
        self._update_empty_state()

    def _show_inspector(self, rec: AssetRecord | None) -> None:
        super()._show_inspector(rec)
        if hasattr(self, "media_info"):
            self.media_info.setText(self._media_text(rec))

    def _media_text(self, rec: AssetRecord | None) -> str:
        if rec is None or self.project is None:
            return ""
        conn, a = self.project.conn, rec.id
        names = {c["id"]: c["display_name"] for c in cam.cameras(conn)}
        lines = [f"Nguồn: {names.get(cam.camera_of(conn, a), cam.UNKNOWN_CAMERA)}"]
        m = moments.moment_of(conn, a)
        mname = next((x.name for x in moments.moments(conn) if x.id == m), None)
        if mname:
            lines.append(f"Khoảnh khắc: {mname}")
        info = self.model.info.get(a)
        if info is not None and info.waiting:
            lines.append("⏳ Chưa phân tích")
        for grp, title in (("shot", "Cỡ cảnh"), ("content", "Nội dung"), ("focus", "Cảnh báo nét")):
            texts = []
            for value, state, _ in lb.labels_of(conn, a).get(grp, []):
                name = ("không đo được" if grp == "focus" else "Chưa xác định") if value == lb.UNKNOWN \
                    else lb.GROUPS[grp][value]
                texts.append(name + (f" {lb.EXPERIMENTAL}" if state == "suggested" else " ✓" if state == "confirmed"
                                     else ""))
            lines.append(f"{title}: {', '.join(texts) if texts else '—'}")
        booth = lb.booth_of(conn, a)
        if booth:
            lines.append(f"Booth: {booth[0]}" + (" (gợi ý)" if booth[1] == "suggested" else ""))
        if moments.warnings(conn).get(a) is not None:
            lines.append("⚠ lệch giờ: có thể thuộc khoảnh khắc khác (KHOẢNH KHẮC → Lệch giờ: Chuyển / Giữ)")
        if self.sampling:
            from app.media import samples as sm

            lines.append("<b>" + sm.sample_text(conn, a) + "</b>")
        return "<br>".join(lines)

    # ------------------------------------------------------------------ sample labelling
    def _sample_mode(self, on: bool) -> None:
        self.sampling = on
        self.status.setText(SAMPLE_HELP if on else "Đã tắt Dán nhãn mẫu.")
        self._show_inspector(self.view_record())

    def _sample(self, grp: str, value: str) -> None:
        from app.media import samples as sm

        ids = self._ids()
        if not ids or self.project is None:
            return
        conn = self.project.conn
        if grp in ("shot", "focus"):
            if all(sm.samples_of(conn, a).get(grp) == [value] for a in ids):
                with conn:
                    conn.executemany("DELETE FROM sample_labels WHERE asset_id = ? AND grp = ?",
                                     [(a, grp) for a in ids])
            else:
                sm.set_sample(conn, ids, grp, value)
        else:
            sm.toggle_sample(conn, ids, grp, value)
        self._show_inspector(self.view_record())
        n = conn.execute("SELECT COUNT(DISTINCT asset_id) FROM sample_labels").fetchone()[0]
        self.status.setText(f"Nhãn mẫu: {n} ảnh đã dán. " + SAMPLE_HELP)

    def show_shortcuts(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Phím tắt — Media sự kiện",
                                "Giống Chụp cá nhân 3.0.0 (⌨ Phím tắt ở cửa sổ Chụp cá nhân), cộng thêm:"
                                + MEDIA_KEYS_TEXT)


__all__ = ["EventWindow", "MediaUndo", "QAction"]
