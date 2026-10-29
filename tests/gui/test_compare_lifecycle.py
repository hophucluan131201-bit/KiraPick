"""Compare mode, part 2 task 7 (CR-P2-04): two single-thread pools, an exact-pixel budget for full-resolution frames
reserved before decoding, stale results ignored, and the part 1 shutdown contract (review RV-P2-B1-02, RV-P2-B2A-03).
Full decodes are replaced by a controllable fake loader: sizes are exact and nothing large is allocated."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.errors import ImageReadError  # noqa: E402
from app.ingest.preview import PreviewSource  # noqa: E402
from app.ui import compare_view as cv  # noqa: E402
from app.ui import main_window as mw  # noqa: E402
from app.ui import viewer as viewer_module  # noqa: E402
from app.ui.compare_view import CompareView  # noqa: E402
from tests.gui.test_compare_tile import _record  # noqa: E402
from tests.gui.test_compare_window import _mark, _opened  # noqa: E402
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: E402, F401 - fixture
from tests.gui.test_shutdown_timeout import _db_open, _watch_db  # noqa: E402
from tests.integration.test_import_job import _photo  # noqa: E402

DROPPED = "đã trả về vừa khung để đủ bộ nhớ"
OVERSIZED = "Ảnh quá lớn để mở độ phân giải đầy đủ khi so sánh — mở ở Xem lớn để soi 100 %"


class FakeFull:
    """Stands in for load_full_resolution: returns an image of the size set per file name, optionally held."""

    def __init__(self) -> None:
        self.sizes: dict[str, tuple[int, int]] = {}
        self.fail: set[str] = set()
        self.gate: threading.Event | None = None
        self.started: list[str] = []
        self.lock = threading.Lock()
        self.running = self.max_running = 0

    def __call__(self, path: Path, **_kw):  # noqa: ANN003, ANN204
        with self.lock:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            self.started.append(path.name)
        try:
            if self.gate is not None:
                self.gate.wait(20)
            if path.name in self.fail:
                raise ImageReadError(path, "test failure")
            w, h = self.sizes.get(path.name, (300, 200))
            return SimpleNamespace(image=Image.new("RGB", (w, h)), source=PreviewSource.DEMOSAIC_FULL)
        finally:
            with self.lock:
                self.running -= 1


@pytest.fixture
def fake(monkeypatch) -> FakeFull:  # noqa: ANN001
    f = FakeFull()
    monkeypatch.setattr(viewer_module, "load_full_resolution", f)
    return f


@pytest.fixture
def photos(tmp_path: Path) -> list[Path]:
    return [_photo(tmp_path / f"IMG_{i:04d}.jpg", 50 + i, size=(600, 400)) for i in range(4)]


def _view(qtbot, photos: list[Path], sizes: list[tuple[int, int]]):  # noqa: ANN001, ANN202
    view = CompareView()
    qtbot.addWidget(view)
    view.resize(1600, 900)
    view.show()
    recs = [_record(p, asset_id=i + 1, width=w, height=h) for i, (p, (w, h)) in enumerate(zip(photos, sizes))]
    view.show_records(recs, {}, 1)
    assert view.wait_idle(10000)
    QApplication.processEvents()
    return view, recs


def _zoom(qtbot, view: CompareView, asset_id: int, *, wait: bool = True) -> None:  # noqa: ANN001
    view._set_active(asset_id)
    view.tile(asset_id).viewer.set_zoom(1.0)
    if wait:
        assert view.wait_idle(10000)
        QApplication.processEvents()


def test_budget_counts_exact_pixels(qtbot, photos, fake) -> None:  # noqa: ANN001
    fake.sizes = {photos[0].name: (6000, 4000), photos[1].name: (6001, 4001)}
    view, recs = _view(qtbot, photos[:2], [(6000, 4000), (6001, 4001)])
    for r in recs:
        _zoom(qtbot, view, r.id)
    assert view.full_pixels() == 24_000_000 + 24_010_001  # no rounding, no megapixel units


def test_budget_drops_least_recently_active(qtbot, photos, fake, monkeypatch) -> None:  # noqa: ANN001
    """Four 61 MP frames do not fit 200 000 000 px; the same ratio scaled down 1000× so nothing large is allocated:
    budget 200 000, frames 301 × 200 = 60 200 (three fit, the fourth drops the least recently active)."""
    monkeypatch.setattr(cv, "FULL_BUDGET_PIXELS", 200_000)
    view, recs = _view(qtbot, photos, [(301, 200)] * 4)
    fake.sizes = {p.name: (301, 200) for p in photos}
    for r in recs[:3]:
        _zoom(qtbot, view, r.id)
    assert view.full_pixels() == 3 * 60_200
    _zoom(qtbot, view, recs[3].id)
    assert view.tile(1).viewer.zoom is None and DROPPED in view.tile(1).header.toolTip()
    assert view.full_pixels() == 3 * 60_200 <= cv.FULL_BUDGET_PIXELS
    assert all(view.tile(r.id).viewer.zoom == 1.0 for r in recs[1:])
    assert not view.tile(1).viewer.is_full_resolution_shown()


def test_default_budget_is_exact() -> None:
    assert cv.FULL_BUDGET_PIXELS == 200_000_000
    assert 3 * 9504 * 6336 <= cv.FULL_BUDGET_PIXELS < 4 * 9504 * 6336  # three 61 MP frames fit, four do not
    assert 4 * 8256 * 5504 <= cv.FULL_BUDGET_PIXELS  # four 45 MP frames fit


def test_reservation_before_decode(qtbot, photos, fake, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(cv, "FULL_BUDGET_PIXELS", 100_000)
    view, recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])  # 60 000 each: two do not fit
    fake.gate = threading.Event()
    _zoom(qtbot, view, recs[0].id, wait=False)
    _zoom(qtbot, view, recs[1].id, wait=False)  # same event-loop turn: tile 1's decode has not even started
    assert view.tile(1).viewer.zoom is None and DROPPED in view.tile(1).header.toolTip()
    assert view.full_pixels() == 60_000  # only tile 2 reserved
    fake.gate.set()
    assert view.wait_idle(10000)
    QApplication.processEvents()
    assert view.full_pixels() == 60_000 and not view.tile(1).viewer.is_full_resolution_shown()


def test_double_reservation_same_tile(qtbot, photos, fake) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])
    fake.gate = threading.Event()
    v = view.tile(recs[0].id).viewer
    view._set_active(recs[0].id)
    v.set_zoom(1.0)
    v.zoom_in()
    v.set_zoom(4.0)  # several zooms before the decode arrives
    assert view.full_pixels() == 60_000
    fake.gate.set()
    assert view.wait_idle(10000)
    QApplication.processEvents()
    assert fake.started.count(photos[0].name) == 1 and view.full_pixels() == 60_000


def test_decoded_larger_than_expected(qtbot, photos, fake, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(cv, "FULL_BUDGET_PIXELS", 200_000)
    view, recs = _view(qtbot, photos[:3], [(300, 200)] * 3)
    for r in recs[:2]:
        _zoom(qtbot, view, r.id)
    assert view.full_pixels() == 120_000
    fake.sizes = {photos[2].name: (400, 300)}  # recorded 300 × 200, decoded 400 × 300 = 120 000
    _zoom(qtbot, view, recs[2].id)
    assert view.tile(1).viewer.zoom is None  # 60 000 + 60 000 + 120 000 > 200 000: least recent dropped
    assert view.full_pixels() == 60_000 + 120_000


def test_reservation_released_on_failure_and_drop(qtbot, photos, fake) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])
    fake.fail = {photos[0].name}
    _zoom(qtbot, view, recs[0].id)
    assert view.full_pixels() == 0  # failed: released
    fake.gate = threading.Event()
    _zoom(qtbot, view, recs[1].id, wait=False)
    assert view.full_pixels() == 60_000
    view.clear()  # leaving Compare drops the reservation at once
    assert view.full_pixels() == 0
    fake.gate.set()
    assert view.wait_idle(10000)
    QApplication.processEvents()
    assert view.full_pixels() == 0  # the late result counts nothing


def test_oversized_single_frame_not_decoded(qtbot, photos, fake) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos[:2], [(20000, 12000), (300, 200)])  # 240 000 000 > the whole budget
    _zoom(qtbot, view, recs[0].id)
    tile = view.tile(recs[0].id)
    assert photos[0].name not in fake.started and view.full_pixels() == 0
    assert tile.viewer.zoom == 1.0 and not tile.viewer.is_full_resolution_shown()  # stays on the preview
    assert OVERSIZED in tile.header.toolTip()


def test_one_full_decode_at_a_time(qtbot, photos, fake) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, photos, [(300, 200)] * 4)
    fake.gate = threading.Event()
    for r in recs:
        _zoom(qtbot, view, r.id, wait=False)
    qtbot.wait(150)
    assert fake.max_running == 1 and view.full_pool.activeThreadCount() <= 1
    assert view.preview_pool.activeThreadCount() + view.full_pool.activeThreadCount() <= 2
    fake.gate.set()
    assert view.wait_idle(10000)
    assert fake.max_running == 1


def test_late_result_after_leaving_and_reopening_is_ignored(qtbot, photos, fake) -> None:  # noqa: ANN001
    """RV-P2-B1-02: close Compare and reopen it with other photos while the old decode is still running."""
    view, recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])
    fake.gate = threading.Event()
    _zoom(qtbot, view, recs[0].id, wait=False)
    qtbot.waitUntil(lambda: fake.running == 1, timeout=5000)
    view.clear()
    others = [_record(p, asset_id=i + 10, width=300, height=200) for i, p in enumerate(photos[2:])]
    view.show_records(others, {}, others[0].id)
    fake.gate.set()
    assert view.wait_idle(10000)
    QApplication.processEvents()
    assert view.full_pixels() == 0
    assert all(not view.tile(r.id).viewer.is_full_resolution_shown() for r in others)
    assert all(view.tile(r.id).viewer._path == r.path for r in others)


@pytest.mark.parametrize("how", ["close", "switch"])
def test_session_waits_for_compare_decodes(qtbot, env: dict, tmp_path: Path, monkeypatch, fake, how) -> None:  # noqa: ANN001, F811
    """RV-P2-B2A-03: closing / switching waits for both Compare pools; the database closes only after they are idle."""
    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    monkeypatch.setattr(mw, "SWITCH_WAIT_MS", 50)
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    fake.gate = threading.Event()
    w.compare._set_active(ids[0])
    w.compare.tile(ids[0]).viewer.set_zoom(1.0)
    qtbot.waitUntil(lambda: fake.running == 1, timeout=5000)
    if how == "close":
        assert w.close() is False and _db_open(project)
        assert "đọc ảnh để so sánh" in w.status.text()
        fake.gate.set()
        qtbot.waitUntil(lambda: not w.isVisible(), timeout=10000)
    else:
        other = tmp_path / "other"
        _photo(other / "IMG_0001.jpg", 99)
        assert w.start_import(other) is None and w.project is project and _db_open(project)
        fake.gate.set()
        monkeypatch.setattr(mw, "SWITCH_WAIT_MS", 10000)
        assert w.start_import(other) is not None
        qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)
    assert events == ["db closed"] and fake.running == 0


@pytest.mark.stress
def test_compare_stress(qtbot, env: dict, fake, monkeypatch) -> None:  # noqa: ANN001, F811
    """30 × (open, zoom every tile, then Esc / a reload / reopen) with decodes in flight: no crash, nothing leaked."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    for i in range(30):
        w.select_row(0)
        ids = _mark(w, [0, 1, 2, 3][: 2 + i % 3], current=0)
        _key(qtbot, w, Qt.Key.Key_C)
        for asset_id in ids:
            w.compare._set_active(asset_id)
            w.compare.tile(asset_id).viewer.set_zoom(1.0)
        if i % 3 == 0:
            w.reload_preserving_view()
        _key(qtbot, w, Qt.Key.Key_Escape)
        assert not w.in_compare() and w.compare.full_pixels() == 0
    assert w.compare.wait_idle(20000)


