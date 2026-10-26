"""SQLite connection setup and versioned, atomic schema migrations.

One database file per project. Schema version lives in ``PRAGMA user_version``.
A database written by a newer app version is refused rather than modified.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.errors import SnorluError

# Each entry is applied once, inside one transaction, in order. Never edit a
# released migration; append a new one.
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
CREATE TABLE project (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    name         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    preset       TEXT NOT NULL DEFAULT 'cosplay',
    config_json  TEXT NOT NULL DEFAULT '{}'
);

-- Folders the user imported. Assets store paths relative to their source so a
-- moved folder is fixed by updating root_path once (relink).
CREATE TABLE sources (
    id            INTEGER PRIMARY KEY,
    root_path     TEXT NOT NULL UNIQUE,
    added_at      TEXT NOT NULL,
    last_scan_at  TEXT
);

-- Derived from file names + capture times; rebuilt on every scan of a source.
CREATE TABLE pair_groups (
    id      INTEGER PRIMARY KEY,
    status  TEXT NOT NULL CHECK (status IN ('confirmed', 'name_only'))
);

CREATE TABLE assets (
    id              INTEGER PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES sources(id),
    relative_path   TEXT NOT NULL,
    extension       TEXT NOT NULL,
    media_kind      TEXT NOT NULL CHECK (media_kind IN ('raw', 'raster')),
    support_level   TEXT NOT NULL,
    size            INTEGER NOT NULL,
    mtime_ns        INTEGER NOT NULL,
    quick_hash      TEXT NOT NULL,
    sha256          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'ok', 'error', 'missing', 'duplicate')),
    duplicate_of    INTEGER REFERENCES assets(id),
    error           TEXT,
    width           INTEGER,
    height          INTEGER,
    orientation     INTEGER,
    capture_time    TEXT,
    subsec          TEXT,
    make            TEXT,
    model           TEXT,
    lens            TEXT,
    exif_json       TEXT,
    pair_group_id   INTEGER REFERENCES pair_groups(id) ON DELETE SET NULL,
    added_at        TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (source_id, relative_path)
);
CREATE INDEX assets_content ON assets (size, quick_hash);
CREATE INDEX assets_capture ON assets (capture_time, subsec);
CREATE INDEX assets_pair ON assets (pair_group_id);

CREATE TABLE previews (
    asset_id        INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('thumb', 'analysis')),
    file_name       TEXT NOT NULL,      -- relative to the project cache dir
    width           INTEGER NOT NULL,
    height          INTEGER NOT NULL,
    source          TEXT NOT NULL,      -- PreviewSource value
    render_version  INTEGER NOT NULL,
    PRIMARY KEY (asset_id, kind)
);

-- Stable identity anchor; detection/clustering tables arrive with M2.
CREATE TABLE subjects (
    id            INTEGER PRIMARY KEY,
    display_name  TEXT,
    user_locked   INTEGER NOT NULL DEFAULT 0,
    merged_into   INTEGER REFERENCES subjects(id),
    created_at    TEXT NOT NULL
);

-- Culling decisions: whole photo (subject_id NULL) or per subject.
-- Partial unique indexes because UNIQUE treats NULLs as distinct in SQLite.
CREATE TABLE decisions (
    id          INTEGER PRIMARY KEY,
    asset_id    INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    subject_id  INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    flag        TEXT CHECK (flag IN ('keep', 'reject')),
    rating      INTEGER NOT NULL DEFAULT 0 CHECK (rating BETWEEN 0 AND 5),
    favorite    INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
    updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX decisions_photo ON decisions (asset_id) WHERE subject_id IS NULL;
CREATE UNIQUE INDEX decisions_subject ON decisions (asset_id, subject_id) WHERE subject_id IS NOT NULL;

-- Raw, preset-independent measurements. Scores are derived from these plus the
-- active preset at ranking time, so changing weights never recomputes them.
CREATE TABLE measurements (
    id                 INTEGER PRIMARY KEY,
    asset_id           INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    occurrence_id      INTEGER,          -- NULL = whole frame; FK added with M2 tables
    extractor          TEXT NOT NULL,
    extractor_version  TEXT NOT NULL,
    input_source       TEXT NOT NULL,    -- which pixels were measured (PreviewSource)
    values_json        TEXT NOT NULL,
    confidence_json    TEXT NOT NULL DEFAULT '{}',
    computed_at        TEXT NOT NULL
);
CREATE UNIQUE INDEX measurements_frame ON measurements (asset_id, extractor, extractor_version)
    WHERE occurrence_id IS NULL;
CREATE UNIQUE INDEX measurements_occurrence ON measurements (occurrence_id, extractor, extractor_version)
    WHERE occurrence_id IS NOT NULL;

CREATE TABLE jobs (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,
    state        TEXT NOT NULL CHECK (state IN ('running', 'paused', 'done', 'failed')),
    params_json  TEXT NOT NULL DEFAULT '{}',
    error        TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- Per-asset pipeline progress: the unit of pause/resume and retry.
CREATE TABLE stage_status (
    asset_id       INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    stage          TEXT NOT NULL,
    stage_version  INTEGER NOT NULL,
    state          TEXT NOT NULL CHECK (state IN ('pending', 'done', 'failed')),
    attempts       INTEGER NOT NULL DEFAULT 0,
    error          TEXT,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (asset_id, stage)
);
CREATE INDEX stage_pending ON stage_status (stage, state);

CREATE TABLE model_registry (
    model_id    TEXT NOT NULL,
    version     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    license     TEXT NOT NULL,
    provenance  TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (model_id, version)
);
""",
    ),
]

SCHEMA_VERSION = MIGRATIONS[-1][0]


class SchemaTooNewError(SnorluError):
    """The project was saved by a newer version of the app."""


def connect(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) a project database and migrate it."""
    conn = sqlite3.connect(path, isolation_level=None)  # explicit transactions only
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        migrate(conn)
    except Exception:
        conn.close()
        raise
    return conn


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> None:
    version = current_version(conn)
    if version > SCHEMA_VERSION:
        raise SchemaTooNewError(
            f"project schema v{version} is newer than this app (v{SCHEMA_VERSION}); update the app"
        )
    for target, sql in MIGRATIONS:
        if target <= version:
            continue
        # executescript commits any open transaction first; BEGIN..COMMIT inside
        # the script makes each migration all-or-nothing.
        try:
            conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {target};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
