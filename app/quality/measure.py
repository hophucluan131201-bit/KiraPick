"""Technical measurements of one subject occurrence. Pure functions on pixels.

Everything here is *measured*, never guessed: when a value cannot be observed
(no face, flat region, crop too small) it is ``None`` and the scoring treats it
as not available instead of zero.

- Sharpness is measured on the **full-resolution** image (the camera's full-size
  embedded JPEG or a full demosaic), around the eyes when a face is visible,
  otherwise in the middle of the person. Metric: steepest edges relative to the
  local contrast, ~1.0 = edge in one pixel, 0.25 = edge spread over ~4 pixels.
- Face quality: eDifFIQA(T) (face image quality: blur, pose, occlusion, light).
- Exposure: face brightness and clipped highlights on the face; clipped and
  crushed areas on the person. Dark backgrounds (low-key) are not judged.
- Framing: subject size, position and cut-offs from the boxes.
- Layout: a gradient-orientation descriptor of the person's silhouette, used
  only to tell poses/framings apart when selecting diverse photos.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.ai.detect import Box

QUALITY_VERSION = "q2"  # q2: + eyes (blink_left/right, ear_left/right, blink)
LAYOUT_VERSION = "hog32x64-v1"
EDGE_PERCENTILE = 99.5
MIN_CONTRAST = 12.0  # grey levels; flatter regions cannot show focus
CLIP_LEVEL = 250
# ArcFace / SFace 5-point reference for a 112x112 aligned face (eyes, nose, mouth corners).
FACE_REFERENCE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                           [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)
_HOG = cv2.HOGDescriptor((32, 64), (16, 16), (8, 8), (8, 8), 9)


@dataclass(slots=True)
class FaceGeometry:
    box: Box  # full-resolution pixels
    landmarks: np.ndarray  # 5x2 full-resolution pixels: right eye, left eye, nose, mouth corners
    score: float


def edge_sharpness(gray: np.ndarray) -> float | None:
    """Steepest edges / local contrast of a grey region at native resolution (0..~1)."""
    if gray.ndim != 2 or min(gray.shape) < 16:
        return None
    g = gray.astype(np.float32)
    lo, hi = np.percentile(g, [2, 98])
    contrast = float(hi - lo)
    if contrast < MIN_CONTRAST:
        return None
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    steep = float(np.percentile(cv2.magnitude(gx, gy), EDGE_PERCENTILE))
    return round(min(1.5, steep / (4.0 * contrast)), 4)  # a 3x3 Sobel answers 4x the step height


def _clip_box(x0: float, y0: float, x1: float, y1: float, w: int, h: int) -> tuple[int, int, int, int] | None:
    a, b, c, d = max(0, int(x0)), max(0, int(y0)), min(w, int(round(x1))), min(h, int(round(y1)))
    return (a, b, c, d) if c - a >= 8 and d - b >= 8 else None


def eye_region(face: FaceGeometry, w: int, h: int) -> tuple[int, int, int, int] | None:
    (rx, ry), (lx, ly) = face.landmarks[0], face.landmarks[1]
    dist = float(np.hypot(lx - rx, ly - ry))
    if dist < 8:
        return None
    return _clip_box(min(rx, lx) - 0.45 * dist, min(ry, ly) - 0.35 * dist,
                     max(rx, lx) + 0.45 * dist, max(ry, ly) + 0.35 * dist, w, h)


def align_face(bgr: np.ndarray, face: FaceGeometry) -> np.ndarray | None:
    m, _ = cv2.estimateAffinePartial2D(face.landmarks.astype(np.float32), FACE_REFERENCE, method=cv2.LMEDS)
    return None if m is None else cv2.warpAffine(bgr, m, (112, 112))


def luminance(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32) * (100.0 / 255.0)


def exposure(region: np.ndarray) -> dict[str, float]:
    lum = luminance(region)
    return {
        "luma": round(float(np.median(lum)), 2),
        "clip": round(float(np.mean(region.max(axis=2) >= CLIP_LEVEL)), 4),
        "dark": round(float(np.mean(lum < 4.0)), 4),
    }


def framing(person: Box | None, face: Box | None) -> dict[str, float | None]:
    """From normalised boxes (0..1 of the frame)."""
    out: dict[str, float | None] = {"area": None, "offcentre": None, "cut_side": None, "cut_head": None,
                                    "face_height": None}
    if person is not None:
        x, y, w, h = person
        out["area"] = round(w * h, 4)
        out["offcentre"] = round(abs(x + w / 2 - 0.5) * 2, 4)
        out["cut_side"] = float(x <= 0.003 or x + w >= 0.997)
    if face is not None:
        out["face_height"] = round(face[3], 4)
        out["cut_head"] = float(face[1] <= 0.005)  # forehead touches the top edge
    return out


def layout_descriptor(bgr: np.ndarray, person: Box | None) -> np.ndarray | None:
    """HOG of the person's box (1:2 canvas), plus where/how big the person is in the frame."""
    if person is None:
        return None
    h, w = bgr.shape[:2]
    x, y, bw, bh = person[0] * w, person[1] * h, person[2] * w, person[3] * h
    box = _clip_box(x, y, x + bw, y + bh, w, h)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    gray = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    ch, cw = gray.shape
    side_w = max(cw, (ch + 1) // 2)
    canvas = np.zeros((side_w * 2, side_w), np.uint8)
    oy, ox = (side_w * 2 - ch) // 2, (side_w - cw) // 2
    canvas[oy:oy + ch, ox:ox + cw] = gray
    hog = _HOG.compute(cv2.resize(canvas, (32, 64), interpolation=cv2.INTER_AREA)).reshape(-1)
    hog = hog / (np.linalg.norm(hog) or 1.0)
    place = np.array([person[0] + person[2] / 2, person[1] + person[3] / 2, person[2], person[3]], np.float32)
    vec = np.concatenate([hog * 0.9, place * 0.5]).astype(np.float32)
    return vec / (np.linalg.norm(vec) or 1.0)
