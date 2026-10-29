"""Compare mode, part 2 task 3: the Compare page — tiles placed by arrange() on the page's own size, the active photo
follows the pointer at once, the detail panel follows 150 ms later (flushed when the pointer leaves the tiles)."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QEvent, QPoint, QPointF  # noqa: E402
from PySide6.QtGui import QEnterEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget  # noqa: E402

from app.ui import compare_view as cv  # noqa: E402
from app.ui.compare_view import PANEL_DELAY_MS, CompareView  # noqa: E402
from tests.gui.test_compare_tile import _centre, _record  # noqa: E402
from tests.integration.test_import_job import _photo  # noqa: E402
from tests.gui.pointer import move_pointer  # noqa: E402


@pytest.fixture
def photos(tmp_path: Path) -> list[Path]:
    return [_photo(tmp_path / f"IMG_{i:04d}.jpg", 10 + i, size=(3000, 2000)) for i in range(4)]


def _view(qtbot, photos: list[Path], n: int = 3, size=(1600, 900), active: int | None = None):  # noqa: ANN001, ANN202
    view = CompareView()
    qtbot.addWidget(view)
    view.resize(*size)
    view.show()
    recs = [_record(p, asset_id=i + 1) for i, p in enumerate(photos[:n])]
    view.show_records(recs, {}, active if active is not None else recs[0].id)
    QApplication.processEvents()
    return view, recs


def _enter(view: CompareView, asset_id: int) -> None:
    """The real pointer onto the tile's photo (from outside the tiles first, so it is a real move)."""
    move_pointer(view.back_button, view.back_button.rect().center())
    viewport = view.tile(asset_id).viewer.viewport()
    assert move_pointer(viewport, viewport.rect().center())


def _leave(view: CompareView) -> None:
    QApplication.sendEvent(view.page, QEvent(QEvent.Type.Leave))


def _signals(view: CompareView) -> tuple[list[int], list[int]]:
    active: list[int] = []
    panel: list[int] = []
    view.active_changed.connect(active.append)
    view.panel_photo_changed.connect(panel.append)
    return active, panel


def test_active_changes_immediately_on_enter(qtbot, photos) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos)
    active, panel = _signals(view)
    _enter(view, 2)
    assert view.active_id == 2 and active == [2] and panel == []  # no event-loop turn needed for the target
    assert view.tile(2).property("active") is True and view.tile(1).property("active") is False
    qtbot.wait(PANEL_DELAY_MS + 60)
    assert panel == [2]


def test_quick_hover_emits_panel_once(qtbot, photos) -> None:  # noqa: ANN001
    view, _recs = _view(qtbot, photos)
    active, panel = _signals(view)
    move_pointer(view.back_button, view.back_button.rect().center())
    for asset_id in (1, 2, 3):  # one sweep across the tiles
        viewport = view.tile(asset_id).viewer.viewport()
        move_pointer(viewport, viewport.rect().center())
        qtbot.wait(15)
    assert active == [2, 3]  # 1 was already active
    qtbot.wait(PANEL_DELAY_MS + 60)
    assert panel == [3]


def test_leave_keeps_last_and_flushes_panel(qtbot, photos) -> None:  # noqa: ANN001
    view, _recs = _view(qtbot, photos)
    _active, panel = _signals(view)
    _enter(view, 3)
    _leave(view)
    assert view.active_id == 3 and panel == [3]  # at once, not after 150 ms
    qtbot.wait(PANEL_DELAY_MS + 60)
    assert panel == [3]  # not emitted a second time


def test_initial_active_without_hover(qtbot, photos) -> None:  # noqa: ANN001
    view = CompareView()
    qtbot.addWidget(view)
    view.resize(1600, 900)
    view.show()
    active, panel = _signals(view)
    recs = [_record(p, asset_id=i + 1) for i, p in enumerate(photos[:3])]
    view.show_records(recs, {}, 2)
    assert view.active_id == 2 and view.tile(2).property("active") is True
    assert active == [2] and panel == [2]  # the panel shows the active photo at once when Compare opens
    assert [t.property("active") for t in (view.tile(1), view.tile(3))] == [False, False]


def test_layout_matches_arrange(qtbot, photos) -> None:  # noqa: ANN001
    view, _recs = _view(qtbot, photos, n=3)
    view.set_arrangement("grid")
    QApplication.processEvents()
    a, b, c = (view.tile(i).geometry() for i in (1, 2, 3))
    assert (view.arrangement.rows, view.arrangement.cols) == (2, 2)
    assert a.top() == b.top() and a.right() < b.left() and c.top() > a.bottom()
    assert c.left() == a.left() and c.right() == b.right()  # the third spans both columns
    assert abs(a.width() - b.width()) <= 1


def test_arrange_uses_the_page_size(qtbot, photos, monkeypatch) -> None:  # noqa: ANN001
    seen: list[tuple[int, int]] = []
    real = cv.arrange
    monkeypatch.setattr(cv, "arrange", lambda sizes, area, mode, **k: seen.append(area) or real(sizes, area, mode, **k))
    window = QWidget()
    qtbot.addWidget(window)
    row = QHBoxLayout(window)
    side, detail = QWidget(), QWidget()
    side.setFixedWidth(260)
    detail.setFixedWidth(380)
    view = CompareView()
    row.addWidget(side)
    row.addWidget(view, 1)
    row.addWidget(detail)
    window.resize(1600, 1000)
    window.show()
    QApplication.processEvents()
    view.show_records([_record(p, asset_id=i + 1) for i, p in enumerate(photos[:2])], {}, 1)
    QApplication.processEvents()
    page = view.page.size()
    assert seen and seen[-1] == (page.width(), page.height())
    assert page.width() < 1600 - 260 - 380 + 1 and page.height() < 1000


