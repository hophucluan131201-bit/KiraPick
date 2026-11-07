"""Media events: one folder and one database per event, apart from Chụp cá nhân (Media spec v6 §1, plan Mốc 1 M1).

    %LOCALAPPDATA%\\KiraPick\\media\\<event id>\\project.snorlu.db  (+ cache\\ thumbnails, export records)

An event database is a session database (the photo tables are shared code: import, thumbnails, P/X, export, result
provenance) plus the Media tables of app.media.schema. The same photo folder can be in a Chụp cá nhân session and in
an event at the same time: they are two databases, so P/X, stars and everything else stay separate.

Deleting an event deletes only its folder under the media root (never a photo): the folder must be inside the media
root and hold a Media database, otherwise nothing is removed.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.branding import data_dir
from app.media.schema import is_media_db, migrate_media
from app.storage.project import DB_NAME, Project, ProjectError, utc_now


class EventError(ProjectError):
    pass


def media_root() -> Path:
    return data_dir() / "media"


@dataclass(frozen=True, slots=True)
class EventInfo:
    id: str
    name: str
    created_at: str
    folder: Path


class MediaEvent(Project):
    """A Project whose database also has the Media tables."""

    @property
    def event_id(self) -> str:
        return self.folder.name

    @property
    def event_name(self) -> str:
        return str(self.conn.execute("SELECT name FROM media_event WHERE id = 1").fetchone()[0])

    def rename(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise EventError("tên sự kiện trống")
        with self.transaction() as conn:
            conn.execute("UPDATE media_event SET name = ? WHERE id = 1", (name,))
            conn.execute("UPDATE project SET name = ? WHERE id = 1", (name,))


def create_event(name: str, root: Path | None = None) -> MediaEvent:
    name = name.strip()
    if not name:
        raise EventError("tên sự kiện trống")
    root = (root or media_root())
    root.mkdir(parents=True, exist_ok=True)
    folder = root / uuid.uuid4().hex[:12]
    base = Project.create(folder, name)
    migrate_media(base.conn)
    base.conn.execute("INSERT INTO media_event (id, name, created_at) VALUES (1, ?, ?)", (name, utc_now()))
    return MediaEvent(base.folder, base.conn)


def open_event(event_id: str, root: Path | None = None) -> MediaEvent:
    folder = _event_folder(event_id, root)
    base = Project.open(folder)
    if not is_media_db(base.conn):
        base.close()
        raise EventError("thư mục này không phải sự kiện Media")
    migrate_media(base.conn)
    return MediaEvent(base.folder, base.conn)


def list_events(root: Path | None = None) -> list[EventInfo]:
    import sqlite3

    root = root or media_root()
    out = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        db_path = folder / DB_NAME
        if not db_path.is_file():
            continue
        try:  # read-only: listing never migrates or changes an event
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                row = conn.execute("SELECT name, created_at FROM media_event WHERE id = 1").fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            continue
        if row is not None:
            out.append(EventInfo(folder.name, row[0], row[1], folder))
    return sorted(out, key=lambda e: e.created_at, reverse=True)


def delete_event(event_id: str, root: Path | None = None) -> None:
    """Remove the event's own folder (its database, thumbnails, records). Photos are never touched."""
    import sqlite3

    folder = _event_folder(event_id, root)
    db_path = folder / DB_NAME
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        if not is_media_db(conn):
            raise EventError("thư mục này không phải sự kiện Media: không xoá")
    finally:
        conn.close()
    shutil.rmtree(folder)


def _event_folder(event_id: str, root: Path | None) -> Path:
    root = (root or media_root()).resolve()
    if not event_id or any(c in event_id for c in "/\\.:") or len(event_id) > 64:
        raise EventError("mã sự kiện không hợp lệ")
    folder = (root / event_id).resolve()
    if folder.parent != root or folder.is_symlink():
        raise EventError("sự kiện nằm ngoài thư mục Media")
    if not (folder / DB_NAME).is_file():
        raise EventError("không có sự kiện này")
    return folder
