"""Best-shot selection: N good photos that are not near-copies of each other.

Greedy maximal marginal relevance (spec 4.6): at each step take the photo with
the best ``LAMBDA * quality - (1 - LAMBDA) * similarity to what is already
chosen``. Similarity = silhouette/framing layout (HOG of the person's box) and
burst membership (same person a moment apart). This never changes the quality
score itself; it only decides the order of picking.

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

LAMBDA = 0.5
BURST_S = 1.5  # photos of one person closer than this are one burst
BURST_SIMILARITY = 0.95
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
    sim = 0.0
    if a.layout is not None and b.layout is not None and len(a.layout) == len(b.layout):
        sim = max(0.0, float(a.layout @ b.layout))
    if a.time is not None and b.time is not None and abs(a.time - b.time) <= BURST_S:
        sim = max(sim, BURST_SIMILARITY)
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
