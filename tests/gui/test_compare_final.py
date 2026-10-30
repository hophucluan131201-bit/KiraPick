"""Compare mode, part 2 task 8: long texts never cut off or covering the photo, DPI changes, slow sources, late
callbacks, shutdown with an export and a full decode running, Snap sizes with Compare open."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.quality.rank import Ranked  # noqa: E402
from app.quality.score import Score  # noqa: E402
from app.storage import decisions  # noqa: E402
from app.ui import main_window as mw  # noqa: E402
from app.ui import viewer as viewer_module  # noqa: E402
from app.ui.compare_view import CompareView  # noqa: E402
from tests.gui.test_compare_lifecycle import FakeFull  # noqa: E402
from tests.gui.test_compare_tile import _record  # noqa: E402
from tests.gui.test_compare_window import _mark, _opened  # noqa: E402
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: E402, F401 - fixture
from tests.gui.test_shutdown_timeout import _db_open, _watch_db  # noqa: E402
from tests.integration.test_import_job import _photo  # noqa: E402
from tests.gui.pointer import move_pointer, park_pointer  # noqa: E402, F401 - autouse fixture

LONG = ("mắt hơi mềm vì tiêu cự dài và tốc độ chụp thấp so với chuyển động của người mẫu, tóc che một phần mắt trái, "
        "ánh sáng nền cháy ở góc trên")


def _view(qtbot, tmp_path: Path, size=(560, 380), n=4):  # noqa: ANN001, ANN202
    photos = [_photo(tmp_path / f"A_VERY_LONG_FILE_NAME_FROM_THE_CAMERA_{i:04d}.jpg", 60 + i, size=(900, 600))
              for i in range(n)]
    view = CompareView()
    qtbot.addWidget(view)
    view.resize(*size)
    view.show()
    score = Score(total=71.0, parts={"eyes": 80.0, "focus": 70.0}, confidence=1.0, weaknesses=[LONG])
    recs = [_record(p, asset_id=i + 1, score=score, ranked=Ranked(71.0, 64.0, 68.0), flag="keep", rating=5,
                    favorite=True) for i, p in enumerate(photos)]
    view.show_records(recs, {}, 1)
    view.set_ai_visible(True)
    QApplication.processEvents()
    return view, recs


def test_long_ai_line_is_elided_inside_the_photo_and_never_covers_its_centre(qtbot, tmp_path) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, tmp_path)
    for r in recs:
        tile = view.tile(r.id)
        label, v = tile.ai_label, tile.viewer
        assert label.isVisible() and label.text().endswith("…") and LONG[1:] in label.toolTip()
        rect = label.geometry()
        assert rect.left() >= 0 and rect.right() <= v.width() and rect.bottom() <= v.height()  # inside the photo area
        assert rect.height() <= label.fontMetrics().height() + 12  # one line
        assert not rect.contains(v.rect().center())  # the middle of the photo stays visible


def test_long_header_is_elided_with_the_full_text_in_the_tooltip(qtbot, tmp_path) -> None:  # noqa: ANN001
    view, recs = _view(qtbot, tmp_path)
    for r in recs:
        header = view.tile(r.id).header
        assert header.fontMetrics().horizontalAdvance(header.text()) <= header.width()
        assert r.name in header.toolTip() and "★★★★★" in header.toolTip()
    view.resize(1600, 900)  # room again: the full text comes back
    qtbot.wait(300)
    assert view.tile(1).header.text().startswith("1") and recs[0].name in view.tile(1).header.text()


def test_dpi_change_keeps_true_100_percent(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """Moving the window to a 200 % screen: zoomed tiles re-apply 100 % = one photo pixel per physical pixel."""
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    v = w.compare.tile(ids[0]).viewer
    w.compare._set_active(ids[0])
    v.set_zoom(1.0)
    qtbot.waitUntil(v.is_full_resolution_shown, timeout=10000)
    assert v.transform().m11() == pytest.approx(1.0)
    for tile in w.compare.tiles:
        monkeypatch.setattr(tile.viewer, "devicePixelRatioF", lambda: 2.0)
    w.layout_controller.on_screen_changed(w.screen())
    assert v.zoom == 1.0 and v.transform().m11() == pytest.approx(0.5)


# ------------------------------------------------------------------ slow sources, late callbacks, shutdown
class _SlowPreview:
    """load_image that takes `delay` seconds (a slow network drive / USB card reader)."""

    def __init__(self, delay: float) -> None:
        self.delay, self.real = delay, viewer_module.load_image

    def __call__(self, *a, **k):  # noqa: ANN002, ANN003, ANN204
        time.sleep(self.delay)
        return self.real(*a, **k)


def _probe_block(qtbot, action, ms: int) -> int:  # noqa: ANN001
    """Largest gap of a 10 ms timer while `action` runs and `ms` pass: how long the Qt thread was blocked."""
    clock, worst, last = QElapsedTimer(), [0], [0]
    timer = QTimer()
    timer.setInterval(10)

    def tick() -> None:
        now = clock.elapsed()
        worst[0] = max(worst[0], now - last[0])
        last[0] = now

    timer.timeout.connect(tick)
    clock.start()
    timer.start()
    action()
    qtbot.wait(ms)
    timer.stop()
    return worst[0]


def test_slow_source_keeps_the_window_responsive_and_actions_work(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(viewer_module, "load_image", _SlowPreview(0.8))
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    ids = _mark(w, [0, 1, 2], current=0)
    block = _probe_block(qtbot, lambda: _key(qtbot, w, Qt.Key.Key_C), 300)
    assert w.in_compare() and block < 150  # previews still loading: the window never waits for them
    vp = w.compare.tile(ids[2]).viewer.viewport()
    move_pointer(w.compare.back_button, w.compare.back_button.rect().center())
    move_pointer(vp, vp.rect().center())
    _key(qtbot, w, Qt.Key.Key_X)
    assert decisions.get(w.project.conn, ids[2]).flag == "reject"
    assert decisions.get(w.project.conn, ids[0]).flag is None
    assert w.compare.wait_idle(20000)


def test_late_previews_after_leave_switch_and_dpi_change(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    """Previews still loading when Compare closes, reopens on other photos, the DPI changes, the folder switches:
    nothing late lands on the wrong tile, nothing crashes, the database closes after the pools are idle."""
    monkeypatch.setattr(viewer_module, "load_image", _SlowPreview(0.3))
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    _key(qtbot, w, Qt.Key.Key_Escape)  # previews still decoding
    others = _mark(w, [3, 4, 5], current=3)
    _key(qtbot, w, Qt.Key.Key_C)
    w.layout_controller.on_screen_changed(w.screen())
    assert w.compare.wait_idle(20000)
    QApplication.processEvents()
    for asset_id in others:
        tile = w.compare.tile(asset_id)
        assert tile is not None and tile.viewer._path == next(r.path for r in w.compare.records() if r.id == asset_id)
    assert all(w.compare.tile(i) is None for i in ids)
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    other = tmp_path / "other"
    _photo(other / "IMG_0001.jpg", 98)
    assert w.start_import(other) is not None  # previews loading again? the switch waits for the pools
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)
    assert events == ["db closed"] and not _db_open(project) and not w.in_compare()


def test_close_with_full_decode_and_export_running(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    """Closing while a Compare full decode AND an export run: the user is asked about the export, both are waited for,
    the database closes last."""
    from PySide6.QtWidgets import QMessageBox

    from tests.gui.test_shutdown_callbacks import _held_export

    monkeypatch.setattr(mw, "CLOSE_WAIT_MS", 50)
    fake = FakeFull()
    fake.gate = threading.Event()
    monkeypatch.setattr(viewer_module, "load_full_resolution", fake)
    w, ids = _opened(qtbot, env, [0, 1], current=0)
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    w.compare._set_active(ids[0])
    w.compare.tile(ids[0]).viewer.set_zoom(1.0)
    qtbot.waitUntil(lambda: fake.running == 1, timeout=5000)
    gate, dialog = _held_export(qtbot, w, tmp_path / "out", monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    assert w.close() is False and _db_open(project)
    gate.set()
    qtbot.wait(200)
    assert _db_open(project)  # the decode still runs
    fake.gate.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=10000)
    assert events == ["db closed"] and fake.running == 0


@pytest.mark.parametrize("size", [(1920, 1040), (1536, 824), (1280, 680), (960, 1040), (640, 680), (1920, 484),
                                  (640, 340), (560, 300)])
def test_snap_sizes_with_compare_open(qtbot, env: dict, size) -> None:  # noqa: ANN001, F811
    """WIDE / MEDIUM / NARROW / SHORT / TINY with four photos compared and the AI line on: no cut-off button, every
    photo shown at ≥ 160 px long side or the arrangement falls back, the AI line inside its tile."""
    from tests.gui.platform_checks import skip_unless_fits, skip_without_real_fonts
    from tests.gui.test_snap_sizes import clipped_buttons

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    skip_unless_fits(w, size)
    w.resize(*size)
    QApplication.processEvents()
    w.layout_controller.evaluate()
    w.select_row(0)
    _mark(w, [0, 1, 2, 3], current=0)
    _key(qtbot, w, Qt.Key.Key_C)
    _key(qtbot, w, Qt.Key.Key_I)
    qtbot.wait(250)
    view = w.compare
    a = view.arrangement
    assert a is not None and len(a.cells) == 4
    for r in view.records():
        tile = view.tile(r.id)
        assert tile.ai_label.geometry().right() <= tile.viewer.width()
    skip_without_real_fonts()
    assert clipped_buttons(w) == []


def _raw_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2] / "test_photos"
    nefs = sorted((root / "user_nikon").glob("*.NEF"))[:2] or sorted((root / "public").glob("*.NEF"))[:2]
    return nefs if len(nefs) == 2 else []


@pytest.mark.skipif(not _raw_files(), reason="RAW samples are git-ignored (local / owner files only)")
def test_real_raw_in_compare_reload_switch_and_close(qtbot, env: dict, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    """Review additional regression: two real NEFs and a JPEG compared; 100 % on a NEF shows the full-resolution
    frame (header size, turned by Xoay xem); P hits it only; a reload keeps Compare and the zoom; a folder switch then
    closes Compare and the database after the pools; the source files are byte-identical throughout."""
    import hashlib
    import shutil

    from app.ingest.preview import header_size, load_full_resolution

    folder = tmp_path / "raw"
    folder.mkdir()
    files = [Path(shutil.copy2(p, folder / p.name)) for p in _raw_files()]
    files.append(_photo(folder / "ZZZ_0001.jpg", 5, size=(1200, 800)))
    sha = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    w = _window(qtbot, env)
    _import(qtbot, w, folder)
    rows = {r.path.name: i for i, r in enumerate(w.model.records())}
    nef_row = rows[files[0].name]
    w.select_row(nef_row)
    ids = _mark(w, [rows[p.name] for p in files], current=nef_row)
    w.rotate_view()  # Xoay xem on the NEF before comparing
    _key(qtbot, w, Qt.Key.Key_C)
    assert w.in_compare()
    nef_id = w.model.records()[nef_row].id
    tile = w.compare.tile(nef_id)
    move_pointer(w.compare.back_button)
    move_pointer(tile.viewer.viewport())
    assert w.compare.active_id == nef_id
    _key(qtbot, w, Qt.Key.Key_Z)
    qtbot.waitUntil(tile.viewer.is_full_resolution_shown, timeout=60000)
    full = load_full_resolution(files[0]).image.size  # as the file shows it (EXIF orientation applied)
    assert tile.viewer.pixmap_size() == (full[1], full[0])  # then turned once by Xoay xem
    assert header_size(files[0]) is not None  # the budget's size before the decode
    others = [i for i in ids if i != nef_id]
    before = {i: decisions.get(w.project.conn, i) for i in others}
    _key(qtbot, w, Qt.Key.Key_P)
    assert decisions.get(w.project.conn, nef_id).flag == "keep"
    assert {i: decisions.get(w.project.conn, i) for i in others} == before
    w.reload_preserving_view()
    assert w.in_compare() and tile.viewer.zoom_percent() == 100
    events: list[str] = []
    project = _watch_db(w, events, monkeypatch)
    other = tmp_path / "other"
    _photo(other / "IMG_0001.jpg", 98)
    assert w.start_import(other) is not None
    qtbot.waitUntil(lambda: w.import_thread is None, timeout=20000)
    assert events == ["db closed"] and not _db_open(project) and not w.in_compare()
    w.close()
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files} == sha


def test_close_right_after_a_hover_never_reads_the_closed_database(qtbot, env: dict) -> None:  # noqa: F811
    """The panel follows the active photo 150 ms later: closing the window in between must not let that timer read
    the closed database (pytest-qt fails the test on any exception raised in the event loop)."""
    w, ids = _opened(qtbot, env, [0, 1, 2], current=0)
    move_pointer(w.compare.back_button)
    move_pointer(w.compare.tile(ids[2]).viewer.viewport())
    assert w.compare.active_id == ids[2]
    assert w.close()
    qtbot.wait(400)
