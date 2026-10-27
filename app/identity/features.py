"""Per-occurrence features computed from one analysed photo.

- prominence: how much a person is "the subject" of the frame (size x centrality),
  relative to the most prominent person in the same photo; background passers-by
  get is_main = False and are not grouped into subjects.
- outfit: colour histograms of three bands of the person (hair/head, upper body,
  lower body), taken from the central 60% of the box width so the background
  beside the person counts little. Computed on a 400 px image (the size of the
  cached thumbnails, so it can be recomputed without the models). It is a weak
  cue: same outfit != same person, and lighting changes colours; grouping only
  uses it together with time and face (see app/identity/cluster.py).
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
OUTFIT_VERSION = "hsv16x4x2-centre3-v2"
OUTFIT_LONG_SIDE = 400  # = thumbnail size
OUTFIT_BANDS = ((0.0, 0.25), (0.25, 0.6), (0.6, 1.0))  # head/hair, upper body, lower body
OUTFIT_STRIP = (0.2, 0.8)  # central part of the box width
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


def _hist(region: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, list(OUTFIT_BINS), [0, 180, 0, 256, 0, 256]).reshape(-1)
    vec = np.sqrt(hist / max(float(hist.sum()), 1.0))
    return vec / (np.linalg.norm(vec) or 1.0)


def outfit_image(bgr: np.ndarray) -> np.ndarray:
    """The photo at the outfit working size (no upscaling)."""
    h, w = bgr.shape[:2]
    scale = OUTFIT_LONG_SIDE / max(h, w)
    if scale >= 1:
        return bgr
    return cv2.resize(bgr, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)


def outfit_descriptor(small: np.ndarray, nbox: Box) -> np.ndarray | None:
    """Hellinger-normalised banded HSV histograms; ``nbox`` is normalised, ``small`` from outfit_image()."""
    h, w = small.shape[:2]
    x, y, bw, bh = nbox[0] * w, nbox[1] * h, nbox[2] * w, nbox[3] * h
    x0, x1 = max(0, int(x + bw * OUTFIT_STRIP[0])), min(w, int(x + bw * OUTFIT_STRIP[1]))
    parts = []
    for a, b in OUTFIT_BANDS:
        y0, y1 = max(0, int(y + bh * a)), min(h, int(y + bh * b))
        if y1 - y0 < 2 or x1 - x0 < 2:
            return None
        parts.append(_hist(small[y0:y1, x0:x1]))
    vec = np.concatenate(parts).astype(np.float32)
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
    small = outfit_image(bgr)
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
            outfit_vector=outfit_descriptor(small, nbox) if nbox is not None else None,
            prominence=round(rel, 4),
            is_main=is_main,
            crop=avatar_crop(bgr, det),
        ))
    return out
