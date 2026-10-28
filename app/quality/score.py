"""Rubric: measurements -> per-occurrence technical score (0..100) with a breakdown.

Recomputed from stored measurements in milliseconds, so the rubric can change
without re-reading photos. A criterion that could not be observed is N/A: its
weight is spread over the others and the confidence drops — never a fake 0.

Mappings are starting values checked on the owner's sample NEFs (sharp eyes
measured 0.5-0.8, a defocused background face 0.08, a 2 px Gaussian blur
~0.2); they are NOT calibrated against the owner's choices yet.
Eyes: MediaPipe eyeBlink (0 open .. 1 closed); on the owner's shoot open eyes measured ~0.06 and
every face >= 0.5 had closed or downcast eyes. Closed eyes are not scored 0: they can be intended.
Aesthetics (beta): TOPIQ trained on AVA contest ratings (general photography, not cosplay), only a
small hint: weight 10. On the owner's shoot the 1..10 score spanned 4.3-5.1 (p5-p95), so it is
stretched 4.2 -> 0 .. 5.2 -> 100.
2.2: the aesthetic part is the mean of TOPIQ and LAION (CLIP ViT-L/14 head, 1..10; on 8 of the owner's
NEFs LAION spanned 4.97-6.02, so 4.8 -> 0 .. 6.2 -> 100 — only 8 photos: re-check on a full shoot). TOPIQ technical quality (KonIQ, 0..1)
takes 20 % of the focus part, TOPIQ face quality (CGFIQA, 0..1) half of the face part.
2.3: the edge measure depends on camera + lens, so the focus part can be overridden (app.learning.focus):
by what the user taught with Q / W / R for that camera, or else relative to the sharpest photos of the
same camera in the project.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

PROFILE_VERSION = "cosplay-tech-v5"
WEIGHTS = {"focus": 30, "eyes": 20, "face": 20, "exposure": 15, "framing": 15, "aesthetic": 10}
LABELS = {"focus": "độ nét", "eyes": "mắt mở", "face": "mặt", "exposure": "sáng", "framing": "bố cục",
          "aesthetic": "thẩm mỹ"}
NOT_MEASURED: tuple[str, ...] = ()
AESTHETIC_LOW, AESTHETIC_HIGH = 4.2, 5.2  # TOPIQ mean score (1..10) mapped to 0..100
LAION_LOW, LAION_HIGH = 4.8, 6.2  # LAION (1..10) -> 0..100; 8 owner NEFs spanned 4.97-6.02
IQA_LOW, IQA_HIGH = 0.3, 0.8  # TOPIQ technical / face quality (0..1) mapped to 0..100
TECH_IN_FOCUS = 0.2  # share of the focus part taken by the technical-quality model
FACE_IQA_IN_FACE = 0.5
BLINK_OPEN, BLINK_CLOSED = 0.30, 0.50  # MediaPipe eyeBlink: below = open, at/above = closed or looking down
GOOD, POOR = 75.0, 45.0  # a criterion at/above GOOD is a strength, at/below POOR a weakness


@dataclass(slots=True)
class Score:
    total: float | None  # 0..100, None if nothing could be judged
    parts: dict[str, float | None]
    confidence: float  # share of the rubric weight that was observable
    warnings: list[str] = field(default_factory=list)  # serious problems (also listed in weaknesses)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    not_rated: list[str] = field(default_factory=list)  # criteria that could not be judged, with why
    reasons: dict[str, str] = field(default_factory=dict)  # one plain sentence per criterion
    aesthetic_detail: str = ""  # "TOPIQ 5,0 · LAION 6,1"
    tags: list[str] = field(default_factory=list)  # CLIP style tags (ids)

    def summary(self) -> str:
        if self.total is None:
            return "chưa chấm được"
        parts = " · ".join(f"{LABELS[k]} {v:.0f}" if v is not None else f"{LABELS[k]} —" for k, v in self.parts.items())
        return f"{self.total:.0f}/100 ({parts})"


@dataclass(frozen=True, slots=True)
class FocusOverride:
    """Focus judged for this camera + lens instead of on the fixed scale."""
    part: float | None  # 0..100 replacing the focus part (tech quality already included), None = keep it
    reason: str  # how it was judged, shown in the explanation
    missed: bool = False  # judged "lệch nét / rung"
    factor: float = 1.0  # session-relative: the measure is multiplied by this before the fixed scale


def _ramp(x: float, lo: float, hi: float) -> float:
    """0 at lo, 100 at hi, clamped (lo > hi for 'lower is better')."""
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100.0))


def score(v: dict, focus: FocusOverride | None = None) -> Score:
    parts: dict[str, float | None] = dict.fromkeys(WEIGHTS)
    warnings: list[str] = []
    sharp = next((v.get(k) for k in ("eye_sharp", "face_sharp", "body_sharp") if v.get(k) is not None), None)
    blur_warning = "lệch nét / rung" if v.get("eye_sharp") is not None else "người không nét"
    if sharp is not None and focus is not None and focus.part is not None:  # learned for this camera
        parts["focus"] = focus.part
        if focus.missed:
            warnings.append(blur_warning)
    elif sharp is not None:
        sharp *= focus.factor if focus is not None else 1.0
        parts["focus"] = _ramp(sharp, 0.15, 0.75)
        if sharp < 0.25:
            warnings.append(blur_warning)
        if v.get("tech_iqa") is not None:
            parts["focus"] = ((1 - TECH_IN_FOCUS) * parts["focus"]
                              + TECH_IN_FOCUS * _ramp(v["tech_iqa"], IQA_LOW, IQA_HIGH))
    beauty = []
    detail = []
    if v.get("aesthetic_mos") is not None:
        beauty.append(_ramp(v["aesthetic_mos"], AESTHETIC_LOW, AESTHETIC_HIGH))
        detail.append(f"TOPIQ {v['aesthetic_mos']:.1f}".replace(".", ","))
    if v.get("laion_mos") is not None:
        beauty.append(_ramp(v["laion_mos"], LAION_LOW, LAION_HIGH))
        detail.append(f"LAION {v['laion_mos']:.1f}".replace(".", ","))
    if beauty:
        parts["aesthetic"] = sum(beauty) / len(beauty)
    blink = v.get("blink")
    if blink is not None:
        if blink < BLINK_OPEN:
            parts["eyes"] = 100.0
        elif blink < BLINK_CLOSED:
            parts["eyes"] = 100.0 - (blink - BLINK_OPEN) / (BLINK_CLOSED - BLINK_OPEN) * 60.0  # 100 -> 40
        else:
            parts["eyes"] = 15.0  # closed: a weakness, but may be intended, so never 0
            warnings.append("mắt nhắm hoặc nhìn xuống (nếu cố ý thì bỏ qua)")
    fq = v.get("face_quality")
    fiqa = v.get("face_iqa")
    if fq is not None or fiqa is not None:
        face_parts = []
        if fq is not None:
            face_parts.append((1 - FACE_IQA_IN_FACE if fiqa is not None else 1.0, _ramp(fq, 0.25, 0.75)))
        if fiqa is not None:
            face_parts.append((FACE_IQA_IN_FACE if fq is not None else 1.0, _ramp(fiqa, IQA_LOW, IQA_HIGH)))
        parts["face"] = sum(w * x for w, x in face_parts)
        if fq is not None and fq < 0.3:
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
    strengths, weaknesses, not_rated = _explain(v, parts, warnings)
    reasons = _reasons(v, parts, " · ".join(detail))
    if focus is not None and sharp is not None:
        reasons["focus"] += f"; {focus.reason}"
    extra = {"reasons": reasons, "aesthetic_detail": " · ".join(detail),
             "tags": [t[0] for t in v.get("style_tags") or []]}
    used = {k: w for k, w in WEIGHTS.items() if parts[k] is not None}
    if not used:
        return Score(None, parts, 0.0, warnings, strengths, weaknesses, not_rated, **extra)
    total = sum(parts[k] * w for k, w in used.items()) / sum(used.values())  # type: ignore[operator]
    return Score(round(total, 1), {k: None if x is None else round(x, 1) for k, x in parts.items()},
                 round(sum(used.values()) / sum(WEIGHTS.values()), 2), warnings, strengths, weaknesses, not_rated,
                 **extra)


def _level(x: float, good: str, mid: str, poor: str) -> str:
    return good if x >= GOOD else (mid if x > POOR else poor)


def _reasons(v: dict, parts: dict[str, float | None], aesthetic_detail: str) -> dict[str, str]:
    """One short sentence per criterion, saying what was measured (or why it could not be)."""
    out: dict[str, str] = {}
    eyes_measured = v.get("eye_sharp") is not None
    f = parts["focus"]
    if f is None:
        out["focus"] = "chưa chấm – vùng đo quá nhỏ hoặc quá phẳng"
    else:
        where = "ở mắt (đo trên ảnh gốc)" if eyes_measured else "ở người (đo trên ảnh gốc)"
        out["focus"] = _level(f, f"nét {where}", f"hơi mềm {where}", f"thiếu nét {where}")
        if v.get("tech_iqa") is not None:
            out["focus"] += f"; chất lượng ảnh (AI) {v['tech_iqa'] * 100:.0f}/100"
    e = parts["eyes"]
    out["eyes"] = ("chưa chấm – không thấy rõ mắt" if e is None else
                   "mở" if e >= 100 else "hơi khép / lim dim" if e > 15 else "nhắm hoặc nhìn xuống (có thể cố ý)")
    fc = parts["face"]
    out["face"] = ("chưa chấm – không thấy rõ mặt" if fc is None else
                   _level(fc, "rõ, dễ nhìn", "hơi nghiêng, che hoặc mềm", "khó thấy (che, nghiêng, mờ)"))
    x = parts["exposure"]
    luma = v.get("face_luma") if v.get("face_luma") is not None else v.get("body_luma")
    if x is None:
        out["exposure"] = "chưa chấm – không đo được vùng người"
    elif x >= GOOD:
        out["exposure"] = "sáng tốt" + (", mặt không cháy" if v.get("face_luma") is not None else "")
    elif luma is not None and luma < 25:
        out["exposure"] = "tối (nếu low-key có chủ ý thì bỏ qua)"
    elif luma is not None and luma > 85:
        out["exposure"] = "hơi sáng quá"
    else:
        out["exposure"] = "có vùng cháy sáng"
    fr = parts["framing"]
    if fr is None:
        out["framing"] = "chưa chấm – không thấy người"
    else:
        issues = [t for cond, t in ((v.get("cut_head"), "đầu chạm mép"), (v.get("cut_side"), "bị cắt ở mép"),
                                    ((v.get("area") or 1) < 0.05, "người quá nhỏ"),
                                    ((v.get("offcentre") or 0) > 0.8, "sát mép khung")) if cond]
        out["framing"] = ", ".join(issues) if issues else "gọn, đủ người"
    out["aesthetic"] = aesthetic_detail or "chưa chấm – chưa có mô hình thẩm mỹ"
    return out


def _explain(v: dict, parts: dict[str, float | None], warnings: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Plain-language strengths / weaknesses / not judged, each backed by a measurement."""
    good: list[str] = []
    bad: list[str] = list(warnings)
    todo: list[str] = []
    eyes = v.get("eye_sharp") is not None  # focus was measured at the eyes
    focus, face, light, frame = parts["focus"], parts["face"], parts["exposure"], parts["framing"]
    lids = parts["eyes"]
    if lids is None:
        todo.append("mắt nhắm/mở (không thấy rõ mắt)")
    elif lids >= 100.0:
        good.append("mắt mở")
    elif lids > 15.0:
        bad.append("mắt hơi khép / lim dim")
    if focus is None:
        todo.append("độ nét (vùng đo quá nhỏ hoặc quá phẳng)")
    elif focus >= GOOD:
        good.append("nét ở mắt" if eyes else "người nét")
    elif focus > POOR:
        bad.append("nét chưa tới, hơi mềm" + (" ở mắt" if eyes else ""))
    elif not any(w in bad for w in ("lệch nét / rung", "người không nét")):
        bad.append("thiếu nét")
    if face is None:
        todo.append("khuôn mặt (không thấy rõ mặt" + (")" if v.get("face_sharp") is not None
                                                       else " hoặc chưa có mô hình chấm mặt)"))
    elif face >= GOOD:
        good.append("mặt rõ, dễ nhìn")
    elif face > POOR:
        bad.append("mặt chưa rõ lắm (hơi nghiêng, che hoặc mềm)")
    elif "mặt khó thấy (che, nghiêng, mờ)" not in bad:
        bad.append("mặt khó thấy (che, nghiêng, mờ)")
    luma = v.get("face_luma") if v.get("face_luma") is not None else v.get("body_luma")
    if light is None:
        todo.append("ánh sáng")
    elif light >= GOOD:
        good.append("sáng tốt, mặt không cháy" if v.get("face_luma") is not None else "sáng tốt")
    else:
        if luma is not None and luma < 25:
            bad.append("tối (nếu chụp low-key có chủ ý thì bỏ qua)")
        elif luma is not None and luma > 85:
            bad.append("hơi sáng quá")
        elif "mặt bị cháy sáng" not in bad:
            bad.append("có vùng cháy sáng trên người")
    if frame is None:
        todo.append("bố cục")
    else:
        if v.get("cut_side"):
            bad.append("người bị cắt ở mép ảnh")
        if (v.get("area") or 1) < 0.05:
            bad.append("người quá nhỏ trong khung")
        if (v.get("offcentre") or 0) > 0.8:
            bad.append("người nằm sát mép khung")
        if frame >= GOOD and not v.get("cut_head"):
            good.append("bố cục gọn, đủ người")
    beauty = parts["aesthetic"]
    if beauty is None:
        todo.append("thẩm mỹ tổng thể (chưa có mô hình)")
    elif beauty >= GOOD:
        good.append("gợi ý thẩm mỹ cao (AI tham khảo, học từ ảnh thi chung)")
    elif beauty <= POOR:
        bad.append("gợi ý thẩm mỹ thấp (AI tham khảo, học từ ảnh thi chung)")
    todo += [f"{name} (chưa có mô hình)" for name in NOT_MEASURED]
    return good, bad, todo


def occurrence_scores(conn: sqlite3.Connection) -> dict[int, Score]:
    from app.learning.focus import focus_overrides  # the learned part lives with the learning code

    rows = conn.execute(
        """SELECT m.occurrence_id, m.values_json, a.make, a.model, a.lens FROM measurements m
           JOIN assets a ON a.id = m.asset_id WHERE m.extractor = 'quality' AND m.occurrence_id IS NOT NULL""").fetchall()
    values = {r[0]: json.loads(r[1]) for r in rows}
    overrides = focus_overrides({r[0]: (r[2], r[3], r[4]) for r in rows}, values)
    return {occ: score(v, overrides.get(occ)) for occ, v in values.items()}


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
