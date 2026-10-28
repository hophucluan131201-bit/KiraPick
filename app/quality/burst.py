"""The burst of a photo: photos of the same person taken a few seconds before or after it ("Ảnh tương tự").

Uses only what import and people recognition stored (capture time with sub-seconds, subject of the photo's
main person); nothing is computed from pixels here.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from app.storage.stats import SHOWN_PHOTO_SQL

WINDOW_S = 3.0


def _moment(capture_time: str | None, subsec: str | None) -> datetime | None:
    if not capture_time:
        return None
    try:
        t = datetime.fromisoformat(capture_time)
    except ValueError:
        return None
    digits = (subsec or "").strip()  # EXIF text may be space-padded
    if digits.isdigit():
        t += timedelta(seconds=float("0." + digits))
    return t


def _main_subject(conn: sqlite3.Connection, asset_id: int) -> int | None:
    row = conn.execute("""SELECT subject_id FROM occurrences WHERE asset_id = ? AND is_main = 1
                          ORDER BY prominence DESC LIMIT 1""", (asset_id,)).fetchone()
    return row[0] if row else None


def neighbours(conn: sqlite3.Connection, asset_id: int, window_s: float = WINDOW_S) -> list[int]:
    """Photos within ±window_s of this one, of the same subject as its main person (any photo when it has
    no recognised person), as the grid shows them (one per RAW+JPEG pair), oldest first, itself excluded."""
    row = conn.execute("SELECT capture_time, subsec FROM assets WHERE id = ?", (asset_id,)).fetchone()
    t = _moment(row[0], row[1]) if row else None
    if t is None:
        return []
    subject = _main_subject(conn, asset_id)
    # Whole-second string range on the indexed column first, then the exact window in Python.
    lo = (t - timedelta(seconds=window_s + 1)).replace(microsecond=0).isoformat()
    hi = (t + timedelta(seconds=window_s + 1)).replace(microsecond=0).isoformat()
    sql = f"""SELECT a.id, a.capture_time, a.subsec FROM assets a
              WHERE a.capture_time BETWEEN ? AND ? AND a.id != ? AND {SHOWN_PHOTO_SQL}"""
    args: list = [lo, hi, asset_id]
    if subject is not None:
        sql += " AND a.id IN (SELECT asset_id FROM occurrences WHERE subject_id = ?)"
        args.append(subject)
    found = []
    for other, when, sub in conn.execute(sql, args):
        m = _moment(when, sub)
        if m is not None and abs((m - t).total_seconds()) <= window_s + 1e-6:
            found.append((m, other))
    return [other for _, other in sorted(found)]
