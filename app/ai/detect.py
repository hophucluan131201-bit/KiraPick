"""Person / face detection and face embeddings on one photo.

All boxes are (x, y, w, h) in the pixel coordinates of the image passed in.
Images are numpy uint8 BGR arrays (OpenCV convention); use ``pil_to_bgr``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

from app.ai.models import ModelRegistry, ModelState
from app.ai.runtime import Session, create_session

Box = tuple[float, float, float, float]

PERSON_SCORE = 0.45
PERSON_NMS_IOU = 0.5
FACE_SCORE = 0.75
FACE_NMS_IOU = 0.3
MIN_FACE_PX = 24  # smaller faces carry too little identity information
# YuNet finds faces of ~10-300 px; two scales cover close-ups and group shots.
FACE_SCALES = (640, 1600)


def pil_to_bgr(image: Image.Image) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(image.convert("RGB"))[:, :, ::-1])


def iou(a: Box, b: Box) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


# ------------------------------------------------------------------ persons


class PersonDetector:
    """YOLOX (COCO) restricted to the 'person' class."""

    INPUT = 640
    STRIDES = (8, 16, 32)

    def __init__(self, session: Session) -> None:
        self.session = session
        self._input = session.session.get_inputs()[0].name
        grids, strides = [], []
        for s in self.STRIDES:
            n = self.INPUT // s
            yv, xv = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            strides.append(np.full((n * n, 1), s))
        self._grid = np.concatenate(grids).astype(np.float32)
        self._stride = np.concatenate(strides).astype(np.float32)

    @classmethod
    def load(cls, registry: ModelRegistry, *, prefer_gpu: bool = True) -> PersonDetector:
        session = create_session(registry.require("person_detector_s"), prefer_gpu=False)
        if prefer_gpu and registry.status("person_detector_m").state is ModelState.READY:  # optional (GPU builds)
            gpu = create_session(registry.require("person_detector_m"), prefer_gpu=True)
            if gpu.device == "cuda":
                session = gpu  # the larger model only when it really runs on the GPU
        return cls(session)

    @property
    def device(self) -> str:
        return self.session.device

    def detect(self, bgr: np.ndarray) -> list[tuple[Box, float]]:
        h, w = bgr.shape[:2]
        ratio = min(self.INPUT / h, self.INPUT / w)
        resized = cv2.resize(bgr, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.INPUT, self.INPUT, 3), 114, np.uint8)
        canvas[: resized.shape[0], : resized.shape[1]] = resized
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32)
        out = self.session.session.run(None, {self._input: blob})[0][0]
        xy = (out[:, :2] + self._grid) * self._stride
        wh = np.exp(out[:, 2:4]) * self._stride
        score = out[:, 4] * out[:, 5]  # objectness x P(person)
        keep = score >= PERSON_SCORE
        if not keep.any():
            return []
        xy, wh, score = xy[keep], wh[keep], score[keep]
        boxes = np.concatenate([xy - wh / 2, wh], 1) / ratio
        boxes[:, 0] = boxes[:, 0].clip(0, w)
        boxes[:, 1] = boxes[:, 1].clip(0, h)
        boxes[:, 2] = np.minimum(boxes[:, 2], w - boxes[:, 0])
        boxes[:, 3] = np.minimum(boxes[:, 3], h - boxes[:, 1])
        idx = cv2.dnn.NMSBoxes(boxes.tolist(), score.tolist(), PERSON_SCORE, PERSON_NMS_IOU)
        return [(tuple(map(float, boxes[i])), float(score[i])) for i in np.array(idx).reshape(-1)]


# -------------------------------------------------------------------- faces


@dataclass(slots=True)
class Face:
    box: Box
    score: float
    landmarks: np.ndarray  # 5x2: eyes, nose, mouth corners
    raw: np.ndarray  # YuNet row (15 values) in image coordinates, needed for alignment
    embedding: np.ndarray | None = None  # L2-normalised 128-d SFace vector


class FaceDetector:
    def __init__(self, registry: ModelRegistry) -> None:
        self._model = str(registry.require("face_detector"))
        self._detectors: dict[tuple[int, int], cv2.FaceDetectorYN] = {}

    def _detector(self, size: tuple[int, int]) -> cv2.FaceDetectorYN:
        det = self._detectors.get(size)
        if det is None:
            det = cv2.FaceDetectorYN.create(self._model, "", size, FACE_SCORE, FACE_NMS_IOU, 5000)
            self._detectors[size] = det
        return det

    def detect(self, bgr: np.ndarray) -> list[Face]:
        h, w = bgr.shape[:2]
        rows = []
        for long_side in FACE_SCALES:
            scale = min(1.0, long_side / max(h, w))
            img = bgr if scale == 1.0 else cv2.resize(bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
            _, found = self._detector((img.shape[1], img.shape[0])).detect(img)
            if found is not None:
                found = found.copy()
                found[:, :14] /= scale
                rows.extend(found)
            if scale == 1.0:
                break  # image already smaller than this scale: larger scales add nothing
        if not rows:
            return []
        arr = np.array(rows, dtype=np.float32)
        idx = np.array(cv2.dnn.NMSBoxes(arr[:, :4].tolist(), arr[:, 14].tolist(), FACE_SCORE, FACE_NMS_IOU)).reshape(-1)
        faces = []
        for i in idx:
            r = arr[i]
            if min(r[2], r[3]) < MIN_FACE_PX:
                continue
            faces.append(Face(tuple(map(float, r[:4])), float(r[14]), r[4:14].reshape(5, 2).copy(), r.copy()))
        return faces


class FaceEmbedder:
    def __init__(self, registry: ModelRegistry) -> None:
        self._rec = cv2.FaceRecognizerSF.create(str(registry.require("face_embedder")), "")

    def embed(self, bgr: np.ndarray, face: Face) -> np.ndarray:
        aligned = self._rec.alignCrop(bgr, face.raw)
        vec = self._rec.feature(aligned).reshape(-1).astype(np.float32)
        return vec / (np.linalg.norm(vec) or 1.0)


# ------------------------------------------------------------- per photo


@dataclass(slots=True)
class Detection:
    """One person in one photo (a subject occurrence before identity grouping)."""

    person_box: Box | None
    person_score: float | None
    face: Face | None
    extra: dict = field(default_factory=dict)


def associate(persons: list[tuple[Box, float]], faces: list[Face]) -> list[Detection]:
    """Attach each face to the person box that contains it best; leftovers stand alone."""
    detections = [Detection(box, score, None) for box, score in persons]
    for face in sorted(faces, key=lambda f: -f.score):
        fx, fy, fw, fh = face.box
        cx, cy = fx + fw / 2, fy + fh / 2
        best, best_area = None, None
        for det in detections:
            if det.face is not None or det.person_box is None:
                continue
            x, y, w, h = det.person_box
            # face centre inside the upper part of the body box
            if x <= cx <= x + w and y <= cy <= y + h * 0.6:
                area = w * h
                if best_area is None or area < best_area:  # tightest enclosing person
                    best, best_area = det, area
        if best is not None:
            best.face = face
        else:
            detections.append(Detection(None, None, face))
    return detections
