"""Hidden per-folder sessions: no "projects" for the user to manage.

Every imported photo folder gets its own session directory (database +
thumbnail cache) under the app's local data folder, keyed by the folder path.
Opening the same folder again restores the earlier work; sessions unused for
``SESSION_TTL_DAYS`` are purged. Only directories that this module created
(they contain the session marker) are ever deleted — never photos.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path

from app.storage.project import DB_NAME, Project

SESSION_TTL_DAYS = 30
_MARKER = "kirapick-session"  # file inside every session dir; required before any deletion
_LEGACY_MARKERS = ("snorlu-session",)  # sessions created before the rename


def session_key(photo_folder: Path) -> str:
    path = str(photo_folder.resolve())
    if os.name == "nt":
        path = path.casefold()  # D:\Ảnh and d:\ảnh are the same folder on Windows
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:20]


def session_dir(sessions_root: Path, photo_folder: Path) -> Path:
    return sessions_root / session_key(photo_folder)


def _touch(folder: Path) -> None:
    marker = folder / _MARKER
    marker.write_text("KiraPick session data (safe to delete; photos are elsewhere)\n", encoding="utf-8")
    for old in _LEGACY_MARKERS:
        (folder / old).unlink(missing_ok=True)


def open_session(sessions_root: Path, photo_folder: Path) -> tuple[Project, bool]:
    """Open the session for ``photo_folder``; returns (project, restored_from_earlier)."""
    folder = session_dir(sessions_root, photo_folder)
    restored = (folder / DB_NAME).is_file()
    project = Project.open(folder) if restored else Project.create(folder, photo_folder.name or str(photo_folder))
    _touch(folder)
    return project, restored


def _is_session(folder: Path) -> bool:
    return (folder.is_dir() and not folder.is_symlink()
            and any((folder / m).is_file() for m in (_MARKER, *_LEGACY_MARKERS))
            and (folder / DB_NAME).is_file())


def delete_session(sessions_root: Path, photo_folder: Path) -> bool:
    """Forget everything remembered for ``photo_folder`` (the session must be closed)."""
    folder = session_dir(sessions_root, photo_folder)
    if not _is_session(folder):
        return False
    shutil.rmtree(folder)
    return True


def purge_old_sessions(sessions_root: Path, *, ttl_days: int = SESSION_TTL_DAYS, now: float | None = None,
                       keep: set[Path] | frozenset[Path] = frozenset()) -> list[Path]:
    """Delete session dirs not used for ``ttl_days``. Returns what was removed."""
    if not sessions_root.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - ttl_days * 86400
    removed = []
    for folder in sessions_root.iterdir():
        if folder in keep or not _is_session(folder):
            continue
        try:
            marker = next(folder / m for m in (_MARKER, *_LEGACY_MARKERS) if (folder / m).is_file())
            if marker.stat().st_mtime < cutoff:
                shutil.rmtree(folder)
                removed.append(folder)
        except OSError:
            continue  # in use or locked: try again next start
    return removed
