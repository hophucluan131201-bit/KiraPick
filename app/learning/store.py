"""Local learning store: numbers from the user's own corrections, across all shoots.

Lives next to the sessions (``%LOCALAPPDATA%\\KiraPick\\learning``),
is never purged with them and is never part of an installer, so every person who
installs the app starts from the defaults and teaches it their own way.

Privacy: only similarity numbers, time gaps, score parts, the user's answer and (v6) the
photo's CLIP embedding (768 numbers, needed to learn taste) and (v7) the camera + lens model
names with the sharpness measurements of labelled photos are stored — no images, file names,
paths, people names or capture dates. Photos and shoot days appear only as one-way hashes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from app import __version__
from app.learning.focus import FocusExample
from app.learning.taste import TasteExample

log = logging.getLogger(__name__)

DB_NAME = "learning.db"
SCHEMA_VERSION = 7
# v7: learned sharpness: one row per photo, the user's Q/W/R label with the sharpness measurements
# and the camera + lens it applies to (model names only).
_SCHEMA_V7 = """
CREATE TABLE focus_feedback (
    id              INTEGER PRIMARY KEY,
    photo_key       TEXT NOT NULL UNIQUE,
    created_on      TEXT NOT NULL,          -- day only
    app_version     TEXT NOT NULL,
    camera          TEXT NOT NULL,          -- "make model + lens"
    grp             TEXT NOT NULL,          -- hashed shoot day
    label           INTEGER NOT NULL CHECK (label IN (0, 1, 2)),
    features        TEXT NOT NULL           -- JSON of the sharpness measurements
);
"""
# v6: taste learning: one row per photo (photo_key, upserted), label/weight from Keep/Reject/stars/❤,
# client picks and pair answers; the photo's CLIP embedding; a hashed shoot-day group for validation.
_SCHEMA_V6 = """
ALTER TABLE culling_feedback ADD COLUMN photo_key TEXT;
ALTER TABLE culling_feedback ADD COLUMN source TEXT;
ALTER TABLE culling_feedback ADD COLUMN label INTEGER;
ALTER TABLE culling_feedback ADD COLUMN weight REAL;
ALTER TABLE culling_feedback ADD COLUMN stars INTEGER;
ALTER TABLE culling_feedback ADD COLUMN grp TEXT;
ALTER TABLE culling_feedback ADD COLUMN clip BLOB;
ALTER TABLE culling_feedback ADD COLUMN clip_version TEXT;
CREATE UNIQUE INDEX culling_feedback_photo ON culling_feedback (photo_key) WHERE photo_key IS NOT NULL;
"""
# v5: every identity cue is stored (SFace, ArcFace, outfit colours, whole-body ReID), so
# a later face model does not throw away what was learnt; pairs of one answer share answer_id.
_SCHEMA_V5 = """
ALTER TABLE identity_feedback ADD COLUMN answer_id INTEGER;
ALTER TABLE identity_feedback ADD COLUMN face_arc REAL;
ALTER TABLE identity_feedback ADD COLUMN arc_version TEXT;
ALTER TABLE identity_feedback ADD COLUMN body REAL;
ALTER TABLE identity_feedback ADD COLUMN body_version TEXT;
"""
_SCHEMA_V4 = "ALTER TABLE culling_feedback ADD COLUMN aesthetic REAL;"  # aesthetic hint score
_SCHEMA_V3 = "ALTER TABLE culling_feedback ADD COLUMN eyes REAL;"  # eyes open/closed score
_SCHEMA_V2 = """
CREATE TABLE culling_feedback (
    id              INTEGER PRIMARY KEY,
    created_on      TEXT NOT NULL,          -- day only
    app_version     TEXT NOT NULL,
    profile_version TEXT NOT NULL,          -- rubric the scores come from
    decision        TEXT NOT NULL CHECK (decision IN ('keep', 'reject')),
    ai_rank         INTEGER,                -- the AI had picked it (rank), NULL = not picked
    total           REAL,
    focus           REAL,
    face            REAL,
    exposure        REAL,
    framing         REAL
);
"""
_SCHEMA = """
CREATE TABLE identity_feedback (
    id              INTEGER PRIMARY KEY,
    created_on      TEXT NOT NULL,          -- day only
    app_version     TEXT NOT NULL,
    face_version    TEXT NOT NULL,          -- vectors the numbers come from
    outfit_version  TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('merge', 'different', 'remove', 'assign')),
    same            INTEGER NOT NULL CHECK (same IN (0, 1)),
    face            REAL,                   -- face similarity, NULL if a face is missing
    outfit          REAL,                   -- outfit similarity
    dt_s            REAL                    -- seconds between the two photos
);
"""


@dataclass(frozen=True, slots=True)
class PairEvidence:
    face: float | None  # SFace similarity
    outfit: float | None  # outfit-colour similarity
    dt_s: float | None
    face_arc: float | None = None  # ArcFace similarity (optional model)
    body: float | None = None  # whole-body ReID similarity (optional model)


@dataclass(frozen=True, slots=True)
class CueVersions:
    face: str
    outfit: str
    arc: str
    body: str


@dataclass(frozen=True, slots=True)
class IdentityExample:
    answer: int  # pairs with the same number come from one correction
    same: bool
    pair: PairEvidence
    versions: CueVersions


class LearningStore:
    def __init__(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / DB_NAME
        self.conn = sqlite3.connect(self.path)
        # Like the session databases: a write-ahead log and no disk flush per commit. Each Chọn / Loại writes one
        # example here on the GUI thread; with SQLite's defaults (rollback journal, a full flush per commit) that
        # took 20+ ms on Windows (Task 14 benchmark). A power cut can lose the last examples, never corrupt the file.
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"learning data is from a newer app version ({version})")
        if version < SCHEMA_VERSION:
            with self.conn:  # one transaction: an upgrade is all or nothing
                if version < 1:
                    self.conn.executescript(_SCHEMA.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))
                if version < 2:
                    self.conn.executescript(_SCHEMA_V2)
                if version < 3:
                    self.conn.executescript(_SCHEMA_V3)
                if version < 4:
                    self.conn.executescript(_SCHEMA_V4)
                if version < 5:
                    self.conn.executescript(_SCHEMA_V5)
                if version < 6:
                    self.conn.executescript(_SCHEMA_V6)
                if version < 7:
                    self.conn.executescript(_SCHEMA_V7)
                self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def add_identity(self, kind: str, same: bool, pairs: list[PairEvidence], face_version: str,
                     outfit_version: str, arc_version: str = "", body_version: str = "") -> int:
        if not pairs:
            return 0
        today = date.today().isoformat()
        r = lambda v, n=4: None if v is None else round(v, n)  # noqa: E731
        with self.conn:
            answer = self.conn.execute("SELECT COALESCE(MAX(answer_id), 0) + 1 FROM identity_feedback").fetchone()[0]
            self.conn.executemany(
                """INSERT INTO identity_feedback (created_on, app_version, face_version, outfit_version, kind, same,
                   face, outfit, dt_s, answer_id, face_arc, arc_version, body, body_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(today, __version__, face_version, outfit_version, kind, int(same), r(p.face), r(p.outfit),
                  r(p.dt_s, 1), answer, r(p.face_arc), arc_version if p.face_arc is not None else None,
                  r(p.body), body_version if p.body is not None else None) for p in pairs],
            )
        return len(pairs)

    def identity_examples(self, limit: int = 20000) -> list[IdentityExample]:
        """The most recent people examples. Rows from before v5 count one answer per day and kind."""
        rows = self.conn.execute(
            """SELECT answer_id, created_on, kind, same, face, outfit, dt_s, face_arc, body,
                      face_version, outfit_version, arc_version, body_version
               FROM identity_feedback ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
        old_answers: dict[tuple, int] = {}
        out = []
        for (answer, day, kind, same, face, outfit, dt, arc, body, fv, ov, av, bv) in rows:
            if answer is None:
                answer = old_answers.setdefault((day, kind, same), -1 - len(old_answers))
            out.append(IdentityExample(answer, bool(same), PairEvidence(face, outfit, dt, arc, body),
                                       CueVersions(fv, ov, av or "", bv or "")))
        return out

    def add_culling(self, decision: str, ai_rank: int | None, total: float | None, parts: dict[str, float | None],
                    profile_version: str) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO culling_feedback (created_on, app_version, profile_version, decision, ai_rank, total,
                   focus, face, exposure, framing, eyes, aesthetic) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (date.today().isoformat(), __version__, profile_version, decision, ai_rank, total,
                 parts.get("focus"), parts.get("face"), parts.get("exposure"), parts.get("framing"), parts.get("eyes"),
                 parts.get("aesthetic")),
            )

    def upsert_taste(self, photo_key: str, source: str, label: int, weight: float, stars: int, group: str,
                     parts: dict[str, float | None], clip: np.ndarray | None, clip_version: str | None,
                     profile_version: str) -> None:
        """The newest answer about one photo replaces the earlier one."""
        blob = None if clip is None else np.asarray(clip, "<f2").tobytes()
        p = {k: parts.get(k) for k in ("focus", "face", "exposure", "framing", "eyes", "aesthetic")}
        with self.conn:
            self.conn.execute(
                """INSERT INTO culling_feedback (created_on, app_version, profile_version, decision, focus, face,
                   exposure, framing, eyes, aesthetic, photo_key, source, label, weight, stars, grp, clip,
                   clip_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (photo_key) WHERE photo_key IS NOT NULL DO UPDATE SET
                   created_on = excluded.created_on, app_version = excluded.app_version,
                   profile_version = excluded.profile_version, decision = excluded.decision,
                   focus = excluded.focus, face = excluded.face, exposure = excluded.exposure,
                   framing = excluded.framing, eyes = excluded.eyes, aesthetic = excluded.aesthetic,
                   source = excluded.source, label = excluded.label, weight = excluded.weight,
                   stars = excluded.stars, grp = excluded.grp, clip = excluded.clip,
                   clip_version = excluded.clip_version""",
                (date.today().isoformat(), __version__, profile_version, "keep" if label > 0 else "reject",
                 p["focus"], p["face"], p["exposure"], p["framing"], p["eyes"], p["aesthetic"], photo_key, source,
                 label, weight, stars, group, blob, clip_version if clip is not None else None),
            )

    def remove_taste(self, photo_key: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM culling_feedback WHERE photo_key = ?", (photo_key,))

    def taste_examples(self, clip_version: str, limit: int = 20000) -> list[TasteExample]:
        """Newest first. Rows from before v6 count as label from Keep/Reject, weight 1, no CLIP vector."""
        rows = self.conn.execute(
            """SELECT label, decision, weight, COALESCE(grp, created_on), clip, clip_version,
                      focus, face, exposure, framing, eyes, aesthetic
               FROM culling_feedback ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
        out = []
        for label, decision, weight, group, blob, cv, *vals in rows:
            if label is None:
                label = 1 if decision == "keep" else -1
            clip = None
            if blob is not None and cv == clip_version:
                clip = np.frombuffer(blob, "<f2").astype(np.float32)
            parts = dict(zip(("focus", "face", "exposure", "framing", "eyes", "aesthetic"), vals, strict=True))
            out.append(TasteExample(int(label), 1.0 if weight is None else float(weight), str(group), clip, parts))
        return out

    def upsert_focus(self, photo_key: str, camera: str, group: str, label: int,
                     features: dict[str, float | None]) -> None:
        values = {k: (None if v is None else round(float(v), 5)) for k, v in features.items()}
        with self.conn:
            self.conn.execute(
                """INSERT INTO focus_feedback (photo_key, created_on, app_version, camera, grp, label, features)
                   VALUES (?,?,?,?,?,?,?) ON CONFLICT (photo_key) DO UPDATE SET
                   created_on = excluded.created_on, app_version = excluded.app_version, camera = excluded.camera,
                   grp = excluded.grp, label = excluded.label, features = excluded.features""",
                (photo_key, date.today().isoformat(), __version__, camera, group, int(label), json.dumps(values)))

    def remove_focus(self, photo_key: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM focus_feedback WHERE photo_key = ?", (photo_key,))

    def focus_examples(self, limit: int = 20000) -> list[FocusExample]:
        rows = self.conn.execute(
            "SELECT label, grp, camera, features FROM focus_feedback ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [FocusExample(int(label), grp, camera, json.loads(feats)) for label, grp, camera, feats in rows]

    def culling_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM culling_feedback").fetchone()[0]

    def identity_counts(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT same, COUNT(*) FROM identity_feedback GROUP BY same").fetchall()
        counts = {"same": 0, "different": 0}
        for same, n in rows:
            counts["same" if same else "different"] = n
        return counts

    def forget(self) -> None:
        """Back to the defaults: delete everything learnt."""
        with self.conn:
            self.conn.execute("DELETE FROM identity_feedback")
            self.conn.execute("DELETE FROM culling_feedback")
            self.conn.execute("DELETE FROM focus_feedback")
        self.conn.execute("VACUUM")

    def close(self) -> None:
        self.conn.close()
