"""Counts for the bottom bar and the size of what an export of the kept photos would copy.

Photos are counted the way the grid shows them: a RAW+JPEG pair is one photo, shown (and decided)
through its RAW. Sizes come from the database (no disk access), so the size is an estimate of the
next export: files that went missing since the import are not known here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# The grid's rule for "one photo": not missing/duplicate, and a JPEG is hidden when its pair group has a RAW.
SHOWN_PHOTO_SQL = """a.status NOT IN ('missing', 'duplicate')
  -- a JPEG that is half of a RAW+JPEG pair is shown through its RAW
  AND NOT (a.media_kind = 'raster' AND a.pair_group_id IS NOT NULL
           AND EXISTS (SELECT 1 FROM assets r WHERE r.pair_group_id = a.pair_group_id AND r.media_kind = 'raw'
                       AND r.status NOT IN ('missing', 'duplicate')))"""


@dataclass(frozen=True, slots=True)
class Counts:
    total: int  # photos shown in the grid (errors included)
    keep: int
    reject: int
    undecided: int  # readable photos with neither Chọn nor Loại
    errors: int  # photos that could not be read
    keep_bytes: int  # files an export of the kept photos would copy


def counts(conn: sqlite3.Connection, include_pairs: bool) -> Counts:
    """``include_pairs``: the export option "Kèm file JPEG của cặp RAW+JPEG" (the pair's other files count)."""
    row = conn.execute(
        f"""SELECT COUNT(*),
                   COALESCE(SUM(d.flag = 'keep'), 0),
                   COALESCE(SUM(d.flag = 'reject'), 0),
                   COALESCE(SUM(d.flag IS NULL AND a.status = 'ok'), 0),
                   COALESCE(SUM(a.status = 'error'), 0),
                   COALESCE(SUM(CASE WHEN d.flag = 'keep' THEN a.size
                                     + CASE WHEN :pairs AND a.pair_group_id IS NOT NULL THEN
                                         (SELECT COALESCE(SUM(m.size), 0) FROM assets m
                                          WHERE m.pair_group_id = a.pair_group_id AND m.id != a.id
                                            AND m.status = 'ok')
                                       ELSE 0 END
                                ELSE 0 END), 0)
            FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
            WHERE {SHOWN_PHOTO_SQL}""", {"pairs": int(include_pairs)}).fetchone()
    return Counts(*(int(v) for v in row))
