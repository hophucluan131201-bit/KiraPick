"""Shot size Toàn / Trung / Cận / Chưa xác định from the boxes of one photo (Media spec v6 §5, plan Mốc 1 M6).

Only the position and size of people count, never sharpness: a blurred close-up is still Cận (with a focus warning).

Main subject = the largest person left after removing:
  - a person cut by a side edge so that less than half of them shows (a thin box along the edge);
  - a person facing away (no face found in their box while another person shows a face);
  - an audience head in the foreground (box in the lower part, touching the bottom edge, no face).
Two paths:
  1. a face is found for the main subject: face height / photo height. Cận > 12 %, Trung 4-12 %, Toàn < 4 %;
  2. only a person box: below 25 % of the photo height -> Toàn; anything else -> Chưa xác định (a body box does not
     tell a waist shot from a knee shot).
No person -> Chưa xác định. The thresholds are the starting values of the spec; the sample-labelling scorer (M9)
reports how they do on the owner's photos. Until then every AI shot size is shown "(thử nghiệm)".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

Box = tuple[float, float, float, float]  # x, y, w, h in pixels

SHOT_VERSION = "s1"


@dataclass(frozen=True, slots=True)
class ShotRules:
    close_face: float = 0.12  # face height / photo height above which a shot is Cận
    wide_face: float = 0.04  # below this, Toàn
    wide_body: float = 0.25  # no face: a person box lower than this is Toàn
    edge_px_frac: float = 0.003  # a box within this fraction of the width touches a side edge
    sliver_aspect: float = 0.22  # a person touching a side edge with w/h below this shows less than half of them
    bottom_frac: float = 0.995  # a box reaching this fraction of the height touches the bottom edge
    audience_top: float = 0.4  # ... and an audience head starts below this fraction (a close-up body starts higher)


@dataclass(frozen=True, slots=True)
class Subject:
    person: Box | None
    face: Box | None
    score: float  # detector confidence: the face's when there is one, else the person's


@dataclass(frozen=True, slots=True)
class ShotResult:
    value: str  # 'toan' | 'trung' | 'can' | '?'
    confidence: float | None
    path: str  # 'face' | 'body' | 'none'
    subject: Subject | None
    measures: dict  # numbers only: face_h, body_h (fractions of the photo height), n_people, n_excluded

    def as_dict(self) -> dict:
        d = asdict(self)
        d["subject"] = None if self.subject is None else {"person": self.subject.person, "face": self.subject.face}
        return d


def _area(s: Subject) -> float:
    box = s.person or s.face
    return 0.0 if box is None else box[2] * box[3]


def _excluded(s: Subject, w: int, h: int, any_face: bool, rules: ShotRules) -> str | None:
    if s.person is None:
        return None
    x, y, bw, bh = s.person
    edge = rules.edge_px_frac * w
    at_side = x <= edge or x + bw >= w - edge
    if at_side and bh > 0 and bw / bh < rules.sliver_aspect:
        return "cut"
    if s.face is None and y + bh >= rules.bottom_frac * h and y >= rules.audience_top * h:
        return "audience"
    if s.face is None and any_face:
        return "back"
    return None


def classify(subjects: list[Subject], width: int, height: int, rules: ShotRules = ShotRules()) -> ShotResult:  # noqa: B008
    any_face = any(s.face is not None for s in subjects)
    kept = [s for s in subjects if _excluded(s, width, height, any_face, rules) is None]
    measures = {"n_people": len(subjects), "n_excluded": len(subjects) - len(kept), "face_h": None, "body_h": None}
    if not kept:
        return ShotResult("?", None, "none", None, measures)
    main = max(kept, key=_area)
    if main.face is not None:
        face_h = main.face[3] / height
        measures["face_h"] = round(face_h, 4)
        if main.person is not None:
            measures["body_h"] = round(main.person[3] / height, 4)
        value = "can" if face_h > rules.close_face else "trung" if face_h >= rules.wide_face else "toan"
        return ShotResult(value, round(main.score, 3), "face", main, measures)
    body_h = main.person[3] / height  # type: ignore[index] - a subject without a face has a person box
    measures["body_h"] = round(body_h, 4)
    if body_h < rules.wide_body:
        return ShotResult("toan", round(main.score, 3), "body", main, measures)
    return ShotResult("?", None, "body", main, measures)


def subjects_from(persons: list[tuple[Box, float]], faces: list[tuple[Box, float]]) -> list[Subject]:
    """Pair each face with the tightest person box whose upper part holds its centre (as app.ai.detect.associate)."""
    out = [[p, None, s] for p, s in persons]
    for fbox, fscore in sorted(faces, key=lambda f: -f[1]):
        cx, cy = fbox[0] + fbox[2] / 2, fbox[1] + fbox[3] / 2
        best = None
        for row in out:
            if row[1] is not None or row[0] is None:
                continue
            x, y, w, h = row[0]
            if x <= cx <= x + w and y <= cy <= y + h * 0.6 and (best is None or w * h < best[0][2] * best[0][3]):
                best = row
        if best is not None:
            best[1], best[2] = fbox, fscore
        else:
            out.append([None, fbox, fscore])
    return [Subject(p, f, float(s)) for p, f, s in out]
