"""Aesthetic suggestion: TOPIQ (CFANet, ResNet50) trained on AVA photo-contest ratings.

It rates "how good a photo looks" the way AVA voters rated general photography
(landscapes, still life, people…), not cosplay specifically. KiraPick uses it only as a
small, clearly labelled hint. Input: the whole photo, shorter side 384 px, both sides
multiples of 32 (the exported graph needs that); output: mean score on 1..10.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.ai.models import ModelRegistry
from app.ai.runtime import Session, create_session

SHORT_SIDE = 384


def _round32(v: float) -> int:
    return max(32, int(round(v / 32)) * 32)


def _input_size(h: int, w: int, short_side: int = SHORT_SIDE) -> tuple[int, int]:
    """(height, width) the model sees for a photo of ``h`` x ``w``."""
    k = short_side / min(h, w)
    return _round32(h * k), _round32(w * k)


class AestheticModel:
    """CPU: one size-free session. GPU: one fixed-size session per photo shape (DirectML failed on the
    size-free graph: Reshape error, owner's self-test 2.1.0b5), checked against the CPU first and
    dropped for good on any GPU error."""

    MODEL_ID = "aesthetic"
    SHORT_SIDE = SHORT_SIDE
    PROBES: tuple[tuple[int, int], ...] = ((384, 576), (576, 384))  # landscape and portrait 3:2 photos
    TOLERANCE = 0.02  # on the 1..10 scale
    MAX_GPU_SHAPES = 4  # each fixed-size graph holds its own GPU memory

    def __init__(self, registry: ModelRegistry, *, prefer_gpu: bool = True) -> None:
        self._path = registry.require(self.MODEL_ID)
        self.session = create_session(self._path, prefer_gpu=False)  # any size; the GPU's reference
        self._input = self.session.session.get_inputs()[0].name
        self._gpu: dict[tuple[int, int], Session] = {}
        self.device = "cpu"
        self.check: dict = {"device": "cpu", "note": None}  # for reports and the log
        if not prefer_gpu:
            return
        first = self._gpu_session(*self.PROBES[0])
        self.check["note"] = first.fallback_reason
        if first.device == "cpu":
            return
        self.device = first.device
        # Keep the GPU only if it gives the CPU's answer on both orientations (owner's laptop:
        # DirectML 11 ms vs CPU 90 ms per detection, so this matters for 📊).
        problem = self._differs_from_cpu()
        self.check["problem"] = problem
        if problem:
            self._use_cpu(f"Gợi ý thẩm mỹ chạy bằng CPU: {problem}")
        self.check["device"] = self.device

    def _gpu_session(self, h: int, w: int) -> Session:
        if (h, w) not in self._gpu:
            if len(self._gpu) >= self.MAX_GPU_SHAPES:
                self._gpu.pop(next(iter(self._gpu)))  # the oldest shape
            self._gpu[(h, w)] = create_session(self._path, prefer_gpu=True, fixed_dims={"h": h, "w": w})
        return self._gpu[(h, w)]

    def _use_cpu(self, reason: str) -> None:
        self._gpu.clear()
        self.device = self.check["device"] = "cpu"
        self.session.fallback_reason = reason

    def _differs_from_cpu(self) -> str | None:
        import time

        self.check["probes"] = probes = []
        for h, w in self.PROBES:
            gx, gy = np.meshgrid(np.linspace(0, 255, w), np.linspace(0, 255, h))
            probe = np.dstack([gx, gy, np.full((h, w), 128.0)]).astype(np.uint8)  # smooth colour ramp
            t0 = time.perf_counter()
            try:
                gpu_score = self.score(probe)
            except Exception as exc:  # noqa: BLE001
                self.check["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                return f"card đồ hoạ lỗi ({type(exc).__name__})"
            t1 = time.perf_counter()
            if self.device == "cpu":
                return "card đồ hoạ lỗi khi chạy"  # score() already moved to the CPU
            cpu_score = self._mos(self.session, self._tensor(probe))
            probes.append({"size": f"{w}x{h}", "gpu": gpu_score, "cpu": cpu_score,
                           "gpu_ms_first_run": round((t1 - t0) * 1000), "cpu_ms": round((time.perf_counter() - t1) * 1000)})
            if abs(gpu_score - cpu_score) > self.TOLERANCE:
                return "kết quả trên card đồ hoạ khác CPU"
        return None

    def _tensor(self, bgr: np.ndarray) -> np.ndarray:
        h, w = bgr.shape[:2]
        th, tw = _input_size(h, w, self.SHORT_SIDE)
        img = cv2.resize(bgr, (tw, th), interpolation=cv2.INTER_AREA if th < h else cv2.INTER_CUBIC)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0

    def _mos(self, session: Session, x: np.ndarray) -> float:
        outs = session.run(None, {self._input: x})
        mos = next(o for o in outs if o.size == 1)
        return round(float(mos.reshape(-1)[0]), 4)

    def score(self, bgr: np.ndarray) -> float:
        x = self._tensor(bgr)
        if self.device == "cpu":
            return self._mos(self.session, x)
        gpu = self._gpu_session(*x.shape[2:])
        if gpu.device == "cpu":  # this shape could not get a GPU session
            self.check["error"] = gpu.fallback_reason
            self._use_cpu(f"Gợi ý thẩm mỹ chạy bằng CPU: {gpu.fallback_reason}")
            return self._mos(self.session, x)
        mos = self._mos(gpu, x)
        if gpu.device == "cpu":  # Session.run met a GPU error and answered on the CPU
            self.check["error"] = gpu.last_error
            self._use_cpu("Gợi ý thẩm mỹ chạy bằng CPU: card đồ hoạ lỗi khi chạy")
        return mos
