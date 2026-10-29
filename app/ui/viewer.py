"""Large preview ("loupe"): fit-to-window, true 100% and closer (up to 800%).

Pixels are decoded off the UI thread. The 1600 px analysis preview is shown
first; any zoom beyond "fit" loads the full-resolution image with
``load_full_resolution`` (camera full-size JPEG when available, otherwise a full
RAW demosaic), so sharpness is judged on real pixels, never on an enlarged preview.
Zoom levels are relative to the full-resolution image: 1.0 = one photo pixel per
physical screen pixel.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QToolButton, QWidget

from app.storage.view import rotate_point
from app.ui.asset_model import turned
from app.core.errors import ImageReadError
from app.ingest.preview import load_full_resolution, load_image
from app.ui import theme
from app.ui.shutdown import Gate
from app.ui.qt_image import pil_to_qimage_rgb32

PREVIEW_LONG_SIDE = 1600
_FULL_CACHE = 2  # full-resolution frames kept in memory (~70 MB each for 24 MP)
MAX_ZOOM = 8.0
ZOOM_STEPS = (1.0, 2.0, 4.0, 8.0)


class Quality(str, Enum):
    PREVIEW = "preview"
    FULL = "full"


class _Signals(QObject):
    done = Signal(int, int, str, QImage, int, str, str)  # token, full request id, quality, image, turns, source, error


class _LoadTask(QRunnable):
    def __init__(self, token: int, path: Path, quality: Quality, signals: _Signals, request: int = 0,
                 turns: int = 0) -> None:
        super().__init__()
        self.token, self.path, self.quality, self.signals, self.request = token, path, quality, signals, request
        self.turns = turns % 4


    def run(self) -> None:
        try:
            if self.quality is Quality.FULL:
                loaded = load_full_resolution(self.path)
            else:
                loaded = load_image(self.path, max_long_side=PREVIEW_LONG_SIDE, min_long_side=PREVIEW_LONG_SIDE)
            # Made ready to show here (32-bit, turned by the Xoay xem asked for): ~0.5 s of GUI-thread work at 24 MP
            image = pil_to_qimage_rgb32(loaded.image, self.turns)
            self.signals.done.emit(self.token, self.request, self.quality.value, image, self.turns, loaded.source.value, "")
        except ImageReadError as exc:
            self.signals.done.emit(self.token, self.request, self.quality.value, QImage(), 0, "", f"{exc.reason}: {exc.detail}")
        except Exception as exc:  # noqa: BLE001 - never crash the UI on a bad file
            self.signals.done.emit(self.token, self.request, self.quality.value, QImage(), 0, "", f"internal_error: {type(exc).__name__}")


class ImageViewer(QGraphicsView):
    status_changed = Signal(str)  # human-readable description of what is shown
    back_requested = Signal()  # the "back to grid" button was pressed
    full_frame_loaded = Signal(object)  # (width, height) of the full-resolution image now held (Compare's budget)
    full_load_failed = Signal()  # the full-resolution load of the photo shown failed

    def __init__(self, parent: QWidget | None = None, *, pool: QThreadPool | None = None,
                 full_pool: QThreadPool | None = None, full_cache: int = _FULL_CACHE) -> None:
        """``pool`` / ``full_pool``: decode pools shared with other viewers (Compare), used and never owned;
        full-resolution loads go to ``full_pool`` (default: ``pool``). Without them the viewer owns one 2-thread pool."""
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().addItem(self._item)
        self.setBackgroundBrush(QColor(theme.BG))
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keys go to the window shortcuts
        self.back_button = QToolButton(self)
        self.back_button.setObjectName("backToGrid")
        self.back_button.setText("◀  Về lưới ảnh  (Esc)")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.move(12, 12)
        self.back_button.clicked.connect(self.back_requested.emit)

        if pool is None:
            pool = QThreadPool(self)
            pool.setMaxThreadCount(2)
        self._pool = pool
        self._full_pool = full_pool or pool
        self._full_cache_size = max(1, full_cache)
        # Asked before a full-resolution decode is queued (Compare's memory budget); False = stay on the preview.
        self.full_allowed: Callable[[], bool] | None = None
        self._full_request = 0  # id of the full decode queued / running for the photo shown (0 = none)
        self._requests = 0
        self.gate = Gate()  # the window shares its own: closed while a session is being released
        self._signals = _Signals(self)  # destroyed by the viewer, on the GUI thread (app.ui.shutdown)
        self._signals.done.connect(self._on_loaded)
        self._token = 0
        self._rotation = 0  # Xoay xem of the photo shown (quarter turns clockwise)
        self._focus: QPointF | None = None  # point asked for by set_zoom (0..1), kept until the full image is shown
        self._path: Path | None = None
        self._quality = Quality.PREVIEW
        self._shown_full = False
        self._full_cache: OrderedDict[Path, tuple[QPixmap, str, int]] = OrderedDict()  # pixmap, source, its turns
        self._message = ""
        self.zoom: float | None = None  # None = fit to window
        self._full_long: int | None = None  # long side of the full-resolution image, when known
        self.source_label = ""

    # ------------------------------------------------------------ public
    @property
    def zoom_100(self) -> bool:
        """Zoomed in (100% or closer) rather than fitted to the window."""
        return self.zoom is not None

    def show_photo(self, path: Path | None, placeholder: QPixmap | None = None,
                   full_long_side: int | None = None, rotation: int = 0) -> None:
        """``placeholder`` is already turned (the grid's thumbnail); loaded images are turned by ``rotation``
        quarter turns clockwise here (Xoay xem: display only)."""
        self._token += 1
        self._full_request = 0
        self._rotation = rotation % 4
        self._base: QPixmap | None = None  # the loaded image, turned by _base_turns (done by the worker)
        self._base_turns = 0
        self._focus = None  # a new photo: no requested point yet
        self._path = path
        self._message = ""
        self._shown_full = False
        self._full_long = full_long_side
        if path is None:  # nothing shown (Compare closed, session closed): full frames are given back too
            self._full_cache.clear()
            self._shown_full = False
            self._set_pixmap(QPixmap())
            return
        if placeholder is not None and not placeholder.isNull():
            self._set_pixmap(placeholder, keep_view=False)
        if self.zoom_100:
            self._request(Quality.FULL)
        else:
            self._request(Quality.PREVIEW)

    def set_rotation(self, turns: int) -> bool:
        """Xoay xem on the photo shown: the image already loaded is turned in place (no reload) and, when zoomed,
        the same photo point stays in the middle of the window. False when nothing is loaded yet (the caller then
        shows the photo again)."""
        turns %= 4
        if self._path is None or getattr(self, "_base", None) is None:
            return False
        delta = (turns - self._rotation) % 4
        if delta == 0:
            return True
        pm = self._item.pixmap()
        centre = self.mapToScene(self.viewport().rect().center())
        rel = QPointF(centre.x() / pm.width(), centre.y() / pm.height()) if not pm.isNull() else QPointF(0.5, 0.5)
        x, y = rotate_point(min(max(rel.x(), 0.0), 1.0), min(max(rel.y(), 0.0), 1.0), delta)
        self._rotation = turns
        # Zoomed: the same photo point goes back to the middle (on a preview it also waits for the full image).
        self._focus = QPointF(x, y) if self.zoom is not None else None
        self._set_pixmap(self._shown_base(), keep_view=False)
        return True

    def _shown_base(self) -> QPixmap:
        """The loaded image turned to the current Xoay xem (no work when the worker already turned it)."""
        assert self._base is not None
        return turned(self._base, self._rotation - self._base_turns)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        self._focus = None  # the user takes over: a pending E point never pulls the view back afterwards
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def toggle_zoom(self) -> None:
        """Z: fit <-> 100%."""
        self.set_zoom(None if self.zoom is not None else 1.0)

    def zoom_in(self) -> None:
        current = self.zoom or 0.0
        self.set_zoom(next((z for z in ZOOM_STEPS if z > current + 1e-6), MAX_ZOOM))

    def zoom_out(self) -> None:
        current = self.zoom
        if current is None:
            return
        smaller = [z for z in ZOOM_STEPS if z < current - 1e-6]
        self.set_zoom(smaller[-1] if smaller else None)

    def set_zoom(self, level: float | None, focus: QPointF | None = None) -> None:
        """level relative to full resolution (None = fit); focus = point to centre, 0..1 of the photo."""
        self.zoom = None if level is None else max(0.05, min(MAX_ZOOM, level))
        self._focus = focus if self.zoom is not None else None
        if self.zoom is None:
            self._fit()
            self._emit_zoom()
            return
        if not self._shown_full:
            self._request(Quality.FULL)
            self.status_changed.emit("Đang tải ảnh độ phân giải đầy đủ…")
        self._apply_zoom(focus)
        self._emit_zoom()

    def zoom_percent(self) -> int | None:
        return None if self.zoom is None else round(self.zoom * 100)

    def is_full_resolution_shown(self) -> bool:
        return self._shown_full

    def pixmap_size(self) -> tuple[int, int]:
        pm = self._item.pixmap()
        return pm.width(), pm.height()

    def drop_full(self, *, keep_zoom: bool = False) -> None:
        """Give the full-resolution frame back (Compare's budget): a preview-sized copy of it is shown, back to fit
        (or at the same zoom on that copy with ``keep_zoom``); a decode still running is not taken when it arrives."""
        self._full_request = 0
        self._full_cache.clear()
        if not keep_zoom:
            self.zoom = None
            self._focus = None
        base = getattr(self, "_base", None)
        if self._shown_full and base is not None and not base.isNull():
            self._base = base.scaled(PREVIEW_LONG_SIDE, PREVIEW_LONG_SIDE, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            self._shown_full = False
            self._set_pixmap(self._shown_base(), keep_view=keep_zoom)
        elif self.zoom is None:
            self._fit()
        self._emit_zoom()

    def wait_idle(self, msecs: int = 30000) -> bool:
        """Both pools idle within ONE deadline of ``msecs`` (not ``msecs`` per pool)."""
        return wait_pools([self._pool, self._full_pool], msecs)

    def stop_pending(self) -> None:
        """Drop loads not started yet (a running decode cannot be interrupted; it finishes). On shared pools this
        also drops the other viewers' queued loads (Compare stops all its tiles together)."""
        self._pool.clear()
        if self._full_pool is not self._pool:
            self._full_pool.clear()

    # ----------------------------------------------------------- loading
    def _request(self, quality: Quality) -> None:
        if self._path is None:
            return
        if quality is Quality.FULL and self._path in self._full_cache:
            pm, source, turns = self._full_cache[self._path]
            self._full_cache.move_to_end(self._path)
            self._show_full(pm, source, turns)
            self.full_frame_loaded.emit((pm.width(), pm.height()))
            return
        if quality is Quality.FULL:
            if self._full_request:
                return  # already queued or decoding: one decode per photo, however many zoom steps
            if not self.gate.open or (self.full_allowed is not None and not self.full_allowed()):
                return  # closing, or over Compare's memory budget: the preview stays (the tile says why)
            self._requests += 1
            self._full_request = self._requests
        if self.gate.open:
            pool = self._full_pool if quality is Quality.FULL else self._pool
            request = self._full_request if quality is Quality.FULL else 0
            pool.start(_LoadTask(self._token, self._path, quality, self._signals, request, self._rotation))

    def _on_loaded(self, token: int, request: int, quality: str, image: QImage, turns: int, source: str,
                   error: str) -> None:
        if token != self._token:
            return  # user already moved to another photo
        if quality == Quality.FULL.value:
            if request != self._full_request:
                return  # not the decode asked for now (dropped meanwhile, or an older request): not taken
            self._full_request = 0
        if error:
            if quality == Quality.FULL.value:
                self.full_load_failed.emit()
                self.status_changed.emit(f"Không tải được ảnh gốc để phóng to: {error} (đang phóng ảnh xem trước)")
            else:
                self._message = error
                self.status_changed.emit(f"Không đọc được ảnh: {error}")
                self.viewport().update()
            return
        pm = QPixmap.fromImage(image)  # already 32-bit and turned by ``turns`` (the worker did both)
        if quality == Quality.FULL.value:
            assert self._path is not None
            self._full_cache[self._path] = (pm, source, turns)
            while len(self._full_cache) > self._full_cache_size:
                self._full_cache.popitem(last=False)
            self._show_full(pm, source, turns)
            self.full_frame_loaded.emit((pm.width(), pm.height()))
        elif not self._shown_full:
            self._base, self._base_turns = pm, turns
            self.source_label = source
            self._set_pixmap(self._shown_base(), keep_view=False)
            self.status_changed.emit(f"Xem trước {pm.width()}×{pm.height()} ({_source_vi(source)})")

    def _show_full(self, pm: QPixmap, source: str, turns: int) -> None:
        self._base, self._base_turns = pm, turns
        self._shown_full = True
        self._full_long = max(pm.width(), pm.height())
        self.source_label = source
        self._set_pixmap(self._shown_base(), keep_view=True)
        self._emit_zoom()

    def _emit_zoom(self) -> None:
        pm = self._item.pixmap()
        if pm.isNull():
            return
        size = f"{pm.width()}×{pm.height()} ({_source_vi(self.source_label)})"
        if self.zoom is None:
            self.status_changed.emit(f"Vừa khung · {'ảnh gốc' if self._shown_full else 'xem trước'} {size}")
        else:
            real = "ảnh gốc" if self._shown_full else "xem trước, đang tải ảnh gốc…"
            self.status_changed.emit(f"Zoom {self.zoom_percent()}% · {real} {size} · cuộn chuột / + − để phóng")

    # ------------------------------------------------------------- view
    def _set_pixmap(self, pm: QPixmap, *, keep_view: bool = False) -> None:
        center = self.mapToScene(self.viewport().rect().center())
        old = self._item.pixmap()
        rel = QPointF(center.x() / old.width(), center.y() / old.height()) if keep_view and not old.isNull() else None
        if self._focus is not None:  # a point was asked for (e.g. E: the eyes) while a smaller image was shown
            rel = self._focus
            if self._shown_full:
                self._focus = None  # reached on the real pixels; from now on the user pans freely
        self._item.setPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        if self.zoom is not None:
            self._apply_zoom(rel)
        else:
            self._fit()

    def _fit(self) -> None:
        self.resetTransform()
        if not self._item.pixmap().isNull():
            self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)

    def _pixmap_scale(self) -> float:
        """Shown pixmap pixels per full-resolution pixel (1 once the full image is shown)."""
        pm = self._item.pixmap()
        if self._shown_full or not self._full_long or pm.isNull():
            return 1.0
        return max(pm.width(), pm.height()) / self._full_long

    def _apply_zoom(self, rel: QPointF | None = None) -> None:
        pm = self._item.pixmap()
        if pm.isNull() or self.zoom is None:
            return
        if rel is None:  # keep what is in the middle of the window
            centre = self.mapToScene(self.viewport().rect().center())
            rel = QPointF(centre.x() / pm.width(), centre.y() / pm.height())
        self.resetTransform()
        ratio = self.devicePixelRatioF() or 1.0
        k = self.zoom / ratio / self._pixmap_scale()  # zoom 1.0 = one photo pixel per physical screen pixel
        self.scale(k, k)
        self.centerOn(rel.x() * pm.width(), rel.y() * pm.height())

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)  # type: ignore[arg-type]
        if self.zoom is None:
            self._fit()

    def _fit_level(self) -> float:
        """Zoom level (relative to full resolution) at which the photo fits the window."""
        pm = self._item.pixmap()
        if pm.isNull():
            return 1.0
        ratio = self.devicePixelRatioF() or 1.0
        fit = min(self.viewport().width() / pm.width(), self.viewport().height() / pm.height())
        return fit * ratio * self._pixmap_scale()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override
        if self._item.pixmap().isNull():
            return
        current = self.zoom if self.zoom is not None else self._fit_level()
        target = current * (1.25 if event.angleDelta().y() > 0 else 0.8)
        if target <= self._fit_level():
            self.set_zoom(None)
            return
        point = self.mapToScene(event.position().toPoint())
        pm = self._item.pixmap()
        before = event.position()
        self.set_zoom(min(MAX_ZOOM, target), QPointF(point.x() / pm.width(), point.y() / pm.height()))
        # keep the photo point under the mouse where it was
        moved = self.mapFromScene(point)
        delta = moved - before.toPoint()
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())

    def mouseDoubleClickEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        """Double-click: 100% on that spot, or back to fit."""
        pm = self._item.pixmap()
        if pm.isNull():
            return
        point = self.mapToScene(event.position().toPoint())  # type: ignore[attr-defined]
        self.set_zoom(1.0 if self.zoom is None else None, QPointF(point.x() / pm.width(), point.y() / pm.height()))

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802 - Qt override
        if self._message:
            painter.save()
            painter.resetTransform()
            painter.setPen(QColor(theme.ERROR))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Không đọc được ảnh này\n" + self._message)
            painter.restore()


def wait_pools(pools: list[QThreadPool], msecs: int) -> bool:
    """Wait for these pools (each once) with one shared deadline; True when all are idle."""
    import time

    deadline = time.monotonic() + msecs / 1000
    done = True
    for pool in dict.fromkeys(pools):  # the same pool twice is waited once
        left = max(0, int((deadline - time.monotonic()) * 1000))
        done = pool.waitForDone(left) and done
    return done


def _source_vi(source: str) -> str:
    return {
        "embedded_jpeg": "ảnh nhúng trong RAW",
        "embedded_bitmap": "ảnh nhúng trong RAW",
        "demosaic_half": "giải mã RAW ½",
        "demosaic_full": "giải mã RAW đầy đủ",
        "raster": "file ảnh",
    }.get(source, source)