def test_leaving_compare_releases_full_frames(qtbot, photos, fake) -> None:  # noqa: ANN001
    """Found by the peak-memory benchmark: the tiles' viewers kept their full frames in their caches after Compare
    closed (memory outside the budget, which reported 0). Leaving must free them; reopening counts each frame once."""
    view, recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])
    for r in recs:
        _zoom(qtbot, view, r.id)
    assert view.full_pixels() == 120_000
    view.clear()
    assert view.full_pixels() == 0
    assert all(not t.viewer._full_cache for t in view.tiles)
    view.show_records(recs, {}, recs[0].id)
    assert view.wait_idle(10000)
    for r in recs:
        _zoom(qtbot, view, r.id)
    assert view.full_pixels() == 120_000  # decoded again and counted once each


def test_loupe_closing_a_session_frees_its_full_frames(qtbot) -> None:  # noqa: ANN001
    from app.ui.viewer import ImageViewer

    v = ImageViewer()
    qtbot.addWidget(v)
    v._full_cache[Path("x.jpg")] = (None, "raster")  # type: ignore[assignment]
    v.show_photo(None)
    assert not v._full_cache


# ------------------------------------------------------------------ review CR-P2-B3A-01 / RV-P2-B3A-01 / RV-P2-B3A-02
def test_unknown_size_frame_over_budget_after_decode(qtbot, photos, fake, monkeypatch) -> None:  # noqa: ANN001
    """CR-P2-B3A-01: no recorded size and no readable header → nothing to reserve; the decoded frame alone is over
    the budget → not kept: the tile goes back to the preview (still zoomed), says why, and nothing stays counted or
    cached."""
    monkeypatch.setattr(cv, "FULL_BUDGET_PIXELS", 200_000)
    monkeypatch.setattr(cv, "header_size", lambda _path: None)
    view, recs = _view(qtbot, photos[:2], [(0, 0), (300, 200)])
    _zoom(qtbot, view, recs[1].id)  # another tile holds a frame: it must not be dropped for a hopeless one
    fake.sizes = {photos[0].name: (600, 400)}  # 240 000 > 200 000 on its own
    _zoom(qtbot, view, recs[0].id)
    tile = view.tile(recs[0].id)
    assert not tile.viewer.is_full_resolution_shown() and not tile.viewer._full_cache
    assert tile.viewer.zoom == 1.0 and OVERSIZED in tile.header.toolTip()
    assert view.full_pixels() == 60_000 and view.tile(recs[1].id).viewer.is_full_resolution_shown()


