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
from app.ai.runtime import create_session

SHORT_SIDE = 384


def _round32(v: float) -> int:
    return max(32, int(round(v / 32)) * 32)


class AestheticModel:
    def __init__(self, registry: ModelRegistry, *, prefer_gpu: bool = True) -> None:
        path = registry.require("aesthetic")
        self.session = create_session(path, prefer_gpu=prefer_gpu)
        self._input = self.session.session.get_inputs()[0].name
        self.check: dict = {"device": self.session.device, "note": self.session.fallback_reason}  # for reports
        if self.session.device != "cpu":
            # The input size follows the photo's shape; a GPU provider may fail or round differently on it.
            # Keep the GPU only if it gives the CPU's answer on both orientations (owner's laptop:
            # DirectML 11 ms vs CPU 200 ms per detection, so this matters for 📊).
            problem = self._differs_from_cpu(path)
            self.check["problem"] = problem
            if problem:
                self.session = create_session(path, prefer_gpu=False)
                self.session.fallback_reason = f"Gợi ý thẩm mỹ chạy bằng CPU: {problem}"
            self.check["device"] = self.session.device

    PROBES = ((384, 576), (576, 384))  # (height, width) of a landscape and a portrait photo
    TOLERANCE = 0.02  # on the 1..10 scale

    def _differs_from_cpu(self, path) -> str | None:  # noqa: ANN001
        cpu = AestheticModel.__new__(AestheticModel)
        cpu.session = create_session(path, prefer_gpu=False)
        cpu._input = cpu.session.session.get_inputs()[0].name
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
            if self.session.device == "cpu":
                self.check["error"] = self.session.last_error
                return "card đồ hoạ lỗi khi chạy"  # Session.run already fell back
            cpu_score = cpu.score(probe)
            probes.append({"size": f"{w}x{h}", "gpu": gpu_score, "cpu": cpu_score,
                           "gpu_ms_first_run": round((t1 - t0) * 1000), "cpu_ms": round((time.perf_counter() - t1) * 1000)})
            if abs(gpu_score - cpu_score) > self.TOLERANCE:
                return "kết quả trên card đồ hoạ khác CPU"
        return None

    def score(self, bgr: np.ndarray) -> float:
        h, w = bgr.shape[:2]
        k = SHORT_SIDE / min(h, w)
        img = cv2.resize(bgr, (_round32(w * k), _round32(h * k)), interpolation=cv2.INTER_AREA if k < 1
                         else cv2.INTER_CUBIC)
        x = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        outs = self.session.run(None, {self._input: x})
        mos = next(o for o in outs if o.size == 1)
        return round(float(mos.reshape(-1)[0]), 4)