def test_resize_keeps_each_tile_zoom(qtbot, photos) -> None:  # noqa: ANN001
    view, _recs = _view(qtbot, photos, n=2)
    points = {1: QPointF(0.3, 0.4), 2: QPointF(0.7, 0.6)}
    for asset_id, point in points.items():
        view.tile(asset_id).viewer.set_zoom(1.0, point)
    for asset_id in points:
        qtbot.waitUntil(view.tile(asset_id).viewer.is_full_resolution_shown, timeout=20000)
    QApplication.processEvents()
    before = (view.arrangement.rows, view.arrangement.cols)
    view.resize(960, 1000)
    qtbot.wait(cv.REARRANGE_MS + 80)
    assert (view.arrangement.rows, view.arrangement.cols) != before  # 1 × 2 → 2 × 1
    for asset_id, point in points.items():
        v = view.tile(asset_id).viewer
        assert v.zoom == 1.0
        assert _centre(v) == pytest.approx((point.x(), point.y()), abs=0.01)


def test_rotation_rearranges_keeping_zoom(qtbot, photos, monkeypatch) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos, n=2, size=(1200, 800))
    other = view.tile(2).viewer
    other.set_zoom(2.0, QPointF(0.35, 0.65))
    qtbot.waitUntil(other.is_full_resolution_shown, timeout=20000)
    QApplication.processEvents()
    seen: list[list] = []
    real = cv.arrange
    monkeypatch.setattr(cv, "arrange", lambda sizes, area, mode, **k: seen.append(list(sizes)) or real(sizes, area, mode, **k))
    view.update_record(replace(recs[0], rotation=1))
    QApplication.processEvents()
    assert seen and seen[-1] == [(2000, 3000), (3000, 2000)]  # recomputed with the turned size
    assert other.zoom == 2.0 and _centre(other) == pytest.approx((0.35, 0.65), abs=0.01)
    assert view.tile(1).viewer._rotation == 1


def test_update_record_without_size_change_does_not_rearrange(qtbot, photos, monkeypatch) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos, n=2)
    calls: list[int] = []
    real = cv.arrange
    monkeypatch.setattr(cv, "arrange", lambda *a, **k: calls.append(1) or real(*a, **k))
    view.update_record(replace(recs[0], flag="keep", rating=4))
    assert calls == [] and "Chọn" in view.tile(1).header.toolTip()


def test_tiles_and_pools_created_once(qtbot, photos) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos, n=4)
    tiles = list(view.tiles)
    pools = (view.preview_pool, view.full_pool)
    for n in (2, 3, 4, 2, 3):
        view.clear()
        assert view.active_id is None and all(not t.isVisible() for t in view.tiles)
        view.show_records(recs[:n], {}, recs[0].id)
        assert sum(t.isVisible() for t in view.tiles) == n
    assert list(view.tiles) == tiles and len(tiles) == 4
    assert (view.preview_pool, view.full_pool) == pools
    assert view.preview_pool.maxThreadCount() == 1 and view.full_pool.maxThreadCount() == 1
    assert all(t.viewer._pool is view.preview_pool and t.viewer._full_pool is view.full_pool for t in tiles)
    assert view.records() == recs[:3] and [view.tile(r.id).header.toolTip()[0] for r in recs[:3]] == ["1", "2", "3"]


def test_back_button_requests_back(qtbot, photos) -> None:  # noqa: ANN001
    view, _recs = _view(qtbot, photos, n=2)
    hits: list[int] = []
    view.back_requested.connect(lambda: hits.append(1))
    view.back_button.click()
    assert hits == [1]


def test_resting_pointer_does_not_pick_a_tile_when_compare_opens(qtbot, photos) -> None:  # noqa: ANN001
    """Qt sends Enter to a tile that appears under a resting pointer: the initial active photo stays (spec) until
    the pointer really moves."""
    view = CompareView()
    qtbot.addWidget(view)
    view.resize(1600, 900)
    view.show()
    qtbot.waitExposed(view)
    recs = [_record(p, asset_id=i + 1) for i, p in enumerate(photos[:3])]
    view.show_records(recs, {}, 2)
    QApplication.processEvents()
    tile = view.tile(3)
    pos = QPointF(5, 5)
    QApplication.sendEvent(tile, QEnterEvent(pos, pos, tile.mapToGlobal(pos)))  # appeared under the pointer
    assert view.active_id == 2
    viewport = tile.viewer.viewport()
    from PySide6.QtGui import QCursor

    start = QCursor.pos()
    moved = move_pointer(viewport, viewport.rect().center() + QPoint(3, 3))  # now the user moves
    under = QApplication.widgetAt(QCursor.pos())
    assert moved and view.active_id == 3, (moved, view.active_id, (start.x(), start.y()),
                                           (QCursor.pos().x(), QCursor.pos().y()), type(under).__name__,
                                           under is viewport, view._armed)
