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
        # Not on DirectML: the input size changes with the photo's shape, which DirectML handles badly
        # (installer 2.0.4: every photo of the quality stage failed on it). CUDA or the CPU.
        self.session = create_session(registry.require("aesthetic"), prefer_gpu=prefer_gpu, allow_directml=False)
        self._input = self.session.session.get_inputs()[0].name

    def score(self, bgr: np.ndarray) -> float:
        h, w = bgr.shape[:2]
        k = SHORT_SIDE / min(h, w)
        img = cv2.resize(bgr, (_round32(w * k), _round32(h * k)), interpolation=cv2.INTER_AREA if k < 1
                         else cv2.INTER_CUBIC)
        x = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        outs = self.session.run(None, {self._input: x})
        mos = next(o for o in outs if o.size == 1)
        return round(float(mos.reshape(-1)[0]), 4)