def test_decoded_frame_that_fits_alone_drops_others(qtbot, photos, fake, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(cv, "FULL_BUDGET_PIXELS", 200_000)
    monkeypatch.setattr(cv, "header_size", lambda _path: None)
    view, recs = _view(qtbot, photos[:3], [(300, 200), (300, 200), (0, 0)])
    for r in recs[:2]:
        _zoom(qtbot, view, r.id)
    fake.sizes = {photos[2].name: (400, 300)}  # unknown before, 120 000 decoded: fits after dropping one tile
    _zoom(qtbot, view, recs[2].id)
    assert view.tile(recs[2].id).viewer.is_full_resolution_shown()
    assert view.tile(1).viewer.zoom is None and view.full_pixels() == 60_000 + 120_000


def test_unknown_size_read_from_the_header_avoids_the_decode(qtbot, photos, fake, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(cv, "header_size", lambda _path: (20000, 12000))
    view, recs = _view(qtbot, photos[:2], [(0, 0), (300, 200)])
    _zoom(qtbot, view, recs[0].id)
    assert photos[0].name not in fake.started and view.full_pixels() == 0
    assert OVERSIZED in view.tile(recs[0].id).header.toolTip()


def test_header_size_reads_only_the_header(tmp_path: Path, public_nef: Path) -> None:  # noqa: ANN001
    from app.ingest.preview import header_size

    jpg = _photo(tmp_path / "h.jpg", 1, size=(1234, 567))
    assert header_size(jpg) == (1234, 567)
    w, h = header_size(public_nef)
    assert w * h > 4_000_000  # the sensor image, not the embedded preview
    bad = tmp_path / "bad.nef"
    bad.write_bytes(b"nothing")
    assert header_size(bad) is None


def test_old_decode_after_drop_and_re_request_is_not_taken(qtbot, photos, monkeypatch) -> None:  # noqa: ANN001
    """RV-P2-B3A-01: drop a tile while its decode runs, zoom it again (same photo, same token): the old result is
    not taken for the new request; the new one is."""
    calls: list[threading.Event] = []
    sizes = iter([(400, 300), (300, 200)])

    def loader(path: Path, **_kw):  # noqa: ANN003, ANN202
        gate = threading.Event()
        calls.append(gate)
        gate.wait(20)
        w, h = next(sizes)
        return SimpleNamespace(image=Image.new("RGB", (w, h)), source=PreviewSource.DEMOSAIC_FULL)

    monkeypatch.setattr(viewer_module, "load_full_resolution", loader)
    view, recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])
    tile = view.tile(recs[0].id)
    _zoom(qtbot, view, recs[0].id, wait=False)
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=5000)
    view._release(tile)
    tile.viewer.drop_full()
    _zoom(qtbot, view, recs[0].id, wait=False)  # a new request for the same photo, the old decode still running
    calls[0].set()  # the OLD decode (400 × 300) arrives
    qtbot.waitUntil(lambda: len(calls) == 2, timeout=5000)
    QApplication.processEvents()
    assert not tile.viewer.is_full_resolution_shown() and view.full_pixels() == 60_000  # still the reservation
    calls[1].set()
    assert view.wait_idle(10000)
    QApplication.processEvents()
    assert tile.viewer.pixmap_size() == (300, 200) and view.full_pixels() == 60_000


def test_wait_idle_has_one_deadline_for_both_pools(qtbot, photos, fake) -> None:  # noqa: ANN001
    """RV-P2-B3A-02: both pools busy → wait_idle(300) gives up after about 300 ms, not 2 × 300."""
    import time

    from tests.gui.test_shutdown_timeout import _hold

    view, _recs = _view(qtbot, photos[:2], [(300, 200), (300, 200)])
    gate, events = threading.Event(), []
    _hold(view.preview_pool, gate, events, "preview")
    _hold(view.full_pool, gate, events, "full")
    t0 = time.monotonic()
    assert view.wait_idle(300) is False
    assert time.monotonic() - t0 < 0.45
    gate.set()
    assert view.wait_idle(5000)
