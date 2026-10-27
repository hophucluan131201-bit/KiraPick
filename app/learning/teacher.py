"""Turns the user's people corrections into learning examples.

Called by the UI around the corrections in app.identity.actions. An example is a
pair of occurrences with its face / outfit similarity and time gap, and the
user's answer (same person or not). Learning must never get in the way: any
error here is logged and the correction itself goes ahead.
"""

from __future__ import annotations

import logging
import sqlite3

import numpy as np

from app.identity.cluster import Occ, load_occurrences
from app.identity.features import OUTFIT_VERSION
from app.learning.store import LearningStore, PairEvidence
from app.workers.analyze_job import FACE_VECTOR_VERSION

log = logging.getLogger(__name__)

MAX_PAIRS_PER_ANSWER = 200  # a big merge must not drown the other examples


def _occurrences(conn: sqlite3.Connection, where: str, args: tuple) -> list[Occ]:
    ids = {r[0] for r in conn.execute(f"SELECT id FROM occurrences WHERE {where}", args)}
    return [o for o in load_occurrences(conn) if o.id in ids]


def evidence(a: list[Occ], b: list[Occ], limit: int = MAX_PAIRS_PER_ANSWER) -> list[PairEvidence]:
    """Pairs across the two sets (never two people of one photo), closest in time first."""
    pairs = []
    for x in a:
        for y in b:
            if x.asset_id == y.asset_id or x.id == y.id:
                continue
            dt = abs(x.time - y.time) if x.time is not None and y.time is not None else None
            face = float(x.face @ y.face) if x.face is not None and y.face is not None else None
            outfit = float(x.outfit @ y.outfit) if x.outfit is not None and y.outfit is not None else None
            if face is None and outfit is None:
                continue
            pairs.append(PairEvidence(face, outfit, dt))
    pairs.sort(key=lambda p: np.inf if p.dt_s is None else p.dt_s)
    return pairs[:limit]


class Teacher:
    def __init__(self, store: LearningStore | None) -> None:
        self.store = store

    def _save(self, kind: str, same: bool, pairs: list[PairEvidence]) -> None:
        if self.store is None:
            return
        try:
            self.store.add_identity(kind, same, pairs, FACE_VECTOR_VERSION, OUTFIT_VERSION)
        except Exception:  # noqa: BLE001 - learning is optional
            log.exception("could not save a learning example")

    def _guard(self, kind: str, same: bool, fn) -> None:  # noqa: ANN001
        if self.store is None:
            return
        try:
            pairs = fn()
        except Exception:  # noqa: BLE001
            log.exception("could not compute a learning example")
            return
        self._save(kind, same, pairs)

    def merged(self, conn: sqlite3.Connection, keep: int, drop: int) -> None:
        """Call BEFORE actions.merge_subjects."""
        self._guard("merge", True, lambda: evidence(
            _occurrences(conn, "subject_id = ?", (keep,)), _occurrences(conn, "subject_id = ?", (drop,))))

    def different(self, conn: sqlite3.Connection, a: int, b: int) -> None:
        self._guard("different", False, lambda: evidence(
            _occurrences(conn, "subject_id = ?", (a,)), _occurrences(conn, "subject_id = ?", (b,))))

    def removed(self, conn: sqlite3.Connection, subject_id: int, asset_ids: list[int]) -> None:
        """Call BEFORE actions.remove_photos_from_subject."""
        marks = ",".join("?" * len(asset_ids))
        self._guard("remove", False, lambda: evidence(
            _occurrences(conn, f"subject_id = ? AND asset_id IN ({marks})", (subject_id, *asset_ids)),
            _occurrences(conn, f"subject_id = ? AND asset_id NOT IN ({marks})", (subject_id, *asset_ids))))

    def assigned(self, conn: sqlite3.Connection, subject_id: int, asset_ids: list[int]) -> None:
        """Call AFTER actions.assign_photos_to_subject (the chosen occurrences are known then)."""
        marks = ",".join("?" * len(asset_ids))
        self._guard("assign", True, lambda: evidence(
            _occurrences(conn, f"subject_id = ? AND asset_id IN ({marks})", (subject_id, *asset_ids)),
            _occurrences(conn, f"subject_id = ? AND asset_id NOT IN ({marks})", (subject_id, *asset_ids))))
