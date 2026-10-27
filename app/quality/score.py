"""Rubric: measurements -> per-occurrence technical score (0..100) with a breakdown.

Recomputed from stored measurements in milliseconds, so the rubric can change
without re-reading photos. A criterion that could not be observed is N/A: its
weight is spread over the others and the confidence drops — never a fake 0.

Mappings are starting values checked on the owner's sample NEFs (sharp eyes
measured 0.5-0.8, a defocused background face 0.08, a 2 px Gaussian blur
~0.2); they are NOT calibrated against the owner's choices yet.
Not measured at all (no model yet): eyes closed, aesthetics/artistry.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

PROFILE_VERSION = "cosplay-tech-v1"
WEIGHTS = {"focus": 35, "face": 25, "exposure": 20, "framing": 20}
LABELS = {"focus": "nét", "face": "mặt", "exposure": "sáng", "framing": "bố cục"}
NOT_MEASURED = ("mắt nhắm/mở", "thẩm mỹ tổng thể")


@dataclass(slots=True)
class Score:
    total: float | None  # 0..100, None if nothing could be judged
    parts: dict[str, float | None]
    confidence: float  # share of the rubric weight that was observable
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.total is None:
            return "chưa chấm được"
        parts = " · ".join(f"{LABELS[k]} {v:.0f}" if v is not None else f"{LABELS[k]} —" for k, v in self.parts.items())
        return f"{self.total:.0f}/100 ({parts})"


def _ramp(x: float, lo: float, hi: float) -> float:
    """0 at lo, 100 at hi, clamped (lo > hi for 'lower is better')."""
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100.0))


def score(v: dict) -> Score:
    parts: dict[str, float | None] = dict.fromkeys(WEIGHTS)
    warnings: list[str] = []
    sharp = next((v.get(k) for k in ("eye_sharp", "face_sharp", "body_sharp") if v.get(k) is not None), None)
    if sharp is not None:
        parts["focus"] = _ramp(sharp, 0.15, 0.75)
        if sharp < 0.25:
            warnings.append("lệch nét / rung" if v.get("eye_sharp") is not None else "người không nét")
    fq = v.get("face_quality")
    if fq is not None:
        parts["face"] = _ramp(fq, 0.25, 0.75)
        if fq < 0.3:
            warnings.append("mặt khó thấy (che, nghiêng, mờ)")
    clip = v.get("face_clip") if v.get("face_clip") is not None else v.get("body_clip")
    luma = v.get("face_luma") if v.get("face_luma") is not None else v.get("body_luma")
    if clip is not None and luma is not None:
        clip_score = _ramp(clip, 0.20, 0.0)  # 0% clipped -> 100, >= 20% -> 0
        if luma < 25:  # low-key is allowed: only a gentle penalty
            luma_score = 50 + _ramp(luma, 5, 25) / 2
        elif luma > 85:
            luma_score = 30 + _ramp(luma, 97, 85) * 0.7
        else:
            luma_score = 100.0
        parts["exposure"] = clip_score * luma_score / 100
        if v.get("face_clip") is not None and clip > 0.10:
            warnings.append("mặt bị cháy sáng")
    if v.get("area") is not None:
        frame = 100.0
        if v.get("cut_head"):
            frame -= 50
            warnings.append("đầu chạm mép ảnh")
        if v.get("cut_side"):
            frame -= 15
        frame -= 20 * max(0.0, (v.get("offcentre") or 0) - 0.5)  # far off-centre
        if v["area"] < 0.05:
            frame -= 30  # subject is tiny in the frame
        parts["framing"] = max(0.0, frame)
    used = {k: w for k, w in WEIGHTS.items() if parts[k] is not None}
    if not used:
        return Score(None, parts, 0.0, warnings)
    total = sum(parts[k] * w for k, w in used.items()) / sum(used.values())  # type: ignore[operator]
    return Score(round(total, 1), {k: None if x is None else round(x, 1) for k, x in parts.items()},
                 round(sum(used.values()) / sum(WEIGHTS.values()), 2), warnings)


def occurrence_scores(conn: sqlite3.Connection) -> dict[int, Score]:
    return {r[0]: score(json.loads(r[1])) for r in conn.execute(
        "SELECT occurrence_id, values_json FROM measurements WHERE extractor = 'quality' AND occurrence_id IS NOT NULL")}


def photo_scores(conn: sqlite3.Connection, subject_id: int | None = None) -> dict[int, tuple[int, Score]]:
    """asset id -> (occurrence id, score) of that person, or of the photo's most prominent main person."""
    by_occ = occurrence_scores(conn)
    sql = "SELECT id, asset_id FROM occurrences WHERE is_main = 1"
    args: tuple = ()
    if subject_id is not None:
        sql = "SELECT id, asset_id FROM occurrences WHERE subject_id = ?"
        args = (subject_id,)
    out: dict[int, tuple[int, Score]] = {}
    for occ_id, asset_id in conn.execute(sql + " ORDER BY prominence DESC", args):
        if asset_id not in out and occ_id in by_occ:
            out[asset_id] = (occ_id, by_occ[occ_id])
    return out
