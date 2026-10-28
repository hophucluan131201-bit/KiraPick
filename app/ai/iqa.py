"""TOPIQ no-reference quality models (IQA-PyTorch, PolyForm Noncommercial; research training data).

- TechnicalIQA: CFANet trained on KonIQ-10k — "how good is this photo technically" (noise, blur,
  compression, exposure) on 0..1. Whole photo, shorter side 384, sides multiples of 32.
- FaceIQA: TOPIQ trained on CGFIQA-40k — quality of a face crop on 0..1. The face box is enlarged
  1.5x, made square and resized to 512 (the model was trained on aligned 512 px faces; KiraPick
  does not align, so the number is a hint, used with the existing face-quality measure).
Both use the aesthetic model's GPU scheme (fixed-size graphs checked against the CPU).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.ai.aesthetic import AestheticModel

MIN_FACE_PX = 48  # smaller faces are not judged


class TechnicalIQA(AestheticModel):
    MODEL_ID = "tech_iqa"
    TOLERANCE = 0.01  # on 0..1


class FaceIQA(AestheticModel):
    MODEL_ID = "face_iqa"
    SHORT_SIDE = 512
    PROBES = ((512, 512),)
    TOLERANCE = 0.01

    def score(self, bgr: np.ndarray, face: tuple[float, float, float, float] | None = None) -> float | None:  # type: ignore[override]
        if face is None:  # the start-up GPU check passes a whole (square) probe image
            return super().score(bgr)
        h, w = bgr.shape[:2]
        fx, fy, fw, fh = face[0] * w, face[1] * h, face[2] * w, face[3] * h
        side = 1.5 * max(fw, fh)
        if max(fw, fh) < MIN_FACE_PX:
            return None
        cx, cy = fx + fw / 2, fy + fh / 2
        x0, y0 = int(round(cx - side / 2)), int(round(cy - side / 2))
        x1, y1 = int(round(cx + side / 2)), int(round(cy + side / 2))
        pad = max(0, -x0, -y0, x1 - w, y1 - h)
        if pad:
            bgr = cv2.copyMakeBorder(bgr, pad, pad, pad, pad, cv2.BORDER_REFLECT)
            x0, y0, x1, y1 = x0 + pad, y0 + pad, x1 + pad, y1 + pad
        crop = bgr[y0:y1, x0:x1]
        crop = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_AREA if crop.shape[0] > 512 else cv2.INTER_CUBIC)
        return super().score(crop)
