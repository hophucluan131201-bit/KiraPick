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


BATCH = 500  # ids per query: far below any SQLite variable limit


def photo_count(conn: sqlite3.Connection, asset_ids: list[int]) -> int:
    """Photos among these files: all files of one RAW+JPEG pair group are one photo.

    Queried in batches; the pair groups are collected across batches, so the two files of a pair
    count once even when they fall into different batches. Duplicate ids count once. An id that is
    not a photo of this session is a caller error (ValueError), never silently dropped."""
    wanted = list(dict.fromkeys(asset_ids))
    photos: set[tuple[str, int]] = set()
    found = 0
    for start in range(0, len(wanted), BATCH):
        chunk = wanted[start:start + BATCH]
        marks = ",".join("?" * len(chunk))
        for a, g in conn.execute(f"SELECT id, pair_group_id FROM assets WHERE id IN ({marks})", chunk):
            photos.add(("pair", g) if g is not None else ("asset", a))
            found += 1
    if found != len(wanted):
        raise ValueError(f"{len(wanted) - found} file(s) are not photos of this session")
    return len(photos)
