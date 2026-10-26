"""Manual culling decisions (keep/reject, stars, favorite).

Whole-photo decisions use ``subject_id = None``; per-subject decisions arrive
with M2. Decisions are user data: re-imports and re-analysis never touch them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from app.storage.project import utc_now

Flag = Literal["keep", "reject"] | None


@dataclass(frozen=True, slots=True)
class Decision:
    flag: Flag = None
    rating: int = 0
    favorite: bool = False


def get(conn: sqlite3.Connection, asset_id: int) -> Decision:
    row = conn.execute(
        "SELECT flag, rating, favorite FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (asset_id,)
    ).fetchone()
    return Decision(row["flag"], row["rating"], bool(row["favorite"])) if row else Decision()


def _upsert(conn: sqlite3.Connection, asset_id: int, column: str, value: object) -> None:
    # column is chosen from a fixed set by the public functions below.
    conn.execute(
        f"""INSERT INTO decisions (asset_id, subject_id, {column}, updated_at) VALUES (?, NULL, ?, ?)
            ON CONFLICT (asset_id) WHERE subject_id IS NULL
            DO UPDATE SET {column} = excluded.{column}, updated_at = excluded.updated_at""",
        (asset_id, value, utc_now()),
    )


def set_flag(conn: sqlite3.Connection, asset_id: int, flag: Flag) -> None:
    if flag not in ("keep", "reject", None):
        raise ValueError(f"invalid flag {flag!r}")
    _upsert(conn, asset_id, "flag", flag)


def set_rating(conn: sqlite3.Connection, asset_id: int, rating: int) -> None:
    if not 0 <= rating <= 5:
        raise ValueError("rating must be 0..5")
    _upsert(conn, asset_id, "rating", rating)


def set_favorite(conn: sqlite3.Connection, asset_id: int, favorite: bool) -> None:
    _upsert(conn, asset_id, "favorite", int(favorite))
