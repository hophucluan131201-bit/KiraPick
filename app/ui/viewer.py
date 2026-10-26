"""Large preview ("loupe") with fit-to-window and 100% zoom.

Pixels are decoded off the UI thread. The 1600 px analysis preview is shown
first; pressing Z switches to true 100% using ``load_full_resolution`` (camera
full-size JPEG when available, otherwise a full RAW demosaic).
"""

from __future__ import annotations

from collections import OrderedDict
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget

from app.core.errors import ImageReadError
from app.ingest.preview import load_full_resolution, load_image
from app.ui import theme
from app.ui.qt_image import pil_to_qimage

PREVIEW_LONG_SIDE = 1600
_FULL_CACHE = 2  # full-resolution frames kept in memory (~70 MB each for 24 MP)


class Quality(str, Enum):
    PREVIEW = "preview"
    FULL = "full"


class _Signals(QObject):
    done = Signal(int, str, QImage, str, str)  # token, quality, image, source, error


class _LoadTask(QRunnable):
    def __init__(self, token: int, path: Path, quality: Quality, signals: _Signals) -> None:
        super().__init__()
        self.token, self.path, self.quality, self.signals = token, path, quality, signals

    def run(self) -> None:
        try:
            if self.quality is Quality.FULL:
                loaded = load_full_resolution(self.path)
            else:
                loaded = load_image(self.path, max_long_side=PREVIEW_LONG_SIDE, min_long_side=PREVIEW_LONG_SIDE)
            self.signals.done.emit(self.token, self.quality.value, pil_to_qimage(loaded.image), loaded.source.value, "")
        except ImageReadError as exc:
            self.signals.done.emit(self.token, self.quality.value, QImage(), "", f"{exc.reason}: {exc.detail}")
        except Exception as exc:  # noqa: BLE001 - never crash the UI on a bad file
            self.signals.done.emit(self.token, self.quality.value, QImage(), "", f"internal_error: {type(exc).__name__}")


class ImageViewer(QGraphicsView):
    status_changed = Signal(str)  # human-readable description of what is shown

    def __init__(self, parent: QWidget | None = None) -> None:
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

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._signals = _Signals()
        self._signals.done.connect(self._on_loaded)
        self._token = 0
        self._path: Path | None = None
        self._quality = Quality.PREVIEW
        self._shown_full = False
        self._full_cache: OrderedDict[Path, tuple[QPixmap, str]] = OrderedDict()
        self._message = ""
        self.zoom_100 = False
        self.source_label = ""

    # ------------------------------------------------------------ public
    def show_photo(self, path: Path | None, placeholder: QPixmap | None = None) -> None:
        self._token += 1
        self._path = path
        self._message = ""
        self._shown_full = False
        if path is None:
            self._set_pixmap(QPixmap())
            return
        if placeholder is not None and not placeholder.isNull():
            self._set_pixmap(placeholder, keep_view=False)
        if self.zoom_100:
            self._request(Quality.FULL)
        else:
            self._request(Quality.PREVIEW)

    def toggle_zoom(self) -> None:
        self.zoom_100 = not self.zoom_100
        if self.zoom_100:
            if self._shown_full:
                self._apply_zoom()
            else:
                self._request(Quality.FULL)
                self.status_changed.emit("Đang tải ảnh độ phân giải đầy đủ…")
        else:
            self._fit()

    def is_full_resolution_shown(self) -> bool:
        return self._shown_full

    def pixmap_size(self) -> tuple[int, int]:
        pm = self._item.pixmap()
        return pm.width(), pm.height()

    def wait_idle(self, msecs: int = 30000) -> bool:
        return self._pool.waitForDone(msecs)

    # ----------------------------------------------------------- loading
    def _request(self, quality: Quality) -> None:
        if self._path is None:
            return
        if quality is Quality.FULL and self._path in self._full_cache:
            pm, source = self._full_cache[self._path]
            self._full_cache.move_to_end(self._path)
            self._show_full(pm, source)
            return
        self._pool.start(_LoadTask(self._token, self._path, quality, self._signals))

    def _on_loaded(self, token: int, quality: str, image: QImage, source: str, error: str) -> None:
        if token != self._token:
            return  # user already moved to another photo
        if error:
            if quality == Quality.FULL.value:
                self.zoom_100 = False
                self.status_changed.emit(f"Không zoom 100% được: {error}")
            else:
                self._message = error
                self.status_changed.emit(f"Không đọc được ảnh: {error}")
                self.viewport().update()
            return
        pm = QPixmap.fromImage(image)
        if quality == Quality.FULL.value:
            assert self._path is not None
            self._full_cache[self._path] = (pm, source)
            while len(self._full_cache) > _FULL_CACHE:
                self._full_cache.popitem(last=False)
            self._show_full(pm, source)
        elif not self._shown_full:
            self.source_label = source
            self._set_pixmap(pm, keep_view=False)
            self.status_changed.emit(f"Xem trước {pm.width()}×{pm.height()} ({_source_vi(source)})")

    def _show_full(self, pm: QPixmap, source: str) -> None:
        self._shown_full = True
        self.source_label = source
        self._set_pixmap(pm, keep_view=True)
        if self.zoom_100:
            self._apply_zoom()
        self.status_changed.emit(f"100%: {pm.width()}×{pm.height()} ({_source_vi(source)})")

    # ------------------------------------------------------------- view
    def _set_pixmap(self, pm: QPixmap, *, keep_view: bool = False) -> None:
        center = self.mapToScene(self.viewport().rect().center())
        old = self._item.pixmap()
        rel = QPointF(center.x() / old.width(), center.y() / old.height()) if keep_view and not old.isNull() else None
        self._item.setPixmap(pm)
        self.scene().setSceneRect(QRectF(pm.rect()))
        if self.zoom_100 and self._shown_full:
            self._apply_zoom(rel)
        else:
            self._fit()

    def _fit(self) -> None:
        self.resetTransform()
        if not self._item.pixmap().isNull():
            self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)

    def _apply_zoom(self, rel: QPointF | None = None) -> None:
        self.resetTransform()
        ratio = self.devicePixelRatioF() or 1.0
        self.scale(1 / ratio, 1 / ratio)  # one image pixel per physical screen pixel
        pm = self._item.pixmap()
        if rel is not None:
            self.centerOn(rel.x() * pm.width(), rel.y() * pm.height())
        else:
            self.centerOn(pm.width() / 2, pm.height() / 2)

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)  # type: ignore[arg-type]
        if not self.zoom_100:
            self._fit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802 - Qt override
        if self._message:
            painter.save()
            painter.resetTransform()
            painter.setPen(QColor(theme.ERROR))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Không đọc được ảnh này\n" + self._message)
            painter.restore()


def _source_vi(source: str) -> str:
    return {
        "embedded_jpeg": "ảnh nhúng trong RAW",
        "embedded_bitmap": "ảnh nhúng trong RAW",
        "demosaic_half": "giải mã RAW ½",
        "demosaic_full": "giải mã RAW đầy đủ",
        "raster": "file ảnh",
    }.get(source, source)
