"""View-only rotation ("Xoay xem"): how a photo is turned on screen, per photo, in quarter turns clockwise.

Only the grid, preview and loupe use it. The photo file, the AI measurements and exported copies
never change.
"""

from __future__ import annotations

import sqlite3


def rotation(conn: sqlite3.Connection, asset_id: int) -> int:
    row = conn.execute("SELECT quarter_turns FROM view_rotation WHERE asset_id = ?", (asset_id,)).fetchone()
    return int(row[0]) if row else 0


def rotate(conn: sqlite3.Connection, asset_id: int) -> int:
    """Turn 90° clockwise; returns the new rotation (0..3). A full turn removes the row."""
    turns = (rotation(conn, asset_id) + 1) % 4
    if turns:
        conn.execute("INSERT INTO view_rotation (asset_id, quarter_turns) VALUES (?, ?) "
                     "ON CONFLICT (asset_id) DO UPDATE SET quarter_turns = excluded.quarter_turns", (asset_id, turns))
    else:
        conn.execute("DELETE FROM view_rotation WHERE asset_id = ?", (asset_id,))
    return turns


def rotations(conn: sqlite3.Connection) -> dict[int, int]:
    return {int(a): int(t) for a, t in conn.execute("SELECT asset_id, quarter_turns FROM view_rotation")}


def rotate_point(x: float, y: float, turns: int) -> tuple[float, float]:
    """A point given as 0..1 of the photo file, where it lands on screen after ``turns`` quarter turns clockwise."""
    for _ in range(turns % 4):
        x, y = 1.0 - y, x
    return x, y
