"""Turns the user's corrections and choices into learning examples.

- People: called around the corrections in app.identity.actions. An example is
  a pair of occurrences with its face / outfit similarity and time gap, and the
  user's answer (same person or not).
- Taste: the latest Keep/Reject/stars/❤ of each photo (one row per photo) with its score
  parts and CLIP embedding; client picks count lightly (they show the client's taste).

Learning must never get in the way: any error here is logged and the user's
action itself goes ahead.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3

import numpy as np

from app.ai.identity_plus import ARCFACE_VERSION, BODY_VERSION
from app.identity.cluster import Occ, load_occurrences
from app.identity.features import OUTFIT_VERSION
from app.learning.store import LearningStore, PairEvidence
from app.ai.clip_version import CLIP_VERSION
from app.quality.score import PROFILE_VERSION
from app.workers.analyze_job import FACE_VECTOR_VERSION

log = logging.getLogger(__name__)

MAX_PAIRS_PER_ANSWER = 200  # a big merge must not drown the other examples
CLIENT_WEIGHT = 0.3  # a client pick shows what fits the client, not always the best photo
PAIR_WEIGHT = 0.5  # one "which do you prefer" answer, per photo


def photo_key(session: str, asset_id: int, prefix: str = "") -> str:
    """One-way key of a photo in a session (no path or name is stored)."""
    return prefix + hashlib.sha256(f"{session}:{asset_id}".encode()).hexdigest()[:32]


def group_key(session: str, day: str | None) -> str:
    """One-way key of a shoot day: photos of one day are validated together."""
    return hashlib.sha256(f"{session}:{day or ''}".encode()).hexdigest()[:12]


def label_for(flag: str | None, rating: int, favorite: bool) -> tuple[int, float] | None:
    """(label, weight) from the photo's decision, or None when it says nothing about taste.

    Stars and ❤ are the stronger statement and win over Keep/Reject."""
    if favorite or rating >= 4:
        return 1, 1.5
    if rating == 3:
        return 1, 1.0
    if rating == 1:
        return -1, 1.0
    if rating == 2:
        return None
    if flag == "keep":
        return 1, 1.0
    if flag == "reject":
        return -1, 1.0
    return None


def _occurrences(conn: sqlite3.Connection, where: str, args: tuple) -> list[Occ]:
    ids = {r[0] for r in conn.execute(f"SELECT id FROM occurrences WHERE {where}", args)}
    return [o for o in load_occurrences(conn) if o.id in ids]


def _sim(u: np.ndarray | None, v: np.ndarray | None) -> float | None:
    return float(u @ v) if u is not None and v is not None else None


def evidence(a: list[Occ], b: list[Occ], limit: int = MAX_PAIRS_PER_ANSWER) -> list[PairEvidence]:
    """Pairs across the two sets (never two people of one photo), closest in time first."""
    pairs = []
    for x in a:
        for y in b:
            if x.asset_id == y.asset_id or x.id == y.id:
                continue
            dt = abs(x.time - y.time) if x.time is not None and y.time is not None else None
            sface = _sim(x.face_sface, y.face_sface)
            if sface is None and x.face_sface is None and x.face_arc is None:
                sface = _sim(x.face, y.face)  # Occ built by hand (tests): the face it has
            outfit = _sim(x.outfit, y.outfit)
            arc, body = _sim(x.face_arc, y.face_arc), _sim(x.body, y.body)
            if sface is None and outfit is None and arc is None and body is None:
                continue
            pairs.append(PairEvidence(sface, outfit, dt, arc, body))
    pairs.sort(key=lambda p: np.inf if p.dt_s is None else p.dt_s)
    return pairs[:limit]


class Teacher:
    def __init__(self, store: LearningStore | None) -> None:
        self.store = store

    def _save(self, kind: str, same: bool, pairs: list[PairEvidence]) -> None:
        if self.store is None:
            return
        try:
            self.store.add_identity(kind, same, pairs, FACE_VECTOR_VERSION, OUTFIT_VERSION, ARCFACE_VERSION,
                                    BODY_VERSION)
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

    def decided(self, key: str, decision: object, parts: dict[str, float | None], clip: np.ndarray | None,
                group: str, *, source: str = "app", weight_scale: float = 1.0) -> None:
        """The user changed Keep/Reject/stars/❤ of one photo: store (or replace, or drop) its example."""
        if self.store is None:
            return
        try:
            lw = label_for(getattr(decision, "flag", None), getattr(decision, "rating", 0) or 0,
                           bool(getattr(decision, "favorite", False)))
            if lw is None:
                self.store.remove_taste(key)
                return
            self.store.upsert_taste(key, source, lw[0], lw[1] * weight_scale, getattr(decision, "rating", 0) or 0,
                                    group, parts, clip, CLIP_VERSION, PROFILE_VERSION)
        except Exception:  # noqa: BLE001 - learning is optional
            log.exception("could not save a taste example")

    def client_picked(self, key: str, parts: dict[str, float | None], clip: np.ndarray | None, group: str) -> None:
        if self.store is None:
            return
        try:
            self.store.upsert_taste(key, "client", 1, CLIENT_WEIGHT, 0, group, parts, clip, CLIP_VERSION,
                                    PROFILE_VERSION)
        except Exception:  # noqa: BLE001
            log.exception("could not save a client pick")

    def preferred(self, session: str, winner: int, loser: int, clips: dict, parts: dict, groups: dict) -> None:
        """A "which do you prefer" answer: one liked and one not-liked example, half weight each."""
        if self.store is None:
            return
        for asset_id, label in ((winner, 1), (loser, -1)):
            try:
                self.store.upsert_taste(photo_key(session, asset_id, "pair:") + f":{winner}-{loser}", "pair", label,
                                        PAIR_WEIGHT, 0, groups.get(asset_id, ""), parts.get(asset_id, {}),
                                        clips.get(asset_id), CLIP_VERSION, PROFILE_VERSION)
            except Exception:  # noqa: BLE001
                log.exception("could not save a pair answer")
