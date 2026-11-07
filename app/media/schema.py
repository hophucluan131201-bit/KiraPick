"""The tables only a Media event database has (Media spec v6 §2.1, plan Mốc 1 §2.1).

An event database is a session database (app.storage.db, the same photo tables: assets, previews, decisions,
analysis runs…) plus these tables. They are applied only by app.media.event when an event is created or opened;
a Chụp cá nhân session never gets them. Versioned on their own in ``media_meta`` (key 'schema').
"""

from __future__ import annotations

import sqlite3

MEDIA_MIGRATIONS: list[tuple[int, str]] = [
    (1, """
-- M1: the event itself
CREATE TABLE media_event (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""),
    (2, """
-- M2: camera sources (spec §9): sub-folder + make / model by default, never the serial number (UX-3);
-- the user can rename, split, merge and assign photos by hand (manual = 1 is never changed automatically)
CREATE TABLE camera_sources (
    id            INTEGER PRIMARY KEY,
    auto_key      TEXT UNIQUE,              -- '<source id>|<sub-folder>|<make>|<model>'; NULL for one made by hand
    make          TEXT,
    model         TEXT,
    display_name  TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE asset_source (
    asset_id   INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    camera_id  INTEGER NOT NULL REFERENCES camera_sources(id),
    manual     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX asset_source_camera ON asset_source (camera_id);
"""),
]
MEDIA_SCHEMA_VERSION = MEDIA_MIGRATIONS[-1][0]


class MediaSchemaTooNew(RuntimeError):
    """The event was saved by a newer KiraPick."""


def media_version(conn: sqlite3.Connection) -> int:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'media_meta'").fetchone() is None:
        return 0
    row = conn.execute("SELECT value FROM media_meta WHERE key = 'schema'").fetchone()
    return int(row[0]) if row else 0


def is_media_db(conn: sqlite3.Connection) -> bool:
    return media_version(conn) > 0


def migrate_media(conn: sqlite3.Connection) -> None:
    """Apply the Media tables up to MEDIA_SCHEMA_VERSION, each step all-or-nothing."""
    version = media_version(conn)
    if version > MEDIA_SCHEMA_VERSION:
        raise MediaSchemaTooNew(f"event schema v{version} is newer than this app (v{MEDIA_SCHEMA_VERSION})")
    for target, sql in MEDIA_MIGRATIONS:
        if target <= version:
            continue
        try:
            conn.executescript(
                "BEGIN IMMEDIATE;\n"
                "CREATE TABLE IF NOT EXISTS media_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);\n"
                f"{sql}\n"
                f"INSERT INTO media_meta (key, value) VALUES ('schema', '{target}')\n"
                "  ON CONFLICT (key) DO UPDATE SET value = excluded.value;\n"
                "COMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
