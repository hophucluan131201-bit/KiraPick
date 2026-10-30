"""The photos of an export with their files, read from the session database only (Part 3 spec §3.1).

A photo is its primary asset (the one the grid shows; the RAW of a RAW+JPEG pair) plus the other readable files of its
pair group. Decisions are the primary's (subject_id NULL). Nothing here touches the disk."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from app.export.formats import file_kind

BATCH = 500  # ids per query


@dataclass(frozen=True, slots=True)
class PhotoFile:
    asset_id: int
    kind: str
    path: Path
    relative_path: str
    source_root: Path
    size: int
    quick_hash: str


@dataclass(frozen=True, slots=True)
class Photo:
    photo_id: int
    stem: str
    files: tuple[PhotoFile, ...]
    capture_time: datetime | None
    subsec: str | None
    camera: str | None
    flag: str | None
    rating: int
    favorite: bool


def _time(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def load_photos(conn: sqlite3.Connection, photo_ids: list[int]) -> list[Photo]:
    """Photos for these ids, in the order asked (each once); ids that are not photos of the session are left out."""
    wanted = list(dict.fromkeys(photo_ids))
    primaries: dict[int, sqlite3.Row] = {}
    for start in range(0, len(wanted), BATCH):
        chunk = wanted[start:start + BATCH]
        for r in conn.execute(
            f"""SELECT a.id, a.relative_path, a.pair_group_id, d.flag, COALESCE(d.rating, 0) AS rating,
                       COALESCE(d.favorite, 0) AS favorite
                FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
                WHERE a.id IN ({','.join('?' * len(chunk))})""", chunk):
            primaries[r["id"]] = r
    out = []
    for photo_id in wanted:
        p = primaries.get(photo_id)
        if p is None:
            continue
        rows = [conn.execute(_FILE_SQL + " WHERE a.id = ? AND a.status = 'ok'", (photo_id,)).fetchone()]
        if p["pair_group_id"] is not None:
            rows += conn.execute(_FILE_SQL + " WHERE a.pair_group_id = ? AND a.id != ? AND a.status = 'ok' "
                                 "ORDER BY a.id", (p["pair_group_id"], photo_id)).fetchall()
        rows = [r for r in rows if r is not None]
        files = tuple(PhotoFile(r["id"], file_kind(r["relative_path"]) or "other",
                                Path(r["root_path"]) / Path(r["relative_path"]), r["relative_path"],
                                Path(r["root_path"]), int(r["size"]), r["quick_hash"]) for r in rows)
        meta = next((r for r in rows if r["capture_time"]), rows[0] if rows else None)
        camera_row = next((r for r in rows if r["make"] or r["model"]), None)
        camera = " ".join(filter(None, [camera_row["make"], camera_row["model"]])) if camera_row else None
        out.append(Photo(photo_id, PurePosixPath(p["relative_path"]).stem, files,
                         _time(meta["capture_time"]) if meta else None, meta["subsec"] if meta else None,
                         camera or None, p["flag"], int(p["rating"]), bool(p["favorite"])))
    return out


_FILE_SQL = """SELECT a.id, a.relative_path, a.size, a.quick_hash, a.capture_time, a.subsec, a.make, a.model,
                      s.root_path
               FROM assets a JOIN sources s ON s.id = a.source_id"""
