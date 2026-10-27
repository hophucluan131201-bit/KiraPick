"""Look-first grouping of occurrences into subjects (people).

A cosplayer is grouped by *look*: the same face, or the same outfit seen again
within a few minutes. Rules, in order of authority:

1. Manual assignments (``assignment = 'manual'``) are never changed.
2. Two people in the same photo are different people (cannot-link).
3. Subjects the user marked as different never merge; an occurrence the user
   removed from a subject never returns to it.
4. Links between two occurrences (strongest first):
   - faces very similar (``face_strong``), at any time (far apart in time the
     look must also be compatible, unless the faces are near-identical);
   - within ``window_s``: look very similar (``outfit_link``) and the faces,
     if both are visible, at least ``face_with_outfit``;
   - within ``window_s``: faces fairly similar (``face_mid``) and look
     similar (``outfit_mid``).
5. Two groups only merge if their faces are similar on average
   (``average_guard``) — prevents chaining A~B~C with A!~C.
6. Photos without a usable face that joined a group are only *suggested*
   (shown with "?"); a group made only of face-less photos needs >= 2 photos.

The thresholds depend on the identity cues a session has (see ``Thresholds``):
SFace + outfit colours, or — when the optional models are installed — ArcFace +
outfit colours mixed with a whole-body ReID vector. Each user's corrections can
shift them a little (app.learning.tuning). Re-check calibration on more shoots
with scripts/calibration/evaluate_grouping.py.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime

import numpy as np

from app.identity.actions import keep_one_per_photo
from app.storage.project import Project, utc_now

REVIEW_LIMIT = 30
LEAD_PROMINENCE = 0.75  # a small group must be (nearly) the most prominent person of one of its photos ...
BACKGROUND_MAX_PHOTOS = 4  # ... unless it has at least this many photos
FACE_CHUNK = 1024  # rows per block when comparing all faces (bounded memory)


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Grouping thresholds for one set of identity cues (face model + look descriptor)."""

    name: str
    face_strong: float  # face cosine: same person (photos far apart in time also need far_outfit)
    face_certain: float  # near-identical faces link at any time whatever the look
    far_outfit: float  # look similarity a face link needs across more than window_s
    outfit_link: float  # look similarity that links inside the window ...
    face_with_outfit: float  # ... unless both faces are visible and less similar than this
    face_mid: float  # fairly similar face ...
    outfit_mid: float  # ... plus similar look inside the window
    average_guard: float  # mean face similarity two groups need to merge
    far_average: float  # ... when no photo of one is within window_s of a photo of the other
    outfit_suggest: float  # left-over face-less photo: look needed for a suggestion
    review_face: float  # review queue: closest faces reach this and photos close in time ...
    review_face_anytime: float  # ... or faces this similar at any time
    review_face_floor: float  # review by look+time only if faces (when visible) reach this
    review_look: float = 0.75  # review queue: typical look similarity two subjects need to be asked about
    body_weight: float = 0.0  # share of the whole-body (ReID) similarity in the look similarity
    window_s: float = 300  # look cues only within +-5 minutes (same look, same set)
    outfit_margin: float = 0.05  # best look match must beat the runner-up by this much
    suggest_window_s: float = 600  # suggestion window for left-over face-less photos
    review_near_s: float = 1800

    def shifted(self, face: float = 0.0, look: float = 0.0) -> Thresholds:
        """Face / look link thresholds moved by the given amounts (per-user tuning)."""
        return replace(
            self, face_strong=self.face_strong + face, face_with_outfit=self.face_with_outfit + face,
            face_mid=self.face_mid + face,
            far_outfit=self.far_outfit + look, outfit_link=self.outfit_link + look,
            outfit_mid=self.outfit_mid + look, outfit_suggest=self.outfit_suggest + look)


