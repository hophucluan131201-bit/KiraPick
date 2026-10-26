"""A project = one folder holding ``project.snorlu.db`` and ``cache/``.

The project folder is separate from the photo folders; photos are referenced,
never copied or modified.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import SnorluError
from app.storage import db

DB_NAME = "project.snorlu.db"
CACHE_DIR = "cache"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProjectError(SnorluError):
    pass


class Project:
    def __init__(self, folder: Path, conn: sqlite3.Connection) -> None:
        self.folder = folder
        self.conn = conn
        self.cache_dir = folder / CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)

    # ---------------------------------------------------------- lifecycle
    @classmethod
    def create(cls, folder: Path, name: str) -> Project:
        folder = folder.resolve()
        if (folder / DB_NAME).exists():
            raise ProjectError(f"a project already exists in {folder}")
        folder.mkdir(parents=True, exist_ok=True)
        conn = db.connect(folder / DB_NAME)
        conn.execute("INSERT INTO project (id, name, created_at) VALUES (1, ?, ?)", (name, utc_now()))
        return cls(folder, conn)

    @classmethod
    def open(cls, folder: Path) -> Project:
        folder = folder.resolve()
        if not (folder / DB_NAME).is_file():
            raise ProjectError(f"no project found in {folder}")
        project = cls(folder, db.connect(folder / DB_NAME))
        project.recover_interrupted_jobs()
        return project

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Project:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------ helpers
    @property
    def name(self) -> str:
        return str(self.conn.execute("SELECT name FROM project WHERE id = 1").fetchone()[0])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    def recover_interrupted_jobs(self) -> int:
        """Jobs left 'running' by a crash/kill become 'paused' (resumable)."""
        cur = self.conn.execute(
            "UPDATE jobs SET state = 'paused', updated_at = ? WHERE state = 'running'", (utc_now(),)
        )
        return cur.rowcount

    def asset_path(self, asset_id: int) -> Path:
        row = self.conn.execute(
            "SELECT s.root_path, a.relative_path FROM assets a JOIN sources s ON s.id = a.source_id WHERE a.id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise ProjectError(f"unknown asset {asset_id}")
        return Path(row["root_path"]) / Path(row["relative_path"])

    def relink_source(self, source_id: int, new_root: Path) -> None:
        """Point a source at its new location (folder moved/renamed or drive letter changed)."""
        new_root = new_root.resolve(strict=True)
        with self.transaction() as conn:
            conn.execute("UPDATE sources SET root_path = ? WHERE id = ?", (str(new_root), source_id))
