"""Schema v7: view-only rotation per photo and a record of finished exports (time and counts only)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.storage import db, exports, view
from app.storage.project import Project


def _asset(conn: sqlite3.Connection, name: str, pair: int | None = None, kind: str = "raster") -> int:
    src = conn.execute("SELECT id FROM sources").fetchone()
    src_id = src[0] if src else conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
    return int(conn.execute(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at, pair_group_id) "
        "VALUES (?, ?, 'jpg', ?, 'full', 1, 1, 'h', 'ok', 't', 't', ?)", (src_id, name, kind, pair)).lastrowid)


def test_migration_7_on_a_v6_session(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for target, sql in db.MIGRATIONS:
        if target <= 6:
            conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {target};\nCOMMIT;")
    assert db.current_version(conn) == 6
    aid = _asset(conn, "a.jpg")
    conn.execute("INSERT INTO decisions (asset_id, subject_id, flag, rating, favorite, focus, updated_at)"
                 " VALUES (?, NULL, 'keep', 4, 1, 'sharp', 't')", (aid,))
    db.migrate(conn)
    assert db.current_version(conn) == 7
    row = conn.execute("SELECT flag, rating, favorite, focus FROM decisions WHERE asset_id = ?", (aid,)).fetchone()
    assert tuple(row) == ("keep", 4, 1, "sharp")
    assert view.rotations(conn) == {} and exports.count(conn) == 0


def test_rotate_cycles_and_clears(tmp_path: Path) -> None:
    with Project.create(tmp_path / "s", "t") as project:
        conn = project.conn
        aid = _asset(conn, "a.jpg")
        assert view.rotation(conn, aid) == 0
        assert [view.rotate(conn, aid) for _ in range(4)] == [1, 2, 3, 0]
        assert conn.execute("SELECT COUNT(*) FROM view_rotation").fetchone()[0] == 0
        view.rotate(conn, aid)
        assert view.rotations(conn) == {aid: 1}
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT OR REPLACE INTO view_rotation VALUES (?, 4)", (aid,))
        conn.execute("DELETE FROM assets WHERE id = ?", (aid,))  # a removed photo takes its rotation with it
        assert view.rotations(conn) == {}


def test_export_run_recorded_without_path(tmp_path: Path) -> None:
    with Project.create(tmp_path / "s", "t") as project:
        conn = project.conn
        exports.record(conn, 3, 5)
        assert exports.count(conn) == 1
        cols = [r[1] for r in conn.execute("PRAGMA table_info(export_runs)")]
        assert cols == ["id", "finished_at", "photos", "files"]
        with pytest.raises(ValueError):
            exports.record(conn, 0, 0)  # nothing copied is not an export


def test_photo_count_counts_a_pair_once(tmp_path: Path) -> None:
    with Project.create(tmp_path / "s", "t") as project:
        conn = project.conn
        group = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
        raw, jpg = _asset(conn, "DSC_1.NEF", group, "raw"), _asset(conn, "DSC_1.jpg", group)
        single = _asset(conn, "DSC_2.jpg")
        assert exports.photo_count(conn, [raw, jpg, single]) == 2
        assert exports.photo_count(conn, []) == 0
