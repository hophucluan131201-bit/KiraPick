"""Local learning store: numbers from the user's own corrections, across all shoots.

Lives next to the sessions (``%LOCALAPPDATA%\\KiraPick\\learning``),
is never purged with them and is never part of an installer, so every person who
installs the app starts from the defaults and teaches it their own way.

Privacy: only similarity numbers, time gaps and the user's answer are stored — no
images, file names, paths, people names or capture dates.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app import __version__

log = logging.getLogger(__name__)

DB_NAME = "learning.db"
SCHEMA_VERSION = 3
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
    face: float | None
    outfit: float | None
    dt_s: float | None


class LearningStore:
    def __init__(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / DB_NAME
        self.conn = sqlite3.connect(self.path)
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
                self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def add_identity(self, kind: str, same: bool, pairs: list[PairEvidence], face_version: str,
                     outfit_version: str) -> int:
        if not pairs:
            return 0
        today = date.today().isoformat()
        with self.conn:
            self.conn.executemany(
                """INSERT INTO identity_feedback (created_on, app_version, face_version, outfit_version, kind, same,
                   face, outfit, dt_s) VALUES (?,?,?,?,?,?,?,?,?)""",
                [(today, __version__, face_version, outfit_version, kind, int(same),
                  None if p.face is None else round(p.face, 4), None if p.outfit is None else round(p.outfit, 4),
                  None if p.dt_s is None else round(p.dt_s, 1)) for p in pairs],
            )
        return len(pairs)

    def add_culling(self, decision: str, ai_rank: int | None, total: float | None, parts: dict[str, float | None],
                    profile_version: str) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO culling_feedback (created_on, app_version, profile_version, decision, ai_rank, total,
                   focus, face, exposure, framing, eyes) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (date.today().isoformat(), __version__, profile_version, decision, ai_rank, total,
                 parts.get("focus"), parts.get("face"), parts.get("exposure"), parts.get("framing"), parts.get("eyes")),
            )

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
        self.conn.execute("VACUUM")

    def close(self) -> None:
        self.conn.close()