# SFace (128-d) + banded HSV outfit histograms. Owner's full shoot (439 NEF, 46
# looks): pairwise precision 1.00, recall 0.82 (first face-only rules: 0.56).
# Margin is thin: different cosplayers in similar colours a few minutes apart reach face 0.58.
SFACE_HSV = Thresholds(
    "sface+hsv", face_strong=0.65, face_certain=0.80, far_outfit=0.65, outfit_link=0.80, face_with_outfit=0.55,
    face_mid=0.55, outfit_mid=0.78, average_guard=0.45, far_average=0.60, outfit_suggest=0.85,
    review_face=0.45, review_face_anytime=0.60, review_face_floor=0.35)
# ArcFace (512-d) + look = HSV histograms mixed 50/50 with YoutuReID. Calibrated on the owner's
# shoot with the vectors the app itself computed at 1600 px (debug bundle 3, 2026-10-27):
# pairwise precision 1.00, recall 0.92 (SFace profile on the same data: 1.00 / 0.81). Different
# people a few minutes apart reach ArcFace 0.45 at most (face_mid 0.50); far apart 0.68 (a face
# link there also needs a compatible look unless >= face_certain 0.70).
ARCFACE_REID = Thresholds(
    "arcface+reid", face_strong=0.58, face_certain=0.70, far_outfit=0.55, outfit_link=0.72, face_with_outfit=0.35,
    face_mid=0.50, outfit_mid=0.66, average_guard=0.20, far_average=0.42, outfit_suggest=0.78,
    review_face=0.35, review_face_anytime=0.50, review_face_floor=0.20, review_look=0.63, body_weight=0.5)
PROFILES = {t.name: t for t in (SFACE_HSV, ARCFACE_REID)}
# Old names (tests, scripts): the SFace profile.
FACE_STRONG = SFACE_HSV.face_strong
WINDOW_S = SFACE_HSV.window_s
OUTFIT_LINK = SFACE_HSV.outfit_link


@dataclass(slots=True)
class Occ:
    id: int
    asset_id: int
    time: float | None
    face: np.ndarray | None  # the face vector grouping uses (ArcFace when the session has it, else SFace)
    outfit: np.ndarray | None  # banded HSV histograms
    assignment: str
    subject_id: int | None
    excluded: int | None
    body: np.ndarray | None = None  # whole-body ReID vector (ArcFace sessions only)
    face_sface: np.ndarray | None = None
    face_arc: np.ndarray | None = None
    prominence: float = 1.0  # 1.0 = the most prominent person of its photo


@dataclass(slots=True)
class ClusterReport:
    subjects: int = 0
    auto: int = 0
    suggested: int = 0
    unassigned: int = 0
    manual: int = 0
    profile: str = ""


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
    suggestions: dict[int, tuple[int, float]]  # left-over occ index -> (group index, look similarity)


def _ts(value: str | None) -> float | None:
    return datetime.fromisoformat(value).timestamp() if value else None


def session_profile(conn: sqlite3.Connection) -> Thresholds:
    """ArcFace thresholds when this session has ArcFace vectors, else SFace."""
    has_arc = conn.execute("SELECT 1 FROM occurrence_vectors WHERE kind = 'face_arc' LIMIT 1").fetchone()
    return ARCFACE_REID if has_arc else SFACE_HSV


def load_occurrences(conn: sqlite3.Connection, profile: Thresholds | None = None) -> list[Occ]:
    profile = profile or session_profile(conn)
    rows = conn.execute(
        """SELECT o.id, o.asset_id, o.assignment, o.subject_id, o.excluded_subject_id, a.capture_time, o.prominence,
                  fv.vector AS face, av.vector AS face_arc, ov.vector AS outfit, bv.vector AS body
           FROM occurrences o JOIN assets a ON a.id = o.asset_id
           LEFT JOIN occurrence_vectors fv ON fv.occurrence_id = o.id AND fv.kind = 'face'
           LEFT JOIN occurrence_vectors av ON av.occurrence_id = o.id AND av.kind = 'face_arc'
           LEFT JOIN occurrence_vectors ov ON ov.occurrence_id = o.id AND ov.kind = 'outfit'
           LEFT JOIN occurrence_vectors bv ON bv.occurrence_id = o.id AND bv.kind = 'body'
           WHERE a.status = 'ok' AND (o.is_main = 1 OR o.assignment = 'manual')
           ORDER BY o.id"""
    ).fetchall()
    vec = lambda b: np.frombuffer(b, dtype="<f4") if b is not None else None  # noqa: E731
    arc = profile.body_weight > 0  # the ArcFace profile; never mix two face models in one grouping
    out = []
    for r in rows:
        sface, face_arc = vec(r["face"]), vec(r["face_arc"])
        out.append(Occ(r["id"], r["asset_id"], _ts(r["capture_time"]), face_arc if arc else sface, vec(r["outfit"]),
                       r["assignment"], r["subject_id"], r["excluded_subject_id"],
                       body=vec(r["body"]) if arc else None, face_sface=sface, face_arc=face_arc,
                       prominence=r["prominence"]))
    return out


