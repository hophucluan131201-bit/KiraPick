"""Per-occurrence features computed from one analysed photo.

- prominence: how much a person is "the subject" of the frame (size x centrality),
  relative to the most prominent person in the same photo; background passers-by
  get is_main = False and are not grouped into subjects.
- outfit: a colour histogram of the body below the head. It is a weak cue
  (same outfit != same person, and lighting changes colours), used only to
  *suggest* identity for photos without a usable face — never to auto-assign.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.ai.detect import Box, Detection

MAIN_RELATIVE = 0.4  # at least 40% of the most prominent person's score
MAIN_MIN_AREA = 0.02  # and at least 2% of the frame (or a usable face)
FACE_TO_BODY_AREA = 8.0  # a lone face stands for a body ~8x its area
OUTFIT_BINS = (16, 4, 2)  # hue, saturation, value
OUTFIT_VERSION = "hsv16x4x2-v1"
CROP_SIZE = 160


@dataclass(slots=True)
class OccurrenceFeatures:
    person_box: Box | None  # normalised 0..1
    person_score: float | None
    face_box: Box | None  # normalised
    face_score: float | None
    face_vector: np.ndarray | None
    outfit_vector: np.ndarray | None
    prominence: float
    is_main: bool
    crop: np.ndarray | None  # BGR avatar


def _norm(box: Box, w: int, h: int) -> Box:
    return (box[0] / w, box[1] / h, box[2] / w, box[3] / h)


def _raw_prominence(nbox: Box) -> float:
    x, y, bw, bh = nbox
    area = bw * bh
    cx, cy = x + bw / 2, y + bh / 2
    off_centre = min(1.0, ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5 / 0.7071)
    return area * (1.0 - 0.5 * off_centre)


def outfit_descriptor(bgr: np.ndarray, box: Box) -> np.ndarray | None:
    """Hellinger-normalised HSV histogram of the body below the head."""
    x, y, w, h = (int(round(v)) for v in box)
    top = y + int(h * 0.25)
    region = bgr[max(0, top): max(0, y + h), max(0, x): max(0, x + w)]
    if region.size == 0 or region.shape[0] < 8 or region.shape[1] < 8:
        return None
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, list(OUTFIT_BINS), [0, 180, 0, 256, 0, 256]).reshape(-1)
    total = float(hist.sum())
    if total <= 0:
        return None
    vec = np.sqrt(hist / total).astype(np.float32)
    return vec / (np.linalg.norm(vec) or 1.0)


def avatar_crop(bgr: np.ndarray, det: Detection) -> np.ndarray | None:
    h, w = bgr.shape[:2]
    if det.face is not None:
        fx, fy, fw, fh = det.face.box
        side = max(fw, fh) * 1.8
        cx, cy = fx + fw / 2, fy + fh / 2
    elif det.person_box is not None:
        px, py, pw, ph = det.person_box
        side = min(pw, ph * 0.5)
        cx, cy = px + pw / 2, py + side / 2
    else:
        return None
    x0, y0 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    x1, y1 = int(min(w, cx + side / 2)), int(min(h, cy + side / 2))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return cv2.resize(bgr[y0:y1, x0:x1], (CROP_SIZE, CROP_SIZE), interpolation=cv2.INTER_AREA)


def features_for(bgr: np.ndarray, detections: list[Detection], usable_face_score: float) -> list[OccurrenceFeatures]:
    h, w = bgr.shape[:2]
    raw: list[float] = []
    for det in detections:
        if det.person_box is not None:
            raw.append(_raw_prominence(_norm(det.person_box, w, h)))
        else:
            fx, fy, fw, fh = _norm(det.face.box, w, h)  # type: ignore[union-attr]
            k = FACE_TO_BODY_AREA ** 0.5
            raw.append(_raw_prominence((fx, fy, fw * k, fh * k)))
    top = max(raw, default=0.0) or 1.0
    out = []
    for det, score in zip(detections, raw):
        rel = score / top
        nbox = _norm(det.person_box, w, h) if det.person_box is not None else None
        face = det.face
        usable_face = face is not None and face.embedding is not None and face.score >= usable_face_score
        area = nbox[2] * nbox[3] if nbox else 0.0
        is_main = rel >= MAIN_RELATIVE and (area >= MAIN_MIN_AREA or usable_face)
        out.append(OccurrenceFeatures(
            person_box=nbox,
            person_score=det.person_score,
            face_box=_norm(face.box, w, h) if face is not None else None,
            face_score=face.score if face is not None else None,
            face_vector=face.embedding if usable_face else None,
            outfit_vector=outfit_descriptor(bgr, det.person_box) if det.person_box is not None else None,
            prominence=round(rel, 4),
            is_main=is_main,
            crop=avatar_crop(bgr, det),
        ))
    return out
