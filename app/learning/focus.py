"""Learned sharpness: where "nét căng / hơi soft / lệch nét" lie for one camera + lens.

The edge measurements of KiraPick are per pixel at 100 %, so a sharp photo from one camera and lens
can measure like a soft one from another (owner's Z5 + 24-70 f/2.8G: sharp eyes ~0.35-0.45, while the
fixed scale expected 0.5-0.8). The owner labels photos with Q / W / R; per camera + lens two small
weighted logistic regressions learn P(not sharp) and P(missed | not sharp) from the measurements.
Shown only when cross-validated accuracy is good enough; otherwise the reason is shown instead.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np

from app.learning.taste import _fit

LABELS = {"sharp": 0, "soft": 1, "missed": 2}
NAMES = {0: "nét căng", 1: "hơi soft", 2: "lệch nét / rung"}
KEYS = {"sharp": "Q", "soft": "W", "missed": "R"}
FEATURES = ("eye_sharp", "face_sharp", "body_sharp", "tech_iqa", "sharp_scale")
MIN_EACH = 8  # labelled photos needed for "sharp" and for "not sharp"
MIN_ACCURACY = 0.75


@dataclass(slots=True)
class FocusExample:
    label: int  # 0 sharp, 1 soft, 2 missed
    group: str  # shoot day (validation folds)
    camera: str
    features: dict[str, float | None]


def _x(features: dict[str, float | None], means: np.ndarray) -> np.ndarray:
    row = []
    for i, name in enumerate(FEATURES):
        v = features.get(name)
        row += [means[i] if v is None else float(v), 1.0 if v is None else 0.0]
    return np.array(row)


@dataclass(slots=True)
class FocusModel:
    means: np.ndarray
    mu: np.ndarray
    sd: np.ndarray
    w_not: np.ndarray
    b_not: float
    w_missed: np.ndarray | None
    b_missed: float
    n: int
    accuracy: float

    def _p(self, features: dict[str, float | None]) -> tuple[float, float, float]:
        x = (_x(features, self.means) - self.mu) / self.sd
        p_not = 1 / (1 + np.exp(-(x @ self.w_not + self.b_not)))
        p_m = 0.5 if self.w_missed is None else 1 / (1 + np.exp(-(x @ self.w_missed + self.b_missed)))
        return float(1 - p_not), float(p_not * (1 - p_m)), float(p_not * p_m)

    def score(self, features: dict[str, float | None]) -> float:
        """0..100: 100 = as sharp as the photos you called "nét căng"."""
        sharp, soft, _missed = self._p(features)
        return round(100 * sharp + 50 * soft, 1)

    def label(self, features: dict[str, float | None]) -> str:
        probs = self._p(features)
        return list(LABELS)[int(np.argmax(probs))]


@dataclass(slots=True)
class FocusStatus:
    ready: bool
    reason: str
    model: FocusModel | None = None


def _fit_model(ex: list[FocusExample]) -> FocusModel:
    means = np.array([np.mean([e.features[f] for e in ex if e.features.get(f) is not None] or [0.0]) for f in FEATURES])
    x = np.stack([_x(e.features, means) for e in ex])
    mu, sd = x.mean(axis=0), x.std(axis=0)
    sd[sd < 1e-6] = 1.0
    xs = (x - mu) / sd
    y_not = np.array([1.0 if e.label > 0 else 0.0 for e in ex])
    w_not, b_not = _fit(xs, y_not, np.ones(len(ex)))
    nots = y_not == 1
    w_m, b_m = None, 0.0
    if nots.sum() >= 4 and 0 < sum(e.label == 2 for e in ex) < nots.sum():
        y_m = np.array([1.0 if e.label == 2 else 0.0 for e in ex])[nots]
        w_m, b_m = _fit(xs[nots], y_m, np.ones(int(nots.sum())))
    return FocusModel(means, mu, sd, w_not, b_not, w_m, b_m, len(ex), 0.0)


def _train_one(ex: list[FocusExample]) -> FocusStatus:
    n_sharp = sum(e.label == 0 for e in ex)
    n_not = len(ex) - n_sharp
    if n_sharp < MIN_EACH or n_not < MIN_EACH:
        return FocusStatus(False, f"Chưa đủ: cần ít nhất {MIN_EACH} tấm nét căng (Q) và {MIN_EACH} tấm hơi soft / "
                                  f"lệch nét (W/R); đang có {n_sharp} và {n_not}")
    groups = sorted({e.group for e in ex})
    folds = {g: i % min(4, len(groups)) for i, g in enumerate(groups)} if len(groups) >= 2 else None
    idx = np.array([folds[e.group] for e in ex]) if folds else np.arange(len(ex)) % 4
    right = 0
    for f in np.unique(idx):
        train = [e for e, k in zip(ex, idx, strict=True) if k != f]
        test = [e for e, k in zip(ex, idx, strict=True) if k == f]
        if len({e.label > 0 for e in train}) < 2:
            continue
        m = _fit_model(train)
        right += sum((m.label(e.features) != "sharp") == (e.label > 0) for e in test)
    accuracy = right / len(ex)
    model = _fit_model(ex)
    model.accuracy = round(accuracy, 3)
    if accuracy < MIN_ACCURACY:
        return FocusStatus(False, f"Chưa khớp: số đo độ nét chưa tách được cách bạn chấm (đúng {accuracy:.0%})", model)
    return FocusStatus(True, f"Đã học từ {len(ex)} tấm, khớp {accuracy:.0%}", model)


def train_focus(examples: list[FocusExample]) -> dict[str, FocusStatus]:
    cameras: dict[str, list[FocusExample]] = {}
    for e in examples:
        cameras.setdefault(e.camera, []).append(e)
    return {cam: _train_one(ex) for cam, ex in cameras.items()}


def camera_key(make: str | None, model: str | None, lens: str | None) -> str:
    if model and make and not model.lower().startswith(make.split()[0].lower()):
        model = f"{make.split()[0].title()} {model}"  # "NIKON CORPORATION" + "NIKON Z 5" -> "NIKON Z 5"
    body = (model or make or "").strip() or "máy không rõ"
    return f"{body} + {lens}" if lens else body


def photo_focus(conn: sqlite3.Connection, asset_id: int) -> tuple[str, dict[str, float | None]] | None:
    """(camera key, measurements) of the photo's most prominent main person, or None if not measured."""
    import json

    row = conn.execute(
        """SELECT a.make, a.model, a.lens, m.values_json FROM measurements m
           JOIN occurrences o ON o.id = m.occurrence_id JOIN assets a ON a.id = m.asset_id
           WHERE m.asset_id = ? AND m.extractor = 'quality' AND o.is_main = 1
           ORDER BY o.prominence DESC LIMIT 1""", (asset_id,)).fetchone()
    if row is None:
        return None
    values = json.loads(row[3])
    return camera_key(row[0], row[1], row[2]), {f: values.get(f) for f in FEATURES}


