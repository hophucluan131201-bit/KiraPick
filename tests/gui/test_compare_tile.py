"""Compare mode, part 2 task 2: a tile wraps one part 1 ImageViewer; the viewer can use shared pools; true 100 %
(one photo pixel per physical screen pixel) and the photo point are kept through async loads and Xoay xem."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, QThreadPool
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication

from app.storage.view import rotate_point
from app.ui.asset_model import AssetRecord
from app.ui.compare_view import CompareTile
from app.ui.viewer import ImageViewer, Quality
from tests.integration.test_import_job import _photo


class _RecordingPool(QThreadPool):
    def __init__(self) -> None:
        super().__init__()
        self.started: list[str] = []

    def start(self, task, priority: int = 0) -> None:  # noqa: ANN001 - Qt override from Python callers
        self.started.append(task.quality.value)
        super().start(task, priority)


def _record(path: Path, asset_id: int = 1, **kw) -> AssetRecord:  # noqa: ANN003
    fields = {"width": 3000, "height": 2000, **kw}
    return AssetRecord(id=asset_id, source_id=1, path=path, relative_path=path.name, extension=path.suffix,
                       status="ok", error=None, thumb_file=None, capture_time=None, camera=None, lens=None, **fields)


@pytest.fixture
def big(tmp_path: Path) -> Path:
    return _photo(tmp_path / "BIG_0001.jpg", 7, size=(3000, 2000))


def _tile(qtbot, rec: AssetRecord, **kw) -> CompareTile:  # noqa: ANN001, ANN003
    tile = CompareTile(**kw)
    qtbot.addWidget(tile)
    tile.resize(700, 500)
    tile.show()
    tile.show_record(rec, None)
    return tile


def _centre(viewer: ImageViewer) -> tuple[float, float]:
    c = viewer.mapToScene(viewer.viewport().rect().center())
    w, h = viewer.pixmap_size()
    return c.x() / w, c.y() / h


def _full(qtbot, viewer: ImageViewer) -> None:  # noqa: ANN001
    qtbot.waitUntil(viewer.is_full_resolution_shown, timeout=20000)
    QApplication.processEvents()


def test_viewer_uses_given_pools(qtbot, big: Path) -> None:  # noqa: ANN001
    p, f = _RecordingPool(), _RecordingPool()
    v = ImageViewer(pool=p, full_pool=f)
    qtbot.addWidget(v)
    v.resize(600, 400)
    v.show()
    v.show_photo(big)
    v.set_zoom(1.0)
    assert v.wait_idle(20000)
    assert p.started == [Quality.PREVIEW.value] and f.started == [Quality.FULL.value]
    assert v._pool is p and v._full_pool is f and p.parent() is None  # used, never owned
    own = ImageViewer()
    qtbot.addWidget(own)
    assert own._pool is own._full_pool and own._pool.maxThreadCount() == 2 and own._pool.parent() is own


@pytest.mark.parametrize("dpr", [1.0, 1.5, 2.0])
def test_true_100_percent_at_dpr(qtbot, big: Path, monkeypatch, dpr: float) -> None:  # noqa: ANN001
    tile = _tile(qtbot, _record(big))
    v = tile.viewer
    monkeypatch.setattr(v, "devicePixelRatioF", lambda: dpr)
    v.set_zoom(1.0)
    _full(qtbot, v)
    assert v.pixmap_size() == (3000, 2000)
    assert v.transform().m11() == pytest.approx(1 / dpr)  # one photo pixel per physical pixel


def test_preview_to_full_keeps_centre_point(qtbot, big: Path) -> None:  # noqa: ANN001
    tile = _tile(qtbot, _record(big))
    v = tile.viewer
    qtbot.waitUntil(lambda: v.pixmap_size()[0] > 0, timeout=20000)  # the preview
    v.set_zoom(1.0, QPointF(0.3, 0.6))
    assert not v.is_full_resolution_shown()
    assert _centre(v) == pytest.approx((0.3, 0.6), abs=0.01)
    _full(qtbot, v)
    assert _centre(v) == pytest.approx((0.3, 0.6), abs=0.01)


def test_rotation_while_zoomed_keeps_point(qtbot, big: Path) -> None:  # noqa: ANN001
    tile = _tile(qtbot, _record(big))
    v = tile.viewer
    v.set_zoom(2.0, QPointF(0.3, 0.6))
    _full(qtbot, v)
    assert v.set_rotation(1)
    assert v.pixmap_size() == (2000, 3000)
    assert _centre(v) == pytest.approx(rotate_point(0.3, 0.6, 1), abs=0.01)


def test_eye_point_with_turned_photo(qtbot, big: Path) -> None:  # noqa: ANN001
    tile = _tile(qtbot, _record(big, rotation=1))
    v = tile.viewer
    x, y = rotate_point(0.2 + 0.1 / 2, 0.1 + 0.1 * 0.42, 1)  # face box (0.2, 0.1, 0.1, 0.1) as E computes it
    v.set_zoom(2.0, QPointF(x, y))
    _full(qtbot, v)
    assert v.pixmap_size() == (2000, 3000)
    assert _centre(v) == pytest.approx((x, y), abs=0.01)


def test_tile_header_follows_record(qtbot, big: Path) -> None:  # noqa: ANN001
    rec = _record(big)
    tile = _tile(qtbot, rec)
    tile.set_number(2)
    assert tile.viewer.wait_idle(20000)
    token = tile.viewer._token
    tile.update_record(replace(rec, flag="keep", rating=3, favorite=True))
    text = tile.header.toolTip()
    assert text.startswith("2") and "BIG_0001.jpg" in text and "Chọn" in text and "★★★" in text and "♥" in text
    assert tile.viewer._token == token  # no reload
    tile.update_record(replace(rec, flag="reject"))
    assert "Loại" in tile.header.toolTip() and "★" not in tile.header.toolTip()


def test_tile_hover_emits_id(qtbot, big: Path) -> None:  # noqa: ANN001
    tile = _tile(qtbot, _record(big, asset_id=42))
    seen: list[int] = []
    tile.hovered.connect(seen.append)
    pos = QPointF(10, 10)
    QApplication.sendEvent(tile, QEnterEvent(pos, pos, tile.mapToGlobal(pos)))
    assert seen == [42]


def test_tile_active_frame_and_notes(qtbot, big: Path) -> None:  # noqa: ANN001
    tile = _tile(qtbot, _record(big))
    assert tile.objectName() == "compareTile" and tile.property("active") in (None, False)
    tile.set_active(True)
    assert tile.property("active") is True
    tile.set_note("đang tải ảnh gốc…")
    assert "đang tải ảnh gốc…" in tile.header.toolTip()
    tile.set_ai_text("K 78 · G 85")
    assert tile.ai_label.isVisible() and tile.ai_label.text() == "K 78 · G 85"
    tile.set_ai_text(None)
    assert not tile.ai_label.isVisible()
    assert not tile.viewer.back_button.isVisible()  # Compare has its own way back


def test_tile_unreadable_file(qtbot, tmp_path: Path) -> None:  # noqa: ANN001
    bad = tmp_path / "BROKEN.jpg"
    bad.write_bytes(b"not a photo" * 50)
    rec = _record(bad)
    tile = _tile(qtbot, rec)
    qtbot.waitUntil(lambda: bool(tile.viewer._message), timeout=20000)
    tile.update_record(replace(rec, flag="keep"))
    assert "Chọn" in tile.header.toolTip()
