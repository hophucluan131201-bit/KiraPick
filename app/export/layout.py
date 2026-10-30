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
    assigned_per_folder: dict[str, int] = field(default_factory=dict)  # folder -> photos the layout puts there
    exportable_per_folder: dict[str, int] = field(default_factory=dict)  # folder -> photos with ≥ 1 file to copy there
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


def _key(name: str) -> str:
    """How Windows compares folder names (case-insensitive) after Unicode normalisation."""
    return unicodedata.normalize("NFC", name).casefold()


def _with_suffix(base: str, suffix: str) -> str:
    """``base`` + ``suffix`` within MAX_FOLDER_CHARS (the base is cut, never the suffix)."""
    room = MAX_FOLDER_CHARS - len(suffix)
    return base[:room].rstrip(". ") + suffix


def subject_folders(conn: sqlite3.Connection) -> dict[int, str]:
    """Unmerged subject -> folder name, unique as Windows compares names (CR-P3-A01).

    1. each subject's sanitised name (``safe_folder_name``);
    2. names shared by several subjects (case-insensitive, NFC) and the reserved ``Chưa xác định`` get `` (#<id>)``;
    3. in subject id order, a name already given to another subject (e.g. one literally named ``Mai (#12)``) gets
       `` (#<id>)`` appended, then `` (#<id>-2)``, `` (#<id>-3)`` … until free.
    Every name stays within MAX_FOLDER_CHARS. The result depends only on the subjects' ids and names, so it is the
    same on every export while the subjects do not change."""
    bases = {int(sid): safe_folder_name(name or "", f"Chủ thể {sid}")
             for sid, name in conn.execute("SELECT id, display_name FROM subjects WHERE merged_into IS NULL")}
    shared: dict[str, int] = {}
    for base in bases.values():
        shared[_key(base)] = shared.get(_key(base), 0) + 1
    used = {_key(UNKNOWN_FOLDER)}
    out = {}
    for sid in sorted(bases):
        base = bases[sid]
        candidates = [base] if shared[_key(base)] == 1 else []
        candidates.append(_with_suffix(base, f" (#{sid})"))
        n = 1
        while all(_key(c) in used for c in candidates):
            n += 1
            candidates.append(_with_suffix(base, f" (#{sid}-{n})"))
        name = next(c for c in candidates if _key(c) not in used)
        used.add(_key(name))
        out[sid] = name
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
