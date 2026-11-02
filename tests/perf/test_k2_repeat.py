"""K2: P / X latency repeatability (measurement only, marker `k2`; never part of the normal or perf runs).

Each test makes 200 P / X presses the way the perf tests do (Compare on 4 photos of a 10,000-photo session, and the
grid of a 10,000-photo session) and writes one JSON line per press to $KIRAPICK_K2_OUT:
  handler_ms  w.set_flag(...) alone (the input handler: decision write, model update, auto-advance, panel refresh)
  ui_ms       the synchronous repaint of what the press changed (visible update)
  total_ms    both
  gc_ms       garbage-collector pauses inside the press; gc_count
  decode_callbacks  thumbnail / full-frame decode results delivered during the press
  parts       time per instrumented part (as in test_sustained_culling) -> dominant part
No assertion: thresholds stay in the perf tests; scripts/k2_repeat.py runs this 20 times in fresh processes.
"""

from __future__ import annotations

import contextlib
import gc
import json
import os
import time

import pytest

from tests.perf.test_compare_perf import _hover, _mark
from tests.perf.test_grid_perf import _ms, _open, _paint, session  # noqa: F401 - fixture

pytestmark = pytest.mark.k2
PRESSES = 200


def _write(row: dict) -> None:
    out = os.environ.get("KIRAPICK_K2_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")


class _Meter:
    """GC pauses, decode callbacks and per-part timings around each press."""

    def __init__(self, w, monkeypatch) -> None:  # noqa: ANN001
        self.parts: dict[str, float] = {}
        self.pauses: list[float] = []
        self._started: list[float] = []
        self.decodes = 0
        w.model.thumbnail_ready.connect(self._decoded)  # extra listeners; the app's own slots are untouched
        for name in ("_learn_taste", "_show_inspector", "_update_counts", "refresh_steps", "step"):
            self._timed(monkeypatch, w, name, name.strip("_"))
        self._timed(monkeypatch, w.model, "refresh_record", "refresh_record")
        real = w.project.transaction

        @contextlib.contextmanager
        def timed():  # noqa: ANN202
            t0 = time.perf_counter()
            with real() as conn:
                yield conn
            self.parts["transaction"] = self.parts.get("transaction", 0.0) + _ms(t0)

        monkeypatch.setattr(w.project, "transaction", timed)
        gc.callbacks.append(self._gc)

    def _decoded(self, *_a: object) -> None:
        self.decodes += 1

    def _gc(self, phase: str, _info: dict) -> None:
        if phase == "start":
            self._started.append(time.perf_counter())
        elif self._started:
            self.pauses.append(_ms(self._started.pop()))

    def _timed(self, monkeypatch, obj, name: str, label: str) -> None:  # noqa: ANN001
        real = getattr(obj, name)

        def wrapper(*a, **k):  # noqa: ANN002, ANN003, ANN202
            t0 = time.perf_counter()
            try:
                return real(*a, **k)
            finally:
                self.parts[label] = self.parts.get(label, 0.0) + _ms(t0)

        monkeypatch.setattr(obj, name, wrapper)

    def close(self) -> None:
        gc.callbacks.remove(self._gc)


def _presses(name: str, w, meter: _Meter, repaint) -> None:  # noqa: ANN001
    run = int(os.environ.get("KIRAPICK_K2_RUN", "0"))
    for i in range(PRESSES):
        meter.parts.clear()
        pauses, decodes = len(meter.pauses), meter.decodes
        t0 = time.perf_counter()
        w.set_flag("keep" if i % 2 == 0 else "reject")
        t1 = time.perf_counter()
        repaint()
        t2 = time.perf_counter()
        handler, ui = (t1 - t0) * 1000, (t2 - t1) * 1000
        parts = {k: round(v, 3) for k, v in meter.parts.items()}
        other = handler - sum(meter.parts.values())
        _write({"test": name, "run": run, "press": i, "handler_ms": round(handler, 3), "ui_ms": round(ui, 3),
                "total_ms": round(handler + ui, 3), "gc_ms": round(sum(meter.pauses[pauses:]), 3),
                "gc_count": len(meter.pauses) - pauses, "decode_callbacks": meter.decodes - decodes,
                "parts": {**parts, "handler_other": round(other, 3), "ui_paint": round(ui, 3)}})


def test_k2_compare_px(session) -> None:  # noqa: ANN001, F811
    w, make = session
    _open(w, make(10000))
    w.select_row(5000)
    _mark(w, [5000, 5001, 5002, 5003])
    assert w.show_compare()
    w.compare.repaint()
    _paint(w)
    ids = [r.id for r in w.compare.records()]
    _hover(w, ids[1])
    meter = _Meter(w, pytest.MonkeyPatch())
    for r in w.compare.records():
        w.compare.tile(r.id).viewer.full_frame_loaded.connect(meter._decoded)

    def repaint() -> None:
        w.compare.repaint()
        _paint(w)

    try:
        _presses("compare_px", w, meter, repaint)
    finally:
        meter.close()


def test_k2_grid_px(session) -> None:  # noqa: ANN001, F811
    w, make = session
    _open(w, make(10000))
    w.select_row(0)
    w.grid.setFocus()
    meter = _Meter(w, pytest.MonkeyPatch())
    try:
        _presses("grid_px", w, meter, lambda: _paint(w))
    finally:
        meter.close()
