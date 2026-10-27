"""Face landmarks at full resolution (YuNet on a face crop) and face image quality (eDifFIQA)."""

from __future__ import annotations

import cv2
import numpy as np

from app.ai.models import ModelRegistry
from app.quality.measure import FaceGeometry, align_face

REFINE_LONG_SIDE = 480  # the face crop is analysed at about this size
REFINE_MARGIN = 0.6  # crop = face box grown by 60% on each side


class FaceRefiner:
    """Finds the face again inside its (stored) box on the full-resolution image."""

    def __init__(self, registry: ModelRegistry) -> None:
        self._model = str(registry.require("face_detector"))
        self._detectors: dict[tuple[int, int], cv2.FaceDetectorYN] = {}

    def refine(self, full: np.ndarray, nbox: tuple[float, float, float, float]) -> FaceGeometry | None:
        h, w = full.shape[:2]
        x, y, bw, bh = nbox[0] * w, nbox[1] * h, nbox[2] * w, nbox[3] * h
        mx, my = bw * REFINE_MARGIN, bh * REFINE_MARGIN
        x0, y0 = max(0, int(x - mx)), max(0, int(y - my))
        x1, y1 = min(w, int(x + bw + mx)), min(h, int(y + bh + my))
        if x1 - x0 < 16 or y1 - y0 < 16:
            return None
        crop = full[y0:y1, x0:x1]
        scale = min(1.0, REFINE_LONG_SIDE / max(crop.shape[:2]))
        small = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else crop
        size = (small.shape[1], small.shape[0])
        det = self._detectors.get(size)
        if det is None:
            det = self._detectors[size] = cv2.FaceDetectorYN.create(self._model, "", size, 0.5, 0.3, 50)
        _, faces = det.detect(small)
        if faces is None or not len(faces):
            return None
        cx, cy = (x + bw / 2 - x0) * scale, (y + bh / 2 - y0) * scale
        best = min(faces, key=lambda f: (f[0] + f[2] / 2 - cx) ** 2 + (f[1] + f[3] / 2 - cy) ** 2)
        k = 1.0 / scale
        box = (float(best[0] * k + x0), float(best[1] * k + y0), float(best[2] * k), float(best[3] * k))
        landmarks = best[4:14].reshape(5, 2).astype(np.float32) * k + np.array([x0, y0], np.float32)
        return FaceGeometry(box, landmarks, float(best[14]))


class FaceQuality:
    """eDifFIQA(T): higher = better face image (sharp, frontal, unoccluded). Roughly 0..1."""

    def __init__(self, registry: ModelRegistry) -> None:
        self._net = cv2.dnn.readNetFromONNX(str(registry.require("face_quality")))

    def score(self, full: np.ndarray, face: FaceGeometry) -> float | None:
        aligned = align_face(full, face)
        if aligned is None:
            return None
        blob = ((cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0) - 0.5) / 0.5
        self._net.setInput(np.ascontiguousarray(blob.transpose(2, 0, 1)[None]))
        return round(float(self._net.forward().reshape(-1)[0]), 4)
