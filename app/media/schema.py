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
    (3, """
-- M3: clock offsets per camera source (spec §9). The corrected time is always capture_time + offset, computed:
-- EXIF and assets.capture_time are never changed. Undo history of Media actions: media_journal (newest kept).
CREATE TABLE clock_offsets (
    camera_id  INTEGER PRIMARY KEY REFERENCES camera_sources(id),
    seconds    REAL NOT NULL
);
CREATE TABLE media_journal (
    id          INTEGER PRIMARY KEY,
    label       TEXT NOT NULL,
    before_json TEXT NOT NULL,   -- {table: {"where": sql, "params": [...], "rows": [...]}} taken before the action
    created_at  TEXT NOT NULL
);
"""),
    (4, """
-- M4: moments (spec §8). Every readable photo is in exactly one moment. AI moments are re-made on every split;
-- a pinned moment (📌: split / merged / moved / renamed by the user) keeps its photo list through re-analysis and
-- clock changes. drift_warnings: ⚠ 'lệch giờ' of the photos of the source whose clock was just changed.
CREATE TABLE moments (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    pinned      INTEGER NOT NULL DEFAULT 0,
    no_time     INTEGER NOT NULL DEFAULT 0,   -- the 'Không rõ giờ' moment
    created_at  TEXT NOT NULL
);
CREATE TABLE moment_assets (
    asset_id   INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    moment_id  INTEGER NOT NULL REFERENCES moments(id) ON DELETE CASCADE
);
CREATE INDEX moment_assets_moment ON moment_assets (moment_id);
CREATE TABLE drift_warnings (
    asset_id    INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    suggested   INTEGER NOT NULL REFERENCES moments(id) ON DELETE CASCADE,
    camera_id   INTEGER NOT NULL           -- the source whose clock change raised it
);
"""),
    (5, """
-- M5: labels (spec §2-§6) with their state (spec §3). grp: 'shot' (one value per photo: toan / trung / can, or
-- '?' = Chưa xác định), 'content' (several: san_khau, booth, decor, san_pham, merch), 'focus' (out_net,
-- trat_net). No row for a group = Đang phân tích. 'removed' = the user took an AI label away: never suggested again.
CREATE TABLE labels (
    asset_id    INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    grp         TEXT NOT NULL CHECK (grp IN ('shot', 'content', 'focus')),
    value       TEXT NOT NULL,
    state       TEXT NOT NULL CHECK (state IN ('unknown', 'suggested', 'confirmed', 'removed')),
    confidence  REAL,
    run_id      INTEGER REFERENCES analysis_runs(id),
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (asset_id, grp, value)
);
CREATE INDEX labels_group ON labels (grp, value, state);
-- booth / sponsor names: set by the user (always confirmed); suggested for photos of the same moment only
CREATE TABLE booth_names (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);
CREATE TABLE asset_booth (
    asset_id  INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    booth_id  INTEGER NOT NULL REFERENCES booth_names(id) ON DELETE CASCADE,
    state     TEXT NOT NULL CHECK (state IN ('suggested', 'confirmed'))
);
"""),
    (6, """
-- M6: per-photo progress of 'Phân tích sự kiện' (no row = ⏳). Numbers only (sizes, sharpness): they let the sample
-- scorer (M9) report how the thresholds do, without running the models again. status: 'done' | 'failed'.
CREATE TABLE media_analysis (
    asset_id       INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    shot_version   TEXT,
    focus_version  TEXT,
    status         TEXT NOT NULL CHECK (status IN ('done', 'failed')),
    run_id         INTEGER REFERENCES analysis_runs(id),
    measures_json  TEXT,
    updated_at     TEXT NOT NULL
);
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