def look_similarity(a: Occ, b: Occ, profile: Thresholds) -> float | None:
    """Outfit colours, mixed with the whole-body vector when both photos have one."""
    if a.outfit is None or b.outfit is None:
        return None
    colours = float(a.outfit @ b.outfit)
    if profile.body_weight and a.body is not None and b.body is not None:
        return (1 - profile.body_weight) * colours + profile.body_weight * float(a.body @ b.body)
    return colours


def pair_link(profile: Thresholds, face: float | None, look: float | None, dt: float | None) -> float | None:
    """Link strength the rules give one pair of photos (None = no direct link).

    Face links score above 1, look links in 0..1. ``dt`` None = unknown capture time,
    treated like photos far apart.
    """
    near = dt is not None and dt <= profile.window_s
    if face is not None and face >= profile.face_strong and (
            near or face >= profile.face_certain or (look is not None and look >= profile.far_outfit)):
        return 1.0 + face
    if not near or look is None:
        return None
    if look >= profile.outfit_link and (face is None or face >= profile.face_with_outfit):
        return look
    if face is not None and face >= profile.face_mid and look >= profile.outfit_mid:
        return (face + look) / 2
    return None


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


def _dt(a: Occ, b: Occ) -> float | None:
    return abs(a.time - b.time) if a.time is not None and b.time is not None else None


def _edges(occs: list[Occ], nodes: list[int], p: Thresholds) -> list[tuple[float, int, int]]:
    """Candidate links (score, i, j) between occurrence indexes; higher score = stronger evidence."""
    edges: list[tuple[float, int, int]] = []
    seen: set[tuple[int, int]] = set()
    faced = [i for i in nodes if occs[i].face is not None]
    if faced:
        F = np.stack([occs[i].face for i in faced])
        for lo in range(0, len(faced), FACE_CHUNK):
            block = F[lo:lo + FACE_CHUNK] @ F.T
            for r, c in zip(*np.nonzero(block >= p.face_strong)):
                if lo + r >= c:
                    continue
                i, j = faced[lo + r], faced[c]
                score = pair_link(p, float(block[r, c]), look_similarity(occs[i], occs[j], p), _dt(occs[i], occs[j]))
                seen.add((i, j))
                if score is not None:
                    edges.append((score, i, j))
    timed = sorted((i for i in nodes if occs[i].time is not None and occs[i].outfit is not None),
                   key=lambda i: occs[i].time)
    times = np.array([occs[i].time for i in timed])
    for k, i in enumerate(timed):
        a = occs[i]
        hi = int(np.searchsorted(times, a.time + p.window_s, side="right"))
        for j in timed[k + 1:hi]:
            if (min(i, j), max(i, j)) in seen:
                continue  # already judged as a face pair
            b = occs[j]
            fs = float(a.face @ b.face) if a.face is not None and b.face is not None else None
            score = pair_link(p, fs, look_similarity(a, b, p), _dt(a, b))
            if score is not None:
                edges.append((score, i, j))
    return edges


