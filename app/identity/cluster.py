"""Conservative grouping of occurrences into subjects (people).

Rules, in order of authority:
1. Manual assignments (``assignment = 'manual'``) are never changed.
2. Two people in the same photo are different people (cannot-link).
3. Subjects the user marked as different never merge; an occurrence the user
   removed from a subject never returns to it.
4. Faces link automatically only when a pair is very similar *and* the two
   groups are similar on average (prevents chaining A~B~C with A!~C).
5. Photos without a usable face get at most a *suggestion* from outfit colour
   within a short time window — never an automatic assignment.

Thresholds are starting values for SFace cosine similarity, NOT calibrated on
labelled data yet; anything between ``SUGGEST`` and the automatic thresholds
is offered in the review queue instead of being merged.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.storage.project import Project, utc_now

AUTO_PAIR = 0.55  # best pair similarity needed to consider merging two groups
AUTO_AVERAGE = 0.45  # mean similarity between the two groups needed to merge
SUGGEST = 0.40  # below auto, at/above this: shown in the review queue
OUTFIT_SUGGEST = 0.85  # outfit-colour cosine to suggest a face-less photo
OUTFIT_MARGIN = 0.05  # best outfit match must beat the runner-up by this much
OUTFIT_WINDOW_S = 600  # outfit cue only within +-10 minutes (same look/session)


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


def group(occs: list[Occ], different: set[tuple[int, int]] = frozenset()) -> tuple[list[_Group], dict[int, tuple[int, float]]]:
    """Returns (groups, suggestions) where suggestions maps occ index -> (group index, outfit similarity)."""
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
            owner[i] = len(groups)
        groups.append(g)

    manual: dict[int, list[int]] = defaultdict(list)
    for i, o in enumerate(occs):
        if o.assignment == "manual" and o.subject_id is not None:
            manual[o.subject_id].append(i)
    for subject_id, idx in manual.items():
        new_group(idx, subject_id)
    face_idx = [i for i, o in enumerate(occs) if o.face is not None and o.assignment != "manual"]
    for i in face_idx:
        new_group([i], None)

    # Faces taking part in grouping: manual seeds + free faces. A face the user
    # deliberately left unassigned (manual, no subject) stays out.
    def absorb(keep: int, drop: int) -> None:
        gk, gd = groups[keep], groups[drop]
        for m in gd.members:
            owner[m] = keep
        gk.members += gd.members
        gk.assets |= gd.assets
        gk.prev_subjects.update(gd.prev_subjects)
        gk.excluded |= gd.excluded
        gk.fixed_subject = gk.fixed_subject or gd.fixed_subject
        gd.members, gd.assets = [], set()

    all_face = sorted(i for i in owner if occs[i].face is not None)
    if all_face:
        F = np.stack([occs[i].face for i in all_face])
        S = F @ F.T
        pos = {occ_i: k for k, occ_i in enumerate(all_face)}
        rows, cols = np.nonzero(np.triu(S >= AUTO_PAIR, k=1))
        order = np.argsort(-S[rows, cols], kind="stable")
        for k in order:
            i, j = all_face[rows[k]], all_face[cols[k]]
            gi, gj = owner[i], owner[j]
            if gi == gj:
                continue
            g1, g2 = groups[gi], groups[gj]
            if _conflict(g1, g2, different):
                continue
            f1 = [pos[m] for m in g1.members if m in pos]
            f2 = [pos[m] for m in g2.members if m in pos]
            if float(S[np.ix_(f1, f2)].mean()) < AUTO_AVERAGE:
                continue
            absorb(*((gi, gj) if g2.fixed_subject is None else (gj, gi)))

    # Stability: a group that already belonged to a person the user corrected
    # (merge, manual assignment) stays with that person unless that conflicts.
    fixed_by_subject = {g.fixed_subject: gi for gi, g in enumerate(groups) if g.fixed_subject is not None and g.members}
    for gi, g in enumerate(groups):
        if g.fixed_subject is None and g.members and g.prev_subjects:
            fi = fixed_by_subject.get(g.prev_subjects.most_common(1)[0][0])
            if fi is not None and not _conflict(groups[fi], g, different):
                absorb(fi, gi)

    # Face-less main occurrences: outfit + time window, suggestion only.
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
                if other.outfit is not None and other.time is not None and abs(other.time - o.time) <= OUTFIT_WINDOW_S:
                    best = max(best, float(o.outfit @ other.outfit))
            if best > 0:
                scores[gi] = best
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if ranked and ranked[0][1] >= OUTFIT_SUGGEST and (len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= OUTFIT_MARGIN):
            suggestions[i] = ranked[0]
    return [g for g in groups], suggestions


def recluster(project: Project) -> ClusterReport:
    conn = project.conn
    occs = load_occurrences(conn)
    different = _different_pairs(conn)
    groups, suggestions = group(occs, different)
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
    similarity: float


def merge_suggestions(conn: sqlite3.Connection, limit: int = 50) -> list[Suggestion]:
    """Subject pairs whose closest faces are similar but below the automatic level."""
    by_subject: dict[int, list[np.ndarray]] = defaultdict(list)
    for r in conn.execute(
        """SELECT o.subject_id, v.vector FROM occurrences o JOIN occurrence_vectors v
           ON v.occurrence_id = o.id AND v.kind = 'face' WHERE o.subject_id IS NOT NULL"""
    ):
        by_subject[r[0]].append(np.frombuffer(r[1], dtype="<f4"))
    different = _different_pairs(conn)
    ids = sorted(by_subject)
    mats = {s: np.stack(v) for s, v in by_subject.items()}
    out = []
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            if (a, b) in different:
                continue
            best = float((mats[a] @ mats[b].T).max())
            if best >= SUGGEST:
                out.append(Suggestion(a, b, round(best, 3)))
    return sorted(out, key=lambda s: -s.similarity)[:limit]
