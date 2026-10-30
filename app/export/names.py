"""The names of the kept photos, for pasting into a message or another program (Part 3 spec §3.8, CR-P3-04).

Database only: works without a destination, without the other folder, with the card disconnected, and does not depend
on the export's Source / Format / Layout choices."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from app.export.photos import Photo, load_photos


@dataclass(frozen=True, slots=True)
class NameList:
    lines: list[str]  # one per photo, identical lines once
    photos: int  # kept photos in the scope
    shared_stems: dict[str, int]  # a base name shared by several different photos -> how many


def _name(photo: Photo) -> str:
    """The file the grid shows for the photo: the RAW of a RAW+JPEG pair, else the photo's own file."""
    raw = next((f for f in photo.files if f.kind == "raw"), None)
    return PurePosixPath((raw or photo.files[0]).relative_path).name


def keep_names(conn: sqlite3.Connection, photo_ids: list[int], *, with_extension: bool) -> NameList:
    """The kept photos among ``photo_ids`` (scope ∩ Keep), one line per photo, by capture time then name."""
    seen: set[int] = set()
    kept: list[tuple[datetime | None, str]] = []
    for photo in load_photos(conn, photo_ids):
        if photo.photo_id in seen:
            continue  # the other file of a pair already listed
        seen.update(f.asset_id for f in photo.files)
        if photo.flag == "keep" and photo.files:
            kept.append((photo.capture_time, _name(photo)))
    kept.sort(key=lambda t: (t[0] is None, t[0] or datetime.min, t[1].casefold()))
    lines: list[str] = []
    listed: set[str] = set()
    stems: dict[str, list[str]] = {}
    for _time, name in kept:
        stem = PurePosixPath(name).stem
        stems.setdefault(stem.casefold(), []).append(stem)
        line = name if with_extension else stem
        if line.casefold() not in listed:
            listed.add(line.casefold())
            lines.append(line)
    shared = {group[0]: len(group) for group in stems.values() if len(group) > 1}
    return NameList(lines, len(kept), shared)