# --- applied in scoring -------------------------------------------------------------------------
SESSION_MIN = 10  # photos of one camera (with the same measure) before the session reference is used
SESSION_TARGET = 0.70  # the 90th percentile of a camera's measures is lifted to this on the fixed scale
SESSION_MAX_FACTOR = 2.0  # never lift more than this (a session of only soft photos must not look sharp)
_SHARP_KEYS = ("eye_sharp", "face_sharp", "body_sharp")

_learned: dict[str, FocusStatus] = {}


def use_models(statuses: dict[str, FocusStatus]) -> None:
    """The app sets the newest trained models; scoring reads them (replaced whole, so thread-safe)."""
    global _learned
    _learned = dict(statuses)


def learned_models() -> dict[str, FocusStatus]:
    return _learned


def _kind(v: dict) -> str | None:
    return next((k for k in _SHARP_KEYS if v.get(k) is not None), None)


def focus_overrides(cameras: dict[int, tuple[str | None, str | None, str | None]],
                    values: dict[int, dict]) -> dict:
    """occurrence id -> FocusOverride: learned for its camera if ready, else relative to the project's sharpest."""
    from app.quality.score import FocusOverride

    keys = {occ: camera_key(*cam) for occ, cam in cameras.items()}
    measures: dict[tuple[str, str], list[float]] = {}
    for occ, v in values.items():
        k = _kind(v)
        if k is not None:
            measures.setdefault((keys[occ], k), []).append(float(v[k]))
    factors = {}
    for ck, vals in measures.items():
        if len(vals) >= SESSION_MIN:
            p90 = float(np.percentile(vals, 90))
            factors[ck] = min(SESSION_MAX_FACTOR, max(1.0, SESSION_TARGET / max(p90, 1e-6)))
    out = {}
    learned = _learned
    for occ, v in values.items():
        k = _kind(v)
        if k is None:
            continue
        status = learned.get(keys[occ])
        if status is not None and status.ready and status.model is not None:
            features = {f: v.get(f) for f in FEATURES}
            out[occ] = FocusOverride(status.model.score(features),
                                     f"chấm theo cách bạn dạy (Q/W/R) cho {keys[occ]}, khớp "
                                     f"{status.model.accuracy:.0%}", status.model.label(features) == "missed")
        elif factors.get((keys[occ], k), 1.0) > 1.05:
            factor = factors[(keys[occ], k)]
            times = f"{factor:.1f}".replace(".", ",")
            out[occ] = FocusOverride(None, f"so với các tấm nét nhất của {keys[occ]} trong buổi này (×{times}; "
                                           "dạy bằng Q/W/R để chính xác hơn)", factor=factor)
    return out
