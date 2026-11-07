"""Clock offsets per camera source (Media spec §9, plan Mốc 1 M3).

corrected time = assets.capture_time + offset of the photo's source. Nothing is written into the photo, its EXIF or
assets.capture_time. Setting an offset is one undoable action; its consequences on moments (re-split, ⚠ drift
warnings) are added to the same action by app.media.moments.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.media import journal
from app.media.journal import Scope
from app.storage.project import Project


def offset(conn: sqlite3.Connection, camera_id: int) -> float:
    row = conn.execute("SELECT seconds FROM clock_offsets WHERE camera_id = ?", (camera_id,)).fetchone()
    return 0.0 if row is None else float(row[0])


def _ts(value: str | None) -> float | None:
    return datetime.fromisoformat(value).timestamp() if value else None


def corrected_times(conn: sqlite3.Connection) -> dict[int, float | None]:
    """Asset id -> corrected capture time (POSIX seconds), None when the photo has no time."""
    rows = conn.execute(
        """SELECT a.id, a.capture_time, COALESCE(o.seconds, 0) AS off FROM assets a
           LEFT JOIN asset_source s ON s.asset_id = a.id LEFT JOIN clock_offsets o ON o.camera_id = s.camera_id
           WHERE a.status = 'ok'""").fetchall()
    out = {}
    for r in rows:
        t = _ts(r["capture_time"])
        out[int(r["id"])] = None if t is None else t + float(r["off"])
    return out


def offset_from_pair(conn: sqlite3.Connection, reference_asset: int, adjusted_asset: int) -> float:
    """Seconds to add to ``adjusted_asset``'s camera so both photos show the same time ('chụp cùng lúc')."""
    times = corrected_times(conn)
    ref, adj = times.get(reference_asset), times.get(adjusted_asset)
    if ref is None or adj is None:
        raise ValueError("một trong hai ảnh không có giờ chụp")
    camera = conn.execute("SELECT camera_id FROM asset_source WHERE asset_id = ?", (adjusted_asset,)).fetchone()[0]
    return offset(conn, camera) + (ref - adj)


def clock_scopes(camera_id: int) -> list[Scope]:
    return [Scope("clock_offsets", "camera_id = ?", (camera_id,))]


def set_offset(event: Project, camera_id: int, seconds: float, *, extra_scopes: list[Scope] | None = None,
               after=None) -> None:  # noqa: ANN001 - after: callable(conn) run in the same undoable action
    """Set the offset of one source (one Ctrl+Z restores the old offset and whatever ``after`` changed)."""

    def action(conn: sqlite3.Connection) -> None:
        if seconds:
            conn.execute("""INSERT INTO clock_offsets (camera_id, seconds) VALUES (?, ?)
                            ON CONFLICT (camera_id) DO UPDATE SET seconds = excluded.seconds""", (camera_id, seconds))
        else:
            conn.execute("DELETE FROM clock_offsets WHERE camera_id = ?", (camera_id,))
        if after is not None:
            after(conn)

    journal.run(event, f"chỉnh giờ nguồn {camera_id}", clock_scopes(camera_id) + list(extra_scopes or []), action)
