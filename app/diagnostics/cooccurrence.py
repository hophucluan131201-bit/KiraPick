"""F3 P0-A: photos where two occurrences carry the SAME person label (diagnostic only).

Within one photo, two people are always different people for the grouping (cannot-link). When the owner's labels
say both are the same customer, one of these is true, and this module only proposes which (a HYPOTHESIS for the
owner to check on the photo; never used by the app):

- ``duplicate_face_only``: a lone face box (an occurrence without a person box) lies inside the other person box —
  the face was not attached to its body, so one person counts twice. One occurrence holding both a person box and
  its face box is the normal case and never appears here (it is a single occurrence).
- ``duplicate_overlapping_bodies``: the two person boxes mostly overlap (one inside the other).
- ``possible_reflection``: separate boxes of similar size with very similar faces (mirror, window, screen).
- ``two_people_same_label``: separate boxes, both faces measured and clearly different: two real people under
  one label (a labelling slip, or the same costume worn by two people).
- ``undetermined``: anything else (missing boxes or faces, or values between the bands). The owner decides.

The bands below are reporting aids for sorting photos to look at; they never change the app's grouping.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CONTAIN_DUPLICATE = 0.8  # share of the smaller box inside the larger one
DISJOINT_MAX_IOU = 0.05
REFLECTION_FACE = 0.6  # face similarity this high on separate boxes: maybe the same person seen twice
DIFFERENT_FACE = 0.3  # face similarity this low on separate boxes: two different people
REFLECTION_SIZE_RATIO = 1.6
CLASSES = ("duplicate_face_only", "duplicate_overlapping_bodies", "possible_reflection",
           "two_people_same_label", "undetermined")


@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return max(self.w, 0.0) * max(self.h, 0.0)


def _box(text: str | None) -> Box | None:
    if not text:
        return None
    try:
        x, y, w, h = (float(v) for v in json.loads(text))
    except (ValueError, TypeError):
        return None
    return Box(x, y, w, h) if w > 0 and h > 0 else None


def _intersection(a: Box, b: Box) -> float:
    w = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    h = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    return max(w, 0.0) * max(h, 0.0)


def iou(a: Box, b: Box) -> float:
    inter = _intersection(a, b)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def containment(a: Box, b: Box) -> float:
    """Share of the smaller box that lies inside the other."""
    small = min(a.area, b.area)
    return _intersection(a, b) / small if small > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Pair:
    asset_id: int
    occ_a: int
    occ_b: int
    klass: str
    iou: float | None
    containment: float | None
    size_ratio: float | None
    face_similarity: float | None


def classify(person_a: Box | None, face_a: Box | None, person_b: Box | None, face_b: Box | None,
             face_sim: float | None) -> tuple[str, float | None, float | None, float | None]:
    """(class, iou, containment, size ratio) for two occurrences of one photo."""
    # A lone face next to a body: is it inside that body?
    for own_person, lone_face, other_person in ((person_a, face_a, person_b), (person_b, face_b, person_a)):
        if own_person is None and lone_face is not None and other_person is not None:
            c = containment(lone_face, other_person)
            if c >= CONTAIN_DUPLICATE and lone_face.area <= other_person.area:
                return "duplicate_face_only", round(iou(lone_face, other_person), 4), round(c, 4), None
    a, b = person_a or face_a, person_b or face_b
    if a is None or b is None:
        return "undetermined", None, None, None
    i, c = iou(a, b), containment(a, b)
    ratio = max(a.area, b.area) / min(a.area, b.area) if min(a.area, b.area) > 0 else None
    values = round(i, 4), round(c, 4), None if ratio is None else round(ratio, 4)
    if person_a is not None and person_b is not None and c >= CONTAIN_DUPLICATE:
        return ("duplicate_overlapping_bodies", *values)
    if i <= DISJOINT_MAX_IOU and face_sim is not None:
        if face_sim >= REFLECTION_FACE and ratio is not None and ratio <= REFLECTION_SIZE_RATIO:
            return ("possible_reflection", *values)
        if face_sim <= DIFFERENT_FACE:
            return ("two_people_same_label", *values)
    return ("undetermined", *values)


def find_pairs(conn, labels: dict) -> list[Pair]:  # noqa: ANN001
    """Every pair of labelled occurrences in one photo that carry the same person label."""
    from app.identity.cluster import load_occurrences, session_profile

    faces = {o.id: o.face for o in load_occurrences(conn, session_profile(conn))}
    rows = conn.execute("SELECT id, asset_id, person_box, face_box FROM occurrences ORDER BY asset_id, id").fetchall()
    by_asset: dict[int, list] = {}
    for r in rows:
        label = labels.get(r[0])
        if label is not None and label.person is not None:
            by_asset.setdefault(r[1], []).append((r[0], label.person, _box(r[2]), _box(r[3])))
    out = []
    for asset_id, occs in by_asset.items():
        for i in range(len(occs)):
            for j in range(i + 1, len(occs)):
                (oa, pa, pba, fba), (ob, pb, pbb, fbb) = occs[i], occs[j]
                if pa != pb:
                    continue
                fa, fb = faces.get(oa), faces.get(ob)
                sim = float(fa @ fb) if fa is not None and fb is not None else None
                klass, i_, c_, r_ = classify(pba, fba, pbb, fbb, sim)
                out.append(Pair(asset_id, oa, ob, klass, i_, c_, r_, None if sim is None else round(sim, 4)))
    return out


def summary(pairs: list[Pair]) -> dict:
    """Counts only (shareable)."""
    counts = Counter(p.klass for p in pairs)
    return {"pairs": len(pairs), "photos": len({p.asset_id for p in pairs}),
            "by_class": {k: counts.get(k, 0) for k in CLASSES},
            "hypotheses_only": True}


def write_local_list(conn, pairs: list[Pair], path: Path) -> int:  # noqa: ANN001
    """The LOCAL list for the owner: photo file name, both subject names, hypothesis and numbers.

    Written only on request; never part of the shareable report. Returns the rows written."""
    import csv

    name = {r[0]: r[1] for r in conn.execute(
        "SELECT o.id, COALESCE(s.display_name, 'Chủ thể ' || s.id) FROM occurrences o "
        "LEFT JOIN subjects s ON s.id = o.subject_id")}
    photo = {r[0]: r[1] for r in conn.execute("SELECT id, relative_path FROM assets")}
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["photo", "subject_a", "subject_b", "hypothesis", "iou", "containment", "size_ratio",
                    "face_similarity", "owner_verdict"])
        for p in pairs:
            w.writerow([photo.get(p.asset_id, ""), name.get(p.occ_a, ""), name.get(p.occ_b, ""), p.klass, p.iou,
                        p.containment, p.size_ratio, p.face_similarity, ""])
    return len(pairs)