def group(occs: list[Occ], different: set[tuple[int, int]] = frozenset(), profile: Thresholds = SFACE_HSV) -> Grouping:
    p = profile
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
        gaps = [abs(t2[min(q, len(t2) - 1)] - t) for q, t in zip(pos, t1)] + \
               [abs(t2[q - 1] - t) for q, t in zip(pos, t1) if q > 0]
        return min(gaps) <= p.window_s

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
    for score, i, j in sorted(_edges(occs, sorted(owner), p),
                              key=lambda e: (not (e[0] >= 1.0 and (e[1] in seeded or e[2] in seeded)), -e[0])):
        gi, gj = owner[i], owner[j]
        if gi != gj:
            g1, g2 = groups[gi], groups[gj]
            if _conflict(g1, g2, different):
                continue
            if g1.faces and g2.faces:
                guard = p.average_guard if _near_in_time(g1, g2) else p.far_average
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

    # A lone face-less photo is not a person of its own. Neither is someone who is never (nearly)
    # the main person of any photo in a small group: a passer-by or a blurred person behind the
    # cosplayer. A partner in a duo shoot stays (close to the lead's size, or many photos).
    for g in groups:
        if g.members and g.fixed_subject is None and (
                (not g.faces and len(g.members) < 2)
                or (len(g.members) < BACKGROUND_MAX_PHOTOS
                    and max(occs[m].prominence for m in g.members) < LEAD_PROMINENCE)):
            for m in g.members:
                del owner[m]
            g.members, g.assets = [], set()
    weak = {i: weak.get(i) for i in owner if occs[i].face is None and occs[i].assignment != "manual"}

    # Left-over face-less main occurrences: look + time window, suggestion only.
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
                if other.outfit is not None and other.time is not None and abs(other.time - o.time) <= p.suggest_window_s:
                    best = max(best, look_similarity(o, other, p) or 0.0)
            if best > 0:
                scores[gi] = best
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if ranked and ranked[0][1] >= p.outfit_suggest and (
                len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= p.outfit_margin):
            suggestions[i] = ranked[0]
    return Grouping(groups, weak, suggestions)


def recluster(project: Project, tune: Callable[[Thresholds], Thresholds] | None = None) -> ClusterReport:
    """Regroup the session. ``tune`` may adjust the thresholds (this user's learnt corrections)."""
    conn = project.conn
    with project.transaction():
        keep_one_per_photo(conn)  # repairs sessions where one subject holds two people of a photo
    profile = session_profile(conn)
    if tune is not None:
        profile = tune(profile)
    occs = load_occurrences(conn, profile)
    different = _different_pairs(conn)
    grouping = group(occs, different, profile)
    groups, weak, suggestions = grouping.groups, grouping.weak, grouping.suggestions
    report = ClusterReport(profile=profile.name)
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
    same_outfit: bool = False  # the looks are as close as the same costume's usually are
    look: float | None = None  # typical (median) look similarity between their photos; None = not comparable


def merge_suggestions(conn: sqlite3.Connection, limit: int = REVIEW_LIMIT) -> list[Suggestion]:
    """Subject pairs that may be one look the grouping split: similar outfits (and faces not against it).

    A look is a costume: two subjects whose outfits are clearly different are not asked about,
    however alike the faces (cosplay makeup makes different people look alike — owner's report:
    face 0.55, different costumes, 57 of 64 such questions were different people).
    """
    p = session_profile(conn)
    occs = [o for o in load_occurrences(conn, p) if o.subject_id is not None]
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
            sims = [v for q in by_subject[a] for r in by_subject[b] if (v := look_similarity(q, r, p)) is not None]
            look = float(np.median(sims)) if sims else None
            if look is None:
                ok = face is not None and face >= p.review_face_anytime  # nothing to compare but faces
            else:
                ok = look >= p.review_look and (face is None or face >= p.review_face_floor)
            if ok:
                out.append(Suggestion(a, b, round(face or 0.0, 3), look is not None, None if look is None else round(look, 3)))
    return sorted(out, key=lambda s: -((s.look or 0.0) + 0.5 * s.similarity))[:limit]
