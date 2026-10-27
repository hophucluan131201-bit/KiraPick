"""Per-user tuning of the grouping thresholds from that user's own corrections.

Each merge / "different" / remove / assign answer left pairs of photos with their
cue similarities in the learning store. Here the face and look thresholds of the
session's profile are shifted a little (stricter by at most ``MAX_SHIFT``, looser by at
most ``MAX_LOOSEN``) to agree better
with those answers. Safety rules, so a few clicks cannot make things worse:

- needs at least ``MIN_ANSWERS`` "same person" and ``MIN_ANSWERS`` "different"
  answers measured with the current models;
- a shift may never wrongly link more "different" pairs than the defaults do;
- it must also win in cross-validation (tuned on some answers, checked on the
  others), else the defaults stay.

Pair-level rules only (see app.identity.cluster.pair_link); a missed direct
link may still be joined through other photos, so this is a conservative proxy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.ai.identity_plus import ARCFACE_VERSION, BODY_VERSION
from app.identity.cluster import Thresholds
from app.identity.features import OUTFIT_VERSION
from app.learning.store import IdentityExample, LearningStore
from app.workers.analyze_job import FACE_VECTOR_VERSION

log = logging.getLogger(__name__)

STEP = 0.02
MAX_SHIFT = 0.06  # stricter than the defaults: up to this much
MAX_LOOSEN = 0.02  # looser: only this much (simulation: -0.06 joined other people on unseen photos)
MIN_ANSWERS = 2
FALSE_LINK_COST = 3.0  # wrongly joining two people is worse than missing one link
FOLDS = 5
_SHIFTS = np.round(np.arange(-MAX_LOOSEN, MAX_SHIFT + 1e-9, STEP), 4)


@dataclass(frozen=True, slots=True)
class Tuning:
    face: float = 0.0
    look: float = 0.0
    same_answers: int = 0
    different_answers: int = 0
    applied: bool = False
    reason: str = ""

    def apply(self, base: Thresholds) -> Thresholds:
        return base.shifted(self.face, self.look) if self.applied else base

    def describe(self) -> str:
        if not self.applied:
            return self.reason
        parts = []
        if self.face:
            parts.append(f"khuôn mặt {'dễ' if self.face < 0 else 'khó'} gộp hơn {abs(self.face):.2f}")
        if self.look:
            parts.append(f"trang phục {'dễ' if self.look < 0 else 'khó'} gộp hơn {abs(self.look):.2f}")
        return (f"Đã học từ {self.same_answers + self.different_answers} lần sửa của bạn: "
                + ", ".join(parts or ["giữ mặc định"]))


@dataclass(slots=True)
class _Data:
    answer: np.ndarray
    same: np.ndarray
    face: np.ndarray  # NaN = no face pair
    look: np.ndarray  # NaN = no look pair
    near: np.ndarray
    weight: np.ndarray  # 1 / pairs of its answer: each correction counts the same


def _arrays(examples: list[IdentityExample], base: Thresholds) -> _Data | None:
    arc = base.body_weight > 0
    rows = []
    for ex in examples:
        p, v = ex.pair, ex.versions
        if arc:
            face = p.face_arc if v.arc == ARCFACE_VERSION else None
            if face is None and p.face is not None:
                continue  # had faces, but not measured with this model: would pass for a face-less pair
        else:
            face = p.face if v.face == FACE_VECTOR_VERSION else None
        look = p.outfit if v.outfit == OUTFIT_VERSION else None
        if look is not None and arc and p.body is not None and v.body == BODY_VERSION:
            look = (1 - base.body_weight) * look + base.body_weight * p.body
        if face is None and look is None:
            continue
        rows.append((ex.answer, ex.same, np.nan if face is None else face, np.nan if look is None else look,
                     p.dt_s is not None and p.dt_s <= base.window_s))
    if not rows:
        return None
    answer = np.array([r[0] for r in rows])
    _, inverse, counts = np.unique(answer, return_inverse=True, return_counts=True)
    return _Data(answer, np.array([r[1] for r in rows]), np.array([r[2] for r in rows], float),
                 np.array([r[3] for r in rows], float), np.array([r[4] for r in rows]), 1.0 / counts[inverse])


def _linked(d: _Data, t: Thresholds, mask: np.ndarray) -> np.ndarray:
    """Vectorised app.identity.cluster.pair_link(...) is not None."""
    face, look, near = d.face[mask], d.look[mask], d.near[mask]
    with np.errstate(invalid="ignore"):
        no_face = np.isnan(face)
        face_link = (face >= t.face_strong) & (near | (face >= t.face_certain) | (look >= t.far_outfit))
        look_link = near & (look >= t.outfit_link) & (no_face | (face >= t.face_with_outfit))
        mid_link = near & (face >= t.face_mid) & (look >= t.outfit_mid)
    return face_link | look_link | mid_link


def _cost(d: _Data, t: Thresholds, mask: np.ndarray) -> tuple[float, float]:
    """(weighted cost, weighted wrong links on 'different' answers)."""
    linked = _linked(d, t, mask)
    same, w = d.same[mask], d.weight[mask]
    false = float((w * (linked & ~same)).sum())
    missed = float((w * (~linked & same)).sum())
    return FALSE_LINK_COST * false + missed, false


def _best(d: _Data, base: Thresholds, mask: np.ndarray) -> tuple[float, float]:
    base_cost, base_false = _cost(d, base, mask)
    best, best_key = (0.0, 0.0), (base_cost, 0.0)
    for f in _SHIFTS:
        for g in _SHIFTS:
            cost, false = _cost(d, base.shifted(float(f), float(g)), mask)
            if false > base_false + 1e-12:
                continue  # never contradict more "different" answers than the defaults
            key = (cost, abs(f) + abs(g))
            if key < best_key:
                best, best_key = (float(f), float(g)), key
    return best


def tune(examples: list[IdentityExample], base: Thresholds) -> Tuning:
    d = _arrays(examples, base)
    if d is None:
        return Tuning(reason="Chưa có lần sửa nào để học (dùng mức mặc định).")
    same_answers = len(np.unique(d.answer[d.same]))
    different_answers = len(np.unique(d.answer[~d.same]))
    counts = dict(same_answers=same_answers, different_answers=different_answers)
    if same_answers < MIN_ANSWERS or different_answers < MIN_ANSWERS:
        return Tuning(**counts, reason=f"Cần thêm lần sửa để bắt đầu học (đã có {same_answers} lần gộp, "
                                        f"{different_answers} lần tách; cần mỗi loại ít nhất {MIN_ANSWERS}).")
    everything = np.ones(len(d.same), bool)
    face, look = _best(d, base, everything)
    if face == 0 and look == 0:
        return Tuning(**counts, reason="Các lần sửa của bạn khớp với mức mặc định.")
    # Cross-validation by answer: tuned without some corrections, checked on them.
    answers = np.unique(d.answer)
    folds = np.arange(len(answers)) % min(FOLDS, len(answers))
    fold_of = dict(zip(answers.tolist(), folds.tolist()))
    fold = np.array([fold_of[a] for a in d.answer.tolist()])
    tuned_cost = default_cost = 0.0
    for k in np.unique(folds):
        train, test = fold != k, fold == k
        if not test.any() or not train.any():
            continue
        f, g = _best(d, base, train)
        tuned_cost += _cost(d, base.shifted(f, g), test)[0]
        default_cost += _cost(d, base, test)[0]
    if tuned_cost >= default_cost - 1e-9:
        return Tuning(**counts, reason="Kiểm tra chéo chưa thấy tốt hơn mặc định: giữ mức mặc định.")
    return Tuning(face, look, **counts, applied=True)


def tune_from_store(folder: Path | None, base: Thresholds) -> Tuning:
    """Tuning for ``base`` from the learning data in ``folder``; defaults on any problem."""
    if folder is None or not (folder / "learning.db").is_file():
        return Tuning(reason="Chưa có dữ liệu học.")
    try:
        store = LearningStore(folder)
        try:
            return tune(store.identity_examples(), base)
        finally:
            store.close()
    except Exception:  # noqa: BLE001 - learning is optional
        log.exception("could not read the learning data")
        return Tuning(reason="Không đọc được dữ liệu học: dùng mức mặc định.")
