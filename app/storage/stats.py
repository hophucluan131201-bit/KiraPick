"""Counts for the bottom bar and the size of what an export of the kept photos would copy.

Photos are counted the way the grid shows them: a RAW+JPEG pair is one photo, shown (and decided)
through its RAW. Sizes come from the database (no disk access), so the size is an estimate of the
next export: files that went missing since the import are not known here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.export.copy_export import Selection, estimated_bytes, select_ids

# The grid's rule for "one photo": not missing/duplicate, and a JPEG is hidden when its pair group has a RAW.
SHOWN_PHOTO_SQL = """a.status NOT IN ('missing', 'duplicate')
  -- a JPEG that is half of a RAW+JPEG pair is shown through its RAW
  AND NOT (a.media_kind = 'raster' AND a.pair_group_id IS NOT NULL
           AND EXISTS (SELECT 1 FROM assets r WHERE r.pair_group_id = a.pair_group_id AND r.media_kind = 'raw'
                       AND r.status NOT IN ('missing', 'duplicate')))"""


@dataclass(frozen=True, slots=True)
class Counts:
    """Contract: keep / reject count every decision on a shown photo, whatever its read status (the user's
    decision is never hidden); errors is a warning count that may overlap them; undecided = readable photos
    without a decision. So total == keep + reject + undecided + errors without a decision."""

    total: int  # photos shown in the grid (errors included)
    keep: int
    reject: int
    undecided: int  # readable photos with neither Chọn nor Loại
    errors: int  # photos that could not be read
    keep_bytes: int  # what "Xuất ảnh đã Chọn" would copy: app.export.copy_export.export_groups, same files


def counts(conn: sqlite3.Connection, include_pairs: bool) -> Counts:
    """``include_pairs``: the export option "Kèm file JPEG của cặp RAW+JPEG" (the pair's other files count)."""
    row = conn.execute(
        f"""SELECT COUNT(*),
                   COALESCE(SUM(d.flag = 'keep'), 0),
                   COALESCE(SUM(d.flag = 'reject'), 0),
                   COALESCE(SUM(d.flag IS NULL AND a.status = 'ok'), 0),
                   COALESCE(SUM(a.status = 'error'), 0)
            FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
            WHERE {SHOWN_PHOTO_SQL}""").fetchone()
    kept = select_ids(conn, Selection.KEEP)
    return Counts(*(int(v) for v in row), estimated_bytes(conn, kept, include_pairs=include_pairs))
