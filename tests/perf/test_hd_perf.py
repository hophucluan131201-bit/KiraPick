"""HD thumbnail cost (review RV13-02): per-photo decode time for JPEG and real RAW files (embedded preview vs the
half-size demosaic fallback), disk use of the cached HD files, and repeated decodes when the card size slider goes
140 → 340 → 140 → 340 on a 200 % screen (marker `perf`). Photos are only read."""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.ingest.preview import load_image
from app.ui import asset_model
from tests.perf.test_grid_perf import _record

pytestmark = pytest.mark.perf
ROOT = Path(__file__).resolve().parents[2]
RAW_DIRS = [ROOT / "test_photos" / "user_nikon", ROOT / "test_photos" / "user_nikon_crop", ROOT / "test_photos" / "mei"]


def _raws() -> list[Path]:
    exts = {".nef", ".arw", ".cr3", ".cr2", ".dng", ".raf", ".orf", ".rw2", ".pef"}
    return [p for d in RAW_DIRS if d.is_dir() for p in sorted(d.iterdir()) if p.suffix.lower() in exts]


def _jpegs(folder: Path, count: int = 8) -> list[Path]:
    """24 MP JPEGs with photo-like structure (gradients and shapes, not noise: realistic file sizes)."""
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(count):
        img = Image.linear_gradient("L").resize((6000, 4000)).convert("RGB")
        d = ImageDraw.Draw(img)
        for k in range(40):
            x, y = (k * 149 + i * 37) % 5600, (k * 97 + i * 53) % 3600
            d.ellipse((x, y, x + 400, y + 400), fill=((k * 50) % 255, (k * 80 + i * 20) % 255, (k * 30) % 255))
        path = folder / f"big_{i}.jpg"
        img.save(path, "JPEG", quality=90)
        out.append(path)
    return out


def _time(fn) -> float:  # noqa: ANN001
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000


def test_hd_decode_jpeg(tmp_path: Path) -> None:
    photos = _jpegs(tmp_path / "jpg")
    hd_dir = tmp_path / "hd"
    times = [_time(lambda p=p, i=i: asset_model.hd_thumbnail(p, hd_dir, i)) for i, p in enumerate(photos)]
    cached = [_time(lambda p=p, i=i: asset_model.hd_thumbnail(p, hd_dir, i)) for i, p in enumerate(photos)]
    sizes = [f.stat().st_size / 1024 for f in hd_dir.glob("*.jpg")]
    _record("hd_jpeg_24mp", len(photos), decode_median_ms=statistics.median(times), decode_worst_ms=max(times),
            cached_median_ms=statistics.median(cached), hd_file_kb_median=statistics.median(sizes),
            source_mb_median=statistics.median(p.stat().st_size / 1e6 for p in photos))
    assert len(sizes) == len(photos)


@pytest.mark.skipif(not _raws(), reason="no RAW samples in test_photos/ (git-ignored, not in CI)")
def test_hd_decode_raw_embedded_vs_demosaic(tmp_path: Path) -> None:
    rows = []
    for path in _raws():
        try:
            t0 = time.perf_counter()
            embedded = load_image(path, max_long_side=asset_model.HD_LONG_SIDE, min_long_side=asset_model.HD_LONG_SIDE)
            fast = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            load_image(path, max_long_side=asset_model.HD_LONG_SIDE, min_long_side=100_000)  # forces the demosaic
            slow = (time.perf_counter() - t0) * 1000
        except Exception as exc:  # noqa: BLE001 - an unsupported sample is reported, not fatal
            print(f"\nskip {path.suffix}: {type(exc).__name__}")
            continue
        rows.append((path, embedded.source.value, fast, slow))
    hd_dir = tmp_path / "hd"
    for i, (path, *_rest) in enumerate(rows):
        asset_model.hd_thumbnail(path, hd_dir, i)
    sizes = [f.stat().st_size / 1024 for f in hd_dir.glob("*.jpg")]
    nikon = [r for r in rows if "user_nikon" in str(r[0])]
    for label, subset in (("all_raw", rows), ("owner_nef", nikon)):
        if not subset:
            continue
        _record(f"hd_{label}", len(subset),
                embedded_used=sum(1 for r in subset if "embedded" in r[1]),
                path_median_ms=statistics.median(r[2] for r in subset), path_worst_ms=max(r[2] for r in subset),
                demosaic_median_ms=statistics.median(r[3] for r in subset),
                demosaic_worst_ms=max(r[3] for r in subset),
                hd_file_kb_median=statistics.median(sizes) if sizes else 0.0)
    print("\nper file (extension, source, ms used, ms if demosaic):")
    for path, source, fast, slow in rows:
        print(f"  {path.suffix:6} {source:28} {fast:8.0f} {slow:8.0f}")


def test_slider_round_trip_decodes(qtbot, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """140 → 340 → 140 → 340 px at 200 %: how often each visible card is decoded, and how many HD files are made."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from app.ui import main_window as mw
    from tests.gui.test_main_window import _import

    photos = tmp_path / "photos"
    for i, p in enumerate(_jpegs(photos, 6)):
        p.rename(photos / f"IMG_{i:04d}.jpg")
    monkeypatch.setattr(mw, "sessions_dir", lambda: tmp_path / "sessions")
    w = mw.MainWindow(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    w._maximize_on_show = False
    w.resize(1920, 1000)
    w.show()
    _import(qtbot, w, photos)
    decodes: list[tuple[int, int]] = []
    real = asset_model._ThumbTask

    class Counting(real):  # type: ignore[misc, valid-type]
        def __init__(self, asset_id, path, signals, target=asset_model.THUMB_DISPLAY, *rest) -> None:  # noqa: ANN001
            decodes.append((asset_id, target))
            super().__init__(asset_id, path, signals, target, *rest)

    monkeypatch.setattr(asset_model, "_ThumbTask", Counting)
    w.model.set_device_pixel_ratio(2.0)
    steps = []
    for size in (140, 340, 140, 340):
        before = len(decodes)
        t0 = time.perf_counter()
        w.set_grid_cell(size)
        for _ in range(3):
            w.grid.viewport().repaint()
            w.model.wait_for_thumbnails(30000)
            QApplication.processEvents()
        steps.append((size, len(decodes) - before, (time.perf_counter() - t0) * 1000))
    hd_files = len(list((w.project.cache_dir / asset_model.HD_DIR).glob("*.jpg")))
    _record("slider_round_trip", 6, **{f"step{i}_{s}px_decodes": d for i, (s, d, _t) in enumerate(steps)},
            **{f"step{i}_{s}px_ms": t for i, (s, _d, t) in enumerate(steps)}, hd_files=hd_files)
    assert steps[2][1] == 0  # back to small cards: the larger cached thumbnails are reused, nothing decoded
    assert hd_files == 6  # each photo's HD file made once, reused on the second 340 step
    w.close()
