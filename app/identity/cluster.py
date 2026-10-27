"""Look-first grouping of occurrences into subjects (people).

A cosplayer is grouped by *look*: the same face, or the same outfit seen again
within a few minutes. Rules, in order of authority:

1. Manual assignments (``assignment = 'manual'``) are never changed.
2. Two people in the same photo are different people (cannot-link).
3. Subjects the user marked as different never merge; an occurrence the user
   removed from a subject never returns to it.
4. Links between two occurrences (strongest first):
   - faces very similar (``FACE_STRONG``), at any time;
   - within ``WINDOW_S``: outfit very similar (``OUTFIT_LINK``) and the faces,
     if both are visible, at least ``FACE_WITH_OUTFIT``;
   - within ``WINDOW_S``: faces fairly similar (``FACE_MID``) and outfit
     similar (``OUTFIT_MID``).
5. Two groups only merge if their faces are similar on average
   (``AVERAGE_GUARD``) — prevents chaining A~B~C with A!~C.
6. Photos without a usable face that joined a group are only *suggested*
   (shown with "?"); a group made only of face-less photos needs >= 2 photos.

Calibration (owner's 'Test' shoot, 109 photos, 37 labelled looks, SFace +
HSV outfit histogram): pairwise precision 1.00, recall 0.76 (previous
face-only rules: 0.56 / 0.76). Margin is thin: the most similar *different*
cosplayers reached face 0.54 / outfit 0.91 within 5 minutes, so these values
must be re-checked on more shoots (scripts/calibration/evaluate_grouping.py).
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.storage.project import Project, utc_now

FACE_STRONG = 0.65  # SFace cosine: same person (photos far apart in time also need FAR_OUTFIT)
FACE_CERTAIN = 0.80  # near-identical faces link at any time whatever the outfit
FAR_OUTFIT = 0.65  # outfit similarity a face link needs across more than WINDOW_S
WINDOW_S = 300  # outfit cues only within +-5 minutes (same look, same set)
OUTFIT_LINK = 0.85  # outfit-colour similarity that links inside the window ...
FACE_WITH_OUTFIT = 0.55  # ... unless both faces are visible and less similar than this
FACE_MID = 0.58  # fairly similar face ...
OUTFIT_MID = 0.70  # ... plus similar outfit inside the window
AVERAGE_GUARD = 0.45  # mean face similarity two groups need to merge
FAR_AVERAGE = 0.60  # ... when no photo of one is within WINDOW_S of a photo of the other
OUTFIT_SUGGEST = 0.85  # left-over face-less photo: outfit needed for a suggestion
OUTFIT_MARGIN = 0.05  # best outfit match must beat the runner-up by this much
SUGGEST_WINDOW_S = 600  # suggestion window for left-over face-less photos
REVIEW_FACE = 0.45  # review queue: closest faces reach this and photos close in time (REVIEW_NEAR_S) ...
REVIEW_NEAR_S = 1800
REVIEW_FACE_ANYTIME = 0.60  # ... or faces this similar at any time
REVIEW_FACE_FLOOR = 0.35  # review by outfit+time only if faces (when visible) reach this
REVIEW_LIMIT = 30
FACE_CHUNK = 1024  # rows per block when comparing all faces (bounded memory)


@dataclass(slots=True)
class Occ:
    id: int
    asset_id: int
    time: float | None
    face: np.ndarray | None
    outfit: np.ndarray | None
    assignment: str
    subject_id: int | None
    excluded: int | None


@dataclass(slots=True)
class ClusterReport:
    subjects: int = 0
    auto: int = 0
    suggested: int = 0
    unassigned: int = 0
    manual: int = 0


@dataclass(slots=True)
class _Group:
    members: list[int] = field(default_factory=list)  # indexes into occs
    fixed_subject: int | None = None  # manual seed
    assets: set[int] = field(default_factory=set)
    prev_subjects: Counter = field(default_factory=Counter)
    excluded: set[int] = field(default_factory=set)
    face_sum: np.ndarray | None = None  # sum of member faces: mean pair similarity = sumA.sumB / (nA nB)
    faces: int = 0


@dataclass(slots=True)
class Grouping:
    groups: list[_Group]
    weak: dict[int, float | None]  # occ index -> link strength; face-less members, assigned as 'suggested'
    suggestions: dict[int, tuple[int, float]]  # left-over occ index -> (group index, outfit similarity)


def _ts(value: str | None) -> float | None:
    return datetime.fromisoformat(value).timestamp() if value else None


def load_occurrences(conn: sqlite3.Connection) -> list[Occ]:
    rows = conn.execute(
        """SELECT o.id, o.asset_id, o.assignment, o.subject_id, o.excluded_subject_id, a.capture_time,
                  fv.vector AS face, ov.vector AS outfit
           FROM occurrences o JOIN assets a ON a.id = o.asset_id
           LEFT JOIN occurrence_vectors fv ON fv.occurrence_id = o.id AND fv.kind = 'face'
           LEFT JOIN occurrence_vectors ov ON ov.occurrence_id = o.id AND ov.kind = 'outfit'
           WHERE a.status = 'ok' AND (o.is_main = 1 OR o.assignment = 'manual')
           ORDER BY o.id"""
    ).fetchall()
    vec = lambda b: np.frombuffer(b, dtype="<f4") if b is not None else None  # noqa: E731
    return [Occ(r["id"], r["asset_id"], _ts(r["capture_time"]), vec(r["face"]), vec(r["outfit"]),
                r["assignment"], r["subject_id"], r["excluded_subject_id"]) for r in rows]


def _different_pairs(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    return {(r[0], r[1]) for r in conn.execute("SELECT a, b FROM subject_pairs WHERE relation = 'different'")}


def _conflict(g1: _Group, g2: _Group, different: set[tuple[int, int]]) -> bool:
    if g1.assets & g2.assets:
        return True  # same photo -> different people
    if g1.fixed_subject is not None and g2.fixed_subject is not None and g1.fixed_subject != g2.fixed_subject:
        return True
    subj1 = set(g1.prev_subjects) | ({g1.fixed_subject} - {None})
    subj2 = set(g2.prev_subjects) | ({g2.fixed_subject} - {None})
    if subj1 & g2.excluded or subj2 & g1.excluded:
        return True
    return any((min(a, b), max(a, b)) in different for a in subj1 for b in subj2 if a != b)


def _far_face_link_ok(a: Occ, b: Occ, face: float) -> bool:
    """A strong face link between photos far apart in time also needs a compatible outfit,
    unless the faces are near-identical: cosplay makeup makes different people look alike."""
    if a.time is not None and b.time is not None and abs(a.time - b.time) <= WINDOW_S:
        return True
    if face >= FACE_CERTAIN:
        return True
    return a.outfit is not None and b.outfit is not None and float(a.outfit @ b.outfit) >= FAR_OUTFIT


def _edges(occs: list[Occ], nodes: list[int]) -> list[tuple[float, int, int]]:
    """Candidate links (score, i, j) between occurrence indexes; higher score = stronger evidence."""
    edges: list[tuple[float, int, int]] = []
    faced = [i for i in nodes if occs[i].face is not None]
    if faced:
        F = np.stack([occs[i].face for i in faced])
        for lo in range(0, len(faced), FACE_CHUNK):
            block = F[lo:lo + FACE_CHUNK] @ F.T
            for r, c in zip(*np.nonzero(block >= FACE_STRONG)):
                i, j = faced[lo + r], faced[c]
                if lo + r < c and _far_face_link_ok(occs[i], occs[j], float(block[r, c])):
                    edges.append((1.0 + float(block[r, c]), i, j))
    timed = sorted((i for i in nodes if occs[i].time is not None and occs[i].outfit is not None),
                   key=lambda i: occs[i].time)
    times = np.array([occs[i].time for i in timed])
    for k, i in enumerate(timed):
        a = occs[i]
        hi = int(np.searchsorted(times, a.time + WINDOW_S, side="right"))
        for j in timed[k + 1:hi]:
            b = occs[j]
            us = float(a.outfit @ b.outfit)
            fs = float(a.face @ b.face) if a.face is not None and b.face is not None else None
            if fs is not None and fs >= FACE_STRONG:
                continue  # already a face edge
            if us >= OUTFIT_LINK and (fs is None or fs >= FACE_WITH_OUTFIT):
                edges.append((us, i, j))
            elif fs is not None and fs >= FACE_MID and us >= OUTFIT_MID:
                edges.append(((fs + us) / 2, i, j))
    return edges


def group(occs: list[Occ], different: set[tuple[int, int]] = frozenset()) -> Grouping:
    groups: list[_Group] = []
    owner: dict[int, int] = {}  # occ index -> group index

    def new_group(idx: list[int], fixed: int | None) -> None:
        g = _Group(fixed_subject=fixed)
        for i in idx:
            g.members.append(i)
            g.assets.add(occs[i].asset_id)
            if occs[i].subject_id is not None and occs[i].assignment in ("auto", "suggested"):
                g.prev_subjects[occs[i].subject_id] += 1
            if occs[i].excluded is not None:
                g.excluded.add(occs[i].excluded)
            if occs[i].face is not None:
                g.face_sum = occs[i].face.astype(np.float64) + (0 if g.face_sum is None else g.face_sum)
                g.faces += 1
            owner[i] = len(groups)
        groups.append(g)

    manual: dict[int, list[int]] = defaultdict(list)
    for i, o in enumerate(occs):
        if o.assignment == "manual" and o.subject_id is not None:
            manual[o.subject_id].append(i)
    for subject_id, idx in manual.items():
        new_group(idx, subject_id)
    # A photo the user deliberately left unassigned (manual, no subject) stays out.
    for i, o in enumerate(occs):
        if o.assignment != "manual" and (o.face is not None or (o.outfit is not None and o.time is not None)):
            new_group([i], None)

    def _near_in_time(g1: _Group, g2: _Group) -> bool:
        t1 = sorted(occs[m].time for m in g1.members if occs[m].time is not None)
        t2 = np.array(sorted(occs[m].time for m in g2.members if occs[m].time is not None))
        if not t1 or not len(t2):
            return True  # unknown capture time: do not make it stricter
        pos = np.searchsorted(t2, t1)
        gaps = [abs(t2[min(p, len(t2) - 1)] - t) for p, t in zip(pos, t1)] + \
               [abs(t2[p - 1] - t) for p, t in zip(pos, t1) if p > 0]
        return min(gaps) <= WINDOW_S

    def absorb(keep: int, drop: int) -> None:
        gk, gd = groups[keep], groups[drop]
        for m in gd.members:
            owner[m] = keep
        gk.members += gd.members
        gk.assets |= gd.assets
        gk.prev_subjects.update(gd.prev_subjects)
        gk.excluded |= gd.excluded
        gk.fixed_subject = gk.fixed_subject or gd.fixed_subject
        if gd.face_sum is not None:
            gk.face_sum = gd.face_sum if gk.face_sum is None else gk.face_sum + gd.face_sum
            gk.faces += gd.faces
        gd.members, gd.assets, gd.face_sum, gd.faces = [], set(), None, 0

    weak: dict[int, float | None] = {}
    # Strong face links to photos the user assigned go first: confirmed people attract before
    # free photos pair up among themselves (keeps a removed photo from dragging others away).
    seeded = {i for idx in manual.values() for i in idx}
    for score, i, j in sorted(_edges(occs, sorted(owner)),
                              key=lambda e: (not (e[0] >= 1.0 and (e[1] in seeded or e[2] in seeded)), -e[0])):
        gi, gj = owner[i], owner[j]
        if gi != gj:
            g1, g2 = groups[gi], groups[gj]
            if _conflict(g1, g2, different):
                continue
            if g1.faces and g2.faces:
                guard = AVERAGE_GUARD if _near_in_time(g1, g2) else FAR_AVERAGE
                if float(g1.face_sum @ g2.face_sum) / (g1.faces * g2.faces) < guard:
                    continue
            absorb(*((gi, gj) if g2.fixed_subject is None else (gj, gi)))
        for x in (i, j):  # strength of the best accepted link of a face-less member
            if occs[x].face is None:
                weak[x] = max(weak.get(x, 0.0), min(score, 1.0))

    # Stability: a group that already belonged to a person the user corrected
    # (merge, manual assignment) stays with that person unless that conflicts.
    fixed_by_subject = {g.fixed_subject: gi for gi, g in enumerate(groups) if g.fixed_subject is not None and g.members}
    for gi, g in enumerate(groups):
        if g.fixed_subject is None and g.members and g.prev_subjects:
            fi = fixed_by_subject.get(g.prev_subjects.most_common(1)[0][0])
            if fi is not None and not _conflict(groups[fi], g, different):
                absorb(fi, gi)

    # A lone face-less photo is not a person of its own.
    for g in groups:
        if g.members and not g.faces and g.fixed_subject is None and len(g.members) < 2:
            for m in g.members:
                del owner[m]
            g.members, g.assets = [], set()
    weak = {i: weak.get(i) for i in owner if occs[i].face is None and occs[i].assignment != "manual"}

    # Left-over face-less main occurrences: outfit + time window, suggestion only.
    suggestions: dict[int, tuple[int, float]] = {}
    for i, o in enumerate(occs):
        if i in owner or o.assignment == "manual" or o.outfit is None or o.time is None:
            continue
        scores: dict[int, float] = {}
        for gi, g in enumerate(groups):
            if not g.members or o.asset_id in g.assets or (o.excluded is not None and
                                                           (o.excluded == g.fixed_subject or o.excluded in g.prev_subjects)):
                continue
            best = 0.0
            for m in g.members:
                other = occs[m]
                if other.outfit is not None and other.time is not None and abs(other.time - o.time) <= SUGGEST_WINDOW_S:
                    best = max(best, float(o.outfit @ other.outfit))
            if best > 0:
                scores[gi] = best
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if ranked and ranked[0][1] >= OUTFIT_SUGGEST and (len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= OUTFIT_MARGIN):
            suggestions[i] = ranked[0]
    return Grouping(groups, weak, suggestions)


def recluster(project: Project) -> ClusterReport:
    conn = project.conn
    occs = load_occurrences(conn)
    different = _different_pairs(conn)
    grouping = group(occs, different)
    groups, weak, suggestions = grouping.groups, grouping.weak, grouping.suggestions
    report = ClusterReport()
    now = utc_now()
    with project.transaction():
        # Map groups to subject ids: manual seed, else the previous subject most of its members had.
        taken: set[int] = set()
        subject_of: dict[int, int] = {}
        order = sorted(range(len(groups)), key=lambda gi: (groups[gi].fixed_subject is None, -len(groups[gi].members)))
        for gi in order:
            g = groups[gi]
            if not g.members:
                continue
            sid = g.fixed_subject
            if sid is None:
                for candidate, _ in g.prev_subjects.most_common():
                    if candidate not in taken and conn.execute("SELECT 1 FROM subjects WHERE id = ?", (candidate,)).fetchone():
                        sid = candidate
                        break
            if sid is None:
                sid = int(conn.execute("INSERT INTO subjects (created_at) VALUES (?)", (now,)).lastrowid)
            taken.add(sid)
            subject_of[gi] = sid
        for gi, g in enumerate(groups):
            for m in g.members:
                o = occs[m]
                if o.assignment == "manual":
                    report.manual += 1
                    continue
                if m in weak:
                    confidence = None if weak[m] is None else round(weak[m], 4)
                    conn.execute("UPDATE occurrences SET subject_id = ?, assignment = 'suggested', confidence = ? WHERE id = ?",
                                 (subject_of[gi], confidence, o.id))
                    report.suggested += 1
                    continue
                conn.execute("UPDATE occurrences SET subject_id = ?, assignment = 'auto', confidence = NULL WHERE id = ?",
                             (subject_of[gi], o.id))
                report.auto += 1
        grouped = {m for g in groups for m in g.members}
        for i, o in enumerate(occs):
            if i in grouped or o.assignment == "manual":
                continue
            if i in suggestions:
                gi, score = suggestions[i]
                conn.execute("UPDATE occurrences SET subject_id = ?, assignment = 'suggested', confidence = ? WHERE id = ?",
                             (subject_of[gi], round(score, 4), o.id))
                report.suggested += 1
            else:
                conn.execute("UPDATE occurrences SET subject_id = NULL, assignment = 'none', confidence = NULL WHERE id = ?",
                             (o.id,))
                report.unassigned += 1
        # Background people are never grouped.
        conn.execute("""UPDATE occurrences SET subject_id = NULL, assignment = 'none'
                        WHERE is_main = 0 AND assignment != 'manual'""")
        # Auto-created subjects that lost all their photos disappear; named ones stay.
        conn.execute("""DELETE FROM subjects WHERE user_locked = 0 AND display_name IS NULL
                        AND id NOT IN (SELECT subject_id FROM occurrences WHERE subject_id IS NOT NULL)""")
        report.subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    return report


@dataclass(frozen=True, slots=True)
class Suggestion:
    a: int
    b: int
    similarity: float  # closest face similarity between the two subjects (0 if no faces to compare)
    same_outfit: bool = False  # suggested because of the same outfit a few minutes apart


def merge_suggestions(conn: sqlite3.Connection, limit: int = REVIEW_LIMIT) -> list[Suggestion]:
    """Subject pairs that may be one person: faces fairly similar, or the same outfit within the window."""
    occs = [o for o in load_occurrences(conn) if o.subject_id is not None]
    different = _different_pairs(conn)
    by_subject: dict[int, list[Occ]] = defaultdict(list)
    for o in occs:
        by_subject[o.subject_id].append(o)
    ids = sorted(by_subject)
    faces = {s: np.stack([o.face for o in v if o.face is not None]) for s, v in by_subject.items()
             if any(o.face is not None for o in v)}
    out = []
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            if (a, b) in different:
                continue
            assets_a = {o.asset_id for o in by_subject[a]}
            if assets_a & {o.asset_id for o in by_subject[b]}:
                continue  # in one photo together -> two people
            face = float((faces[a] @ faces[b].T).max()) if a in faces and b in faces else None
            outfit = max((float(p.outfit @ q.outfit) for p in by_subject[a] for q in by_subject[b]
                          if p.outfit is not None and q.outfit is not None and p.time is not None
                          and q.time is not None and abs(p.time - q.time) <= WINDOW_S), default=0.0)
            gap = min((abs(p.time - q.time) for p in by_subject[a] for q in by_subject[b]
                       if p.time is not None and q.time is not None), default=float("inf"))
            same_outfit = outfit >= OUTFIT_LINK and (face is None or face >= REVIEW_FACE_FLOOR)
            similar_face = face is not None and (face >= REVIEW_FACE_ANYTIME or (face >= REVIEW_FACE and gap <= REVIEW_NEAR_S))
            if similar_face or same_outfit:
                out.append(Suggestion(a, b, round(face or 0.0, 3), same_outfit))
    return sorted(out, key=lambda s: -(s.similarity + (0.2 if s.same_outfit else 0.0)))[:limit]
