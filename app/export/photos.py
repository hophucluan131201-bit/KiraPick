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


def _kind(media_kind: str, relative_path: str) -> str:
    """The import's media kind decides RAW; among rasters the extension tells JPEG from other."""
    if media_kind == "raw":
        return "raw"
    return "jpeg" if file_kind(relative_path) == "jpeg" else "other"


def _time(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def load_photos(conn: sqlite3.Connection, photo_ids: list[int]) -> list[Photo]:
    """Photos for these ids, in the order asked (each once); ids that are not photos of the session are left out.

    Queried in batches (the bottom bar runs this for every kept photo after each P / X: one query per photo was the
    Part 3 slowdown measured in beta readiness BR-02)."""
    wanted = list(dict.fromkeys(photo_ids))
    primaries: dict[int, sqlite3.Row] = {}
    files: dict[int, sqlite3.Row] = {}
    for start in range(0, len(wanted), BATCH):
        chunk = wanted[start:start + BATCH]
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(
            f"""SELECT a.id, a.relative_path, a.pair_group_id, d.flag, COALESCE(d.rating, 0) AS rating,
                       COALESCE(d.favorite, 0) AS favorite
                FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
                WHERE a.id IN ({marks})""", chunk):
            primaries[r["id"]] = r
        for r in conn.execute(_FILE_SQL + f" WHERE a.id IN ({marks})", chunk):
            files[r["id"]] = r
    groups = list(dict.fromkeys(p["pair_group_id"] for p in primaries.values() if p["pair_group_id"] is not None))
    partners: dict[int, list[sqlite3.Row]] = {}
    for start in range(0, len(groups), BATCH):
        chunk = groups[start:start + BATCH]
        for r in conn.execute(_FILE_SQL + f" WHERE a.pair_group_id IN ({','.join('?' * len(chunk))}) "
                              "AND a.status = 'ok' ORDER BY a.id", chunk):
            partners.setdefault(r["pair_group_id"], []).append(r)
    out = []
    for photo_id in wanted:
        p = primaries.get(photo_id)
        if p is None:
            continue
        # The photo's own file whatever its read status (as the export before Part 3: an unreadable file is still
        # copied); the other files of its pair group only when readable.
        rows = [files[photo_id]] if photo_id in files else []
        if p["pair_group_id"] is not None:
            rows += [r for r in partners.get(p["pair_group_id"], ()) if r["id"] != photo_id]
        files_of = tuple(PhotoFile(r["id"], _kind(r["media_kind"], r["relative_path"]),
                                   Path(r["root_path"]) / Path(r["relative_path"]), r["relative_path"],
                                   Path(r["root_path"]), int(r["size"]), r["quick_hash"]) for r in rows)
        meta = next((r for r in rows if r["capture_time"]), rows[0] if rows else None)
        camera_row = next((r for r in rows if r["make"] or r["model"]), None)
        camera = " ".join(filter(None, [camera_row["make"], camera_row["model"]])) if camera_row else None
        out.append(Photo(photo_id, PurePosixPath(p["relative_path"]).stem, files_of,
                         _time(meta["capture_time"]) if meta else None, meta["subsec"] if meta else None,
                         camera or None, p["flag"], int(p["rating"]), bool(p["favorite"])))
    return out


_FILE_SQL = """SELECT a.id, a.relative_path, a.media_kind, a.size, a.quick_hash, a.capture_time, a.subsec, a.make, a.model,
                      a.pair_group_id, s.root_path
               FROM assets a JOIN sources s ON s.id = a.source_id"""
