"""Finished exports of a session: when, how many photos and files. Never where (no destination path)."""

from __future__ import annotations

import sqlite3

from app.storage.project import utc_now


def record(conn: sqlite3.Connection, photos: int, files: int) -> None:
    if files <= 0 or photos <= 0:
        raise ValueError("an export run copies at least one file")
    conn.execute("INSERT INTO export_runs (finished_at, photos, files) VALUES (?, ?, ?)", (utc_now(), photos, files))


def count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0])


def photo_count(conn: sqlite3.Connection, asset_ids: list[int]) -> int:
    """Photos among these files: the RAW and JPEG of one pair are one photo."""
    if not asset_ids:
        return 0
    marks = ",".join("?" * len(asset_ids))
    rows = conn.execute(f"SELECT id, pair_group_id FROM assets WHERE id IN ({marks})", list(asset_ids))
    return len({("pair", g) if g is not None else ("asset", a) for a, g in rows})
