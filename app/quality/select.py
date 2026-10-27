"""Best-shot selection: N good photos that are not near-copies of each other.

Greedy maximal marginal relevance (spec 4.6): at each step take the photo with
the best ``LAMBDA * quality - (1 - LAMBDA) * redundancy with what is already
chosen``. Redundancy comes from the silhouette/framing layout (HOG of the
person's box) and burst membership (same person a moment apart), rescaled so
that only near-copies count: on the owner's shoot, burst frames ≤ 1.5 s apart
had layout similarity median 0.98 (p5 0.89), while different poses of one look
were already at median 0.87 — a raw similarity would punish real pose changes
and over-reward a mere portrait/landscape change. A near-copy costs about 33
points, so a clearly better photo still wins over a different but much worse
one. This never changes the quality score itself; it only decides the order.

Per person: every person gets their own N (a crowded look cannot crowd out a
person with few photos); a photo with two people can be chosen for each.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from app.quality.score import Score, photo_scores
from app.storage.project import utc_now

LAMBDA = 0.75
BURST_S = 1.5  # photos of one person closer than this are one burst
SIMILAR_FROM = 0.85  # layout similarity at/below this: different enough, no penalty
SIMILAR_FULL = 0.97  # at/above this: a near-copy (full penalty)
MIN_SCORE = 0.0  # every scored photo can be picked; the order does the work


@dataclass(slots=True)
class Candidate:
    asset_id: int
    occurrence_id: int
    score: Score
    time: float | None
    layout: np.ndarray | None


@dataclass(slots=True)
class Pick:
    asset_id: int
    subject_id: int | None
    rank: int
    score: float
    reason: dict


def similarity(a: Candidate, b: Candidate) -> float:
    """Redundancy 0..1: 0 = clearly another pose/framing, 1 = near-copy or same burst."""
    sim = 0.0
    if a.layout is not None and b.layout is not None and len(a.layout) == len(b.layout):
        raw = float(a.layout @ b.layout)
        sim = max(0.0, min(1.0, (raw - SIMILAR_FROM) / (SIMILAR_FULL - SIMILAR_FROM)))
    if a.time is not None and b.time is not None and abs(a.time - b.time) <= BURST_S:
        sim = 1.0
    return sim


def choose(candidates: list[Candidate], n: int, lam: float = LAMBDA) -> list[tuple[Candidate, float]]:
    """Greedy MMR. Returns (candidate, max similarity to earlier picks) in pick order."""
    pool = [c for c in candidates if c.score.total is not None]
    chosen: list[tuple[Candidate, float]] = []
    max_sim = {id(c): 0.0 for c in pool}
    while pool and len(chosen) < n:
        best = max(pool, key=lambda c: (lam * c.score.total / 100 - (1 - lam) * max_sim[id(c)], c.score.total))
        chosen.append((best, max_sim[id(best)]))
        pool.remove(best)
        for c in pool:
            max_sim[id(c)] = max(max_sim[id(c)], similarity(c, best))
    return chosen


def _candidates(conn: sqlite3.Connection, subject_id: int | None, asset_ids: set[int] | None) -> list[Candidate]:
    scored = photo_scores(conn, subject_id)
    if asset_ids is not None:
        scored = {a: v for a, v in scored.items() if a in asset_ids}
    if not scored:
        return []
    occ_ids = [occ for occ, _ in scored.values()]
    marks = ",".join("?" * len(occ_ids))
    layouts = {r[0]: np.frombuffer(r[1], "<f4") for r in conn.execute(
        f"SELECT occurrence_id, vector FROM occurrence_vectors WHERE kind = 'layout' AND occurrence_id IN ({marks})",
        occ_ids)}
    times = {r[0]: r[1] for r in conn.execute(
        f"SELECT id, capture_time FROM assets WHERE id IN ({','.join('?' * len(scored))})", list(scored))}
    return [Candidate(a, occ, s, datetime.fromisoformat(times[a]).timestamp() if times.get(a) else None,
                      layouts.get(occ)) for a, (occ, s) in scored.items()]


def _picks(chosen: list[tuple[Candidate, float]], subject_id: int | None) -> list[Pick]:
    out = []
    for rank, (c, sim) in enumerate(chosen, 1):
        out.append(Pick(c.asset_id, subject_id, rank, c.score.total or 0.0, {
            "score": c.score.total, "parts": c.score.parts, "warnings": c.score.warnings,
            "similar_to_earlier": round(sim, 3),
        }))
    return out


def select_per_person(conn: sqlite3.Connection, n: int, asset_ids: set[int] | None = None) -> list[Pick]:
    picks: list[Pick] = []
    for (sid,) in conn.execute("SELECT id FROM subjects ORDER BY id").fetchall():
        picks += _picks(choose(_candidates(conn, sid, asset_ids), n), sid)
    return picks


def select_in_view(conn: sqlite3.Connection, n: int, asset_ids: set[int], subject_id: int | None = None) -> list[Pick]:
    return _picks(choose(_candidates(conn, subject_id, asset_ids), n), subject_id)


def save_run(conn: sqlite3.Connection, picks: list[Pick], params: dict) -> int:
    """The newest selection replaces the previous one (decisions are not touched here)."""
    conn.execute("DELETE FROM pick_runs")
    run_id = int(conn.execute("INSERT INTO pick_runs (created_at, params_json) VALUES (?, ?)",
                              (utc_now(), json.dumps(params))).lastrowid)
    seen: set[int] = set()
    for p in picks:
        if p.asset_id in seen:  # chosen for two people: keep the first (best rank) row
            continue
        seen.add(p.asset_id)
        conn.execute("""INSERT INTO picks (run_id, asset_id, subject_id, rank, score, reason_json)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (run_id, p.asset_id, p.subject_id, p.rank, p.score, json.dumps(p.reason)))
    return run_id


