from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.storage import db, decisions
from app.storage.project import Project, ProjectError


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "proj", "Test")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/photos', 'now')")
    for name in ("a.nef", "b.nef"):
        p.conn.execute(
            """INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, added_at, updated_at) VALUES (1, ?, '.nef', 'raw', 'verified', 1, 1, ?, 'n', 'n')""",
            (name, name),
        )
    yield p
    p.close()


def test_new_project_is_fully_migrated(project: Project) -> None:
    assert db.current_version(project.conn) == db.SCHEMA_VERSION
    assert project.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert project.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert project.name == "Test"


def test_reopen_and_refuse_duplicates(tmp_path: Path) -> None:
    Project.create(tmp_path / "p", "X").close()
    with pytest.raises(ProjectError):
        Project.create(tmp_path / "p", "Y")
    with pytest.raises(ProjectError):
        Project.open(tmp_path / "nothing")
    with Project.open(tmp_path / "p") as p:
        assert p.name == "X"


def test_newer_schema_is_refused_untouched(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
    conn.close()
    with pytest.raises(db.SchemaTooNewError):
        db.connect(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0


def test_failed_migration_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    released = db.SCHEMA_VERSION
    broken = db.MIGRATIONS + [(db.SCHEMA_VERSION + 1, "CREATE TABLE extra (x INTEGER); SELECT * FROM no_such_table;")]
    monkeypatch.setattr(db, "MIGRATIONS", broken)
    monkeypatch.setattr(db, "SCHEMA_VERSION", db.SCHEMA_VERSION + 1)
    path = tmp_path / "p.db"
    with pytest.raises(sqlite3.Error):
        db.connect(path)
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == released  # broken one not half-applied
    assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name = 'extra'").fetchone()[0] == 0


def test_photo_decisions_upsert_to_one_row(project: Project) -> None:
    decisions.set_flag(project.conn, 1, "keep")
    decisions.set_rating(project.conn, 1, 5)
    decisions.set_favorite(project.conn, 1, True)
    decisions.set_flag(project.conn, 1, "reject")
    assert decisions.get(project.conn, 1) == decisions.Decision("reject", 5, True)
    assert decisions.get(project.conn, 2) == decisions.Decision()
    assert project.conn.execute("SELECT count(*) FROM decisions").fetchone()[0] == 1
    decisions.set_flag(project.conn, 1, None)
    assert decisions.get(project.conn, 1).flag is None


def test_decision_validation(project: Project) -> None:
    with pytest.raises(ValueError):
        decisions.set_rating(project.conn, 1, 6)
    with pytest.raises(ValueError):
        decisions.set_flag(project.conn, 1, "maybe")  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        decisions.set_flag(project.conn, 999, "keep")  # FK enforced


def test_measurements_unique_per_frame_and_occurrence(project: Project) -> None:
    sql = """INSERT INTO measurements (asset_id, occurrence_id, extractor, extractor_version, input_source,
             values_json, computed_at) VALUES (1, ?, 'sharpness', '1', 'embedded_jpeg', '{}', 'n')"""
    project.conn.execute(sql, (None,))
    with pytest.raises(sqlite3.IntegrityError):
        project.conn.execute(sql, (None,))
    project.conn.execute(sql, (7,))
    with pytest.raises(sqlite3.IntegrityError):
        project.conn.execute(sql, (7,))


def test_interrupted_jobs_become_paused(tmp_path: Path) -> None:
    with Project.create(tmp_path / "p", "X") as p:
        p.conn.execute(
            "INSERT INTO jobs (kind, state, created_at, updated_at) VALUES ('import', 'running', 'n', 'n')"
        )
    with Project.open(tmp_path / "p") as p:
        assert p.conn.execute("SELECT state FROM jobs").fetchone()[0] == "paused"


def test_transaction_rolls_back_on_error(project: Project) -> None:
    with pytest.raises(RuntimeError):
        with project.transaction() as tx:
            tx.execute("UPDATE assets SET status = 'ok' WHERE id = 1")
            raise RuntimeError("boom")
    assert project.conn.execute("SELECT status FROM assets WHERE id = 1").fetchone()[0] == "pending"
