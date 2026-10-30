"""The export's ③ Thư mục đích option: one folder, or one folder per subject (Part 3 spec §3.4).

Subject assignments are only read — no AI runs and nothing is written. A photo belongs to the subjects its
occurrences are assigned to automatically or by hand (``suggested`` does not count); an occurrence that still points
to a merged subject counts for the subject it was finally merged into."""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from app.export.photos import Photo

UNKNOWN_FOLDER = "Chưa xác định"
MAX_FOLDER_CHARS = 60
MAX_PATH_CHARS = 259  # Windows MAX_PATH without long-path support
MAX_MERGE_STEPS = 32
_FORBIDDEN = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class Layout(str, Enum):
    SINGLE = "single"  # every file into the destination folder
    SUBJECTS = "subjects"  # one folder per subject


@dataclass(slots=True)
class LayoutStats:
    per_folder: dict[str, int] = field(default_factory=dict)  # folder -> photos
    multi_subject: int = 0  # photos copied into several subject folders
    unknown_suggested: int = 0  # photos in "Chưa xác định" with a subject only suggested by the AI
    unknown_other: int = 0  # photos in "Chưa xác định" without any subject (no person, unknown, not analysed)
    analysed: bool = False  # the subject analysis ran at least once in this session


def safe_folder_name(name: str, fallback: str) -> str:
    """A folder name Windows accepts. Without any letter or digit left (``???``, ``...``) → ``fallback``."""
    text = unicodedata.normalize("NFC", name or "")
    text = "".join("_" if c in _FORBIDDEN or unicodedata.category(c).startswith("C") else c for c in text)
    text = text.strip(" ").rstrip(". ")
    if text.split(".")[0].upper() in _RESERVED:
        text += "_"
    text = text[:MAX_FOLDER_CHARS].rstrip(". ")
    if not any(unicodedata.category(c)[0] in "LN" for c in text):
        return fallback
    return text


def resolve_subject(conn: sqlite3.Connection, subject_id: int) -> int | None:
    """The subject this one was finally merged into (itself when never merged); None for a cycle or a missing row."""
    current = subject_id
    for _ in range(MAX_MERGE_STEPS):
        row = conn.execute("SELECT merged_into FROM subjects WHERE id = ?", (current,)).fetchone()
        if row is None:
            return None
        if row[0] is None:
            return current
        current = int(row[0])
    return None


def subject_folders(conn: sqlite3.Connection) -> dict[int, str]:
    """Unmerged subject -> its folder name, unique case-insensitively (``Mai (#12)`` when two would be equal)."""
    names = {int(sid): safe_folder_name(name or "", f"Chủ thể {sid}")
             for sid, name in conn.execute("SELECT id, display_name FROM subjects WHERE merged_into IS NULL")}
    taken: dict[str, int] = {}
    for name in names.values():
        taken[name.casefold()] = taken.get(name.casefold(), 0) + 1
    out = {}
    for sid, name in names.items():
        clash = taken[name.casefold()] > 1 or name.casefold() == UNKNOWN_FOLDER.casefold()
        out[sid] = f"{name} (#{sid})" if clash else name
    return out


def photo_subjects(conn: sqlite3.Connection, photos: list[Photo]) -> dict[int, tuple[int, ...]]:
    """Photo id -> its subjects (resolved, unique, sorted); empty = "Chưa xác định"."""
    cache: dict[int, int | None] = {}
    out = {}
    for photo in photos:
        ids = [f.asset_id for f in photo.files] or [photo.photo_id]
        rows = conn.execute(
            f"""SELECT subject_id FROM occurrences WHERE asset_id IN ({','.join('?' * len(ids))})
                AND subject_id IS NOT NULL AND assignment IN ('auto', 'manual')""", ids).fetchall()
        found = set()
        for (sid,) in rows:
            if sid not in cache:
                cache[sid] = resolve_subject(conn, int(sid))
            if cache[sid] is not None:
                found.add(cache[sid])
        out[photo.photo_id] = tuple(sorted(found))
    return out


def has_suggestion(conn: sqlite3.Connection, photo: Photo) -> bool:
    ids = [f.asset_id for f in photo.files] or [photo.photo_id]
    return conn.execute(f"""SELECT 1 FROM occurrences WHERE asset_id IN ({','.join('?' * len(ids))})
                            AND assignment = 'suggested' AND subject_id IS NOT NULL LIMIT 1""", ids).fetchone() is not None


def analysed(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM occurrences LIMIT 1").fetchone() is not None
