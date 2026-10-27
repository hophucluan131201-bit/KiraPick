"""Stronger, optional identity cues: ArcFace face embeddings and YoutuReID whole-body embeddings.

- ArcFace (InsightFace buffalo_l, ResNet50 trained on WebFace600K): 512-d vector of
  a face aligned to the 112x112 ArcFace template. Clearly better than SFace on the
  owner's labelled shoot, above all for photos taken far apart in time. Its weights
  are for non-commercial research only (see docs/model-licenses.md).
- YoutuReID (Apache-2.0): 768-d vector of a whole person crop (128x256). Trained on
  street pedestrians, so it mostly sees clothing and silhouette; it is combined
  with the colour descriptor and never links photos on its own.

Both run on ONNX Runtime (GPU when available, else CPU). Inputs are BGR uint8.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.ai.models import ModelRegistry
from app.ai.runtime import Session, create_session
from app.quality.measure import FaceGeometry, align_face

ARCFACE_VERSION = "arcface-w600k-r50"
BODY_VERSION = "youtu-reid-2021nov"
BODY_SIZE = (128, 256)  # width, height
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)
MIN_BODY_PX = 32  # shorter side of a person crop below this carries too little


def _unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, np.float32).reshape(-1)
    return v / (float(np.linalg.norm(v)) or 1.0)


class ArcFaceEmbedder:
    def __init__(self, registry: ModelRegistry, *, prefer_gpu: bool = True) -> None:
        self.session: Session = create_session(registry.require("face_embedder_arcface"), prefer_gpu=prefer_gpu)
        self._input = self.session.session.get_inputs()[0].name

    def embed(self, bgr: np.ndarray, face: FaceGeometry) -> np.ndarray | None:
        aligned = align_face(bgr, face)
        if aligned is None:
            return None
        x = (cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB).astype(np.float32) - 127.5) / 127.5
        out = self.session.session.run(None, {self._input: np.ascontiguousarray(x.transpose(2, 0, 1)[None])})[0]
        return _unit(out)


class BodyEmbedder:
    def __init__(self, registry: ModelRegistry, *, prefer_gpu: bool = True) -> None:
        self.session: Session = create_session(registry.require("body_reid"), prefer_gpu=prefer_gpu)
        self._input = self.session.session.get_inputs()[0].name

    def embed(self, bgr: np.ndarray, nbox: tuple[float, float, float, float]) -> np.ndarray | None:
        """``nbox`` = person box normalised to 0..1."""
        h, w = bgr.shape[:2]
        x0, y0 = max(0, int(nbox[0] * w)), max(0, int(nbox[1] * h))
        x1, y1 = min(w, int(round((nbox[0] + nbox[2]) * w))), min(h, int(round((nbox[1] + nbox[3]) * h)))
        if min(x1 - x0, y1 - y0) < MIN_BODY_PX:
            return None
        crop = cv2.resize(bgr[y0:y1, x0:x1], BODY_SIZE, interpolation=cv2.INTER_AREA)
        x = (cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0 - _MEAN) / _STD
        out = self.session.session.run(None, {self._input: np.ascontiguousarray(x.transpose(2, 0, 1)[None])})[0]
        return _unit(out)
