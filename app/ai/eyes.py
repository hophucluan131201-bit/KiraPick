"""Eyes open/closed with MediaPipe Face Landmarker (Apache-2.0), run through ONNX Runtime.

Two small models converted from Google's ``face_landmarker.task`` (v1, float16):
- face landmarks v2: 478 3-D points of a 256x256 face crop (with irises);
- face blendshapes: 52 expression scores from 146 of those points, among them
  ``eyeBlinkLeft`` / ``eyeBlinkRight`` (0 = open, 1 = closed).

The crop follows MediaPipe's own region of interest: square, 1.5x the face box,
rotated so the eyes are level, then refined once from the first landmarks. The
face box and eye positions come from YuNet on the full-resolution photo.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from app.ai.models import ModelRegistry
from app.ai.runtime import create_session
from app.quality.measure import FaceGeometry

INPUT = 256
ROI_SCALE = 1.5
EYE_BLINK = (9, 10)  # eyeBlinkLeft, eyeBlinkRight in the 52 blendshapes (MediaPipe order)
# Subset of the 478 landmarks fed to the blendshapes model (face_blendshapes_graph.cc, kLandmarksSubsetIdxs).
BLENDSHAPE_POINTS = np.array([
    0, 1, 4, 5, 6, 7, 8, 10, 13, 14, 17, 21, 33, 37, 39, 40, 46, 52, 53, 54, 55, 58, 61, 63, 65, 66, 67, 70, 78,
    80, 81, 82, 84, 87, 88, 91, 93, 95, 103, 105, 107, 109, 127, 132, 133, 136, 144, 145, 146, 148, 149, 150, 152,
    153, 154, 155, 157, 158, 159, 160, 161, 162, 163, 168, 172, 173, 176, 178, 181, 185, 191, 195, 197, 234, 246,
    249, 251, 263, 267, 269, 270, 276, 282, 283, 284, 285, 288, 291, 293, 295, 296, 297, 300, 308, 310, 311, 312,
    314, 317, 318, 321, 323, 324, 332, 334, 336, 338, 356, 361, 362, 365, 373, 374, 375, 377, 378, 379, 380, 381,
    382, 384, 385, 386, 387, 388, 389, 390, 397, 398, 400, 402, 405, 409, 415, 454, 466, 468, 469, 470, 471, 472,
    473, 474, 475, 476, 477])
# Eye aspect ratio points (upper/lower lid, corners) of each eye in the 478-point mesh.
_EAR = {"right": (159, 145, 33, 133), "left": (386, 374, 362, 263)}


class EyeState:
    """Measures how closed each eye is. Raises ModelUnavailableError if the models are missing."""

    def __init__(self, registry: ModelRegistry) -> None:
        self._mesh = create_session(registry.require("face_mesh"), prefer_gpu=False).session
        self._shapes = create_session(registry.require("face_blendshapes"), prefer_gpu=False).session
        self._mesh_in = self._mesh.get_inputs()[0].name
        self._shapes_in = self._shapes.get_inputs()[0].name

    def _landmarks(self, full: np.ndarray, centre: tuple[float, float], size: float,
                   angle: float) -> tuple[np.ndarray, float]:
        """478x3 points in full-image pixels, and face presence 0..1, for one square crop."""
        k = INPUT / size
        m = cv2.getRotationMatrix2D(centre, math.degrees(angle), k)
        m[:, 2] += (INPUT / 2 - centre[0], INPUT / 2 - centre[1])
        crop = cv2.warpAffine(full, m, (INPUT, INPUT), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_CONSTANT)
        blob = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32)[None] / 255.0
        outs = self._mesh.run(None, {self._mesh_in: blob})
        points = next(o for o in outs if o.size == 478 * 3).reshape(478, 3)
        logit = float(next(o for o in outs if o.shape == (1, 1, 1, 1)).reshape(-1)[0])
        inv = cv2.invertAffineTransform(m)
        xy = points[:, :2] @ inv[:, :2].T + inv[:, 2]
        return np.c_[xy, points[:, 2] / k], 1.0 / (1.0 + math.exp(-logit))

    def measure(self, full: np.ndarray, face: FaceGeometry) -> dict[str, float] | None:
        (rx, ry), (lx, ly) = face.landmarks[0], face.landmarks[1]
        angle = math.atan2(ly - ry, lx - rx)  # rotate so that the eyes are level
        x, y, w, h = face.box
        points, presence = self._landmarks(full, (x + w / 2, y + h / 2), max(w, h) * ROI_SCALE, angle)
        if presence < 0.5:
            return None
        # One refinement, as MediaPipe tracking does: the crop around the first landmarks.
        lo, hi = points[:, :2].min(axis=0), points[:, :2].max(axis=0)
        points, presence = self._landmarks(full, tuple((lo + hi) / 2), float(max(hi - lo)) * ROI_SCALE, angle)
        if presence < 0.5:
            return None
        shapes = self._shapes.run(None, {self._shapes_in: points[BLENDSHAPE_POINTS, :2][None].astype(np.float32)})[0]
        shapes = shapes.reshape(-1)
        out = {"face_presence": round(presence, 3),
               "blink_left": round(float(shapes[EYE_BLINK[0]]), 3),
               "blink_right": round(float(shapes[EYE_BLINK[1]]), 3)}
        for side, (top, bottom, a, b) in _EAR.items():
            width = float(np.linalg.norm(points[a, :2] - points[b, :2]))
            out[f"ear_{side}"] = round(float(np.linalg.norm(points[top, :2] - points[bottom, :2])) / width, 3) if width else 0.0
        return out