def clear_picks(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM pick_runs")


def why_not_picked(conn: sqlite3.Connection, asset_id: int) -> str | None:
    """For a scored photo the last selection did not choose: the most likely reason, in plain words."""
    run = conn.execute("SELECT params_json FROM pick_runs").fetchone()
    if run is None or conn.execute("SELECT 1 FROM picks WHERE asset_id = ?", (asset_id,)).fetchone():
        return None
    params = json.loads(run[0])
    subjects = [r[0] for r in conn.execute(
        "SELECT DISTINCT subject_id FROM occurrences WHERE asset_id = ? AND subject_id IS NOT NULL", (asset_id,))]
    subject = params.get("subject_id") if params.get("mode") == "in_view" else (subjects[0] if subjects else None)
    if params.get("mode") == "per_person" and subject is None:
        return "Không được chọn: chưa thuộc chủ thể nào (Chưa xác định)."
    picked = [r[0] for r in conn.execute(
        "SELECT asset_id FROM picks WHERE subject_id IS ?" if subject is None else
        "SELECT asset_id FROM picks WHERE subject_id = ?", (subject,))]
    cands = {c.asset_id: c for c in _candidates(conn, subject, set(picked) | {asset_id})}
    me = cands.get(asset_id)
    if me is None or me.score.total is None:
        return None
    nearest = max((c for a, c in cands.items() if a != asset_id), key=lambda c: similarity(me, c), default=None)
    if nearest is not None and similarity(me, nearest) >= 0.5:
        name = conn.execute("SELECT relative_path FROM assets WHERE id = ?", (nearest.asset_id,)).fetchone()[0]
        better = "điểm cao hơn" if (nearest.score.total or 0) >= me.score.total else "đã được chọn trước"
        return (f"Không được chọn: gần giống {name.rsplit('/', 1)[-1]} ({better}) — "
                "cùng dáng/khung hoặc chụp liên tiếp.")
    return (f"Không được chọn: đã đủ {params.get('n')} ảnh"
            + (" cho chủ thể này" if params.get("mode") == "per_person" else "")
            + ", các ảnh được chọn có điểm cao hơn hoặc khác dáng hơn.")


def pick_reason(reason_json: str | None, rank: int) -> str:
    if rank == 1:
        return "điểm cao nhất"
    sim = json.loads(reason_json or "{}").get("similar_to_earlier", 0) or 0
    return "điểm cao và khác dáng với các ảnh đã chọn" if sim < 0.5 else "điểm cao (dáng hơi giống một ảnh đã chọn)"
