"""Compare mode, peak memory while full-resolution frames decode (review: RAM at 24–61 MP, not only the cache size
afterwards). Four tiles zoomed to 100 % one after another with the real loader; process RSS sampled every 10 ms in a
thread. Synthetic 45 / 61 MP JPEGs (smooth content: small files, full-size pixels); the owner's 24 MP NEF files when
present (git-ignored; skipped otherwise). Marker `perf`; numbers only."""

from __future__ import annotations

import ctypes
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from app.ui import compare_view as cv
from app.ui.compare_view import CompareView
from tests.gui.test_compare_tile import _record
from tests.perf.test_grid_perf import _record as _perf_record
from tests.perf.test_hd_perf import ROOT

pytestmark = pytest.mark.perf
OWNER = ROOT / "test_photos" / "user_nikon"


def _rss() -> int:
    """Resident memory of this process in bytes (Linux /proc; Windows working set)."""
    if sys.platform == "win32":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = kernel32.K32GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        c = Counters()
        c.cb = ctypes.sizeof(c)
        if not get_info(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return int(c.WorkingSetSize)
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


class _Sampler:
    def __init__(self, view: CompareView) -> None:
        self.view, self.peak, self.max_full = view, 0, 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, _rss())
            self.max_full = max(self.max_full, self.view.full_pool.activeThreadCount())
            time.sleep(0.01)

    def __enter__(self) -> _Sampler:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()


def _trim() -> int:
    """glibc keeps freed heap pages; malloc_trim returns them, so the RSS after it is what is really in use."""
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except OSError:
            pass
    return _rss()


def _jpeg(path: Path, size: tuple[int, int], mark: int = 0) -> Path:
    """``mark`` changes the colour: different files (the import keeps one of identical photos)."""
    img = Image.linear_gradient("L").resize(size).convert("RGB")
    ImageDraw.Draw(img).ellipse((size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2), fill=(200, 80 + mark, 40))
    img.save(path, "JPEG", quality=85)
    return path


def _sets(tmp: Path) -> list[tuple[str, list[Path], tuple[int, int] | None]]:
    out = []
    for label, size in (("45mp", (8256, 5504)), ("61mp", (9504, 6336))):
        first = _jpeg(tmp / f"{label}_0.jpg", size)
        files = [first] + [Path(shutil.copy2(first, tmp / f"{label}_{i}.jpg")) for i in range(1, 4)]
        out.append((label, files, size))
    nefs = sorted(OWNER.glob("*.NEF"))[:4] if OWNER.is_dir() else []
    if len(nefs) == 4:
        out.insert(0, ("24mp_nef", nefs, None))
    return out


def test_peak_memory_zooming_four_tiles(qtbot, tmp_path: Path) -> None:  # noqa: ANN001
    for label, files, size in _sets(tmp_path):
        view = CompareView()
        qtbot.addWidget(view)
        view.resize(1600, 900)
        view.show()
        w, h = size or (6016, 4016)
        recs = [_record(p, asset_id=i + 1, width=w, height=h) for i, p in enumerate(files)]
        view.show_records(recs, {}, 1)
        assert view.wait_idle(120_000)
        QApplication.processEvents()
        base = _rss()
        assert base > 0  # a memory reading that silently returns 0 must fail, not report "0 MB"
        decode_peaks: list[int] = []
        with _Sampler(view) as s:
            for r in recs:
                before_peak = s.peak
                view._set_active(r.id)
                view.tile(r.id).viewer.set_zoom(1.0)
                assert view.wait_idle(120_000)
                QApplication.processEvents()
                decode_peaks.append(max(0, s.peak - before_peak))
                assert view.full_pixels() <= cv.FULL_BUDGET_PIXELS
        dropped = sum(1 for r in recs if view.tile(r.id).viewer.zoom is None)
        held, zoomed_mb = view.full_pixels(), _rss() / 1e6
        view.clear()  # leaving Compare: every full frame is given back (budget and caches)
        QApplication.processEvents()
        assert view.full_pixels() == 0 and all(not t.viewer._full_cache for t in view.tiles)
        cleared_mb = _rss() / 1e6
        trimmed_mb = _trim() / 1e6  # Linux: what the allocator still keeps vs what is really in use
        _perf_record(f"compare_memory_{label}", 4, base_mb=base / 1e6, peak_mb=s.peak / 1e6,
                     peak_over_base_mb=(s.peak - base) / 1e6, zoomed_mb=zoomed_mb, after_leave_mb=cleared_mb,
                     after_leave_trimmed_mb=trimmed_mb, held_full_mpx=held / 1e6, tiles_dropped=dropped,
                     max_full_decodes_at_once=s.max_full)
        assert s.max_full <= 1
        if label == "61mp":
            assert dropped == 1  # three 61 MP frames fit, the fourth drops the least recently active
        else:
            assert dropped == 0
        view.close()
        del view
        QApplication.processEvents()
