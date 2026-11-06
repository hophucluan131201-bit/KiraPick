"""U11: schema v8 result provenance. A 3.0.0 (v7) session upgrades with a v7 backup, its old results stay with
run_id NULL (source unknown), new results carry the run and the weights really opened; restoring the v7 backup on
a copy works, and edits made after the upgrade are not in that backup (the documented limit of going back)."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.ai.policy import LOAD_LOG
from app.identity.features import OccurrenceFeatures
from app.storage import db, provenance
from app.storage.project import Project


def _v7_session(path: Path) -> None:
    """A session as 3.0.0 left it (schema v7) with ArcFace vectors, TOPIQ values, P/X and manual groups."""
    conn = sqlite3.connect(path, isolation_level=None)
    for target, sql in db.MIGRATIONS[:7]:
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {target};\nCOMMIT;")
    conn.execute("INSERT INTO project (id, name, created_at) VALUES (1, 'Old', 'then')")
    conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/photos', 'now')")
    for name in ("a.nef", "b.jpg"):
        conn.execute("""INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size,
                        mtime_ns, quick_hash, added_at, updated_at)
                        VALUES (1, ?, '.nef', 'raw', 'verified', 1, 1, ?, 'n', 'n')""", (name, name))
    conn.execute("INSERT INTO decisions (asset_id, flag, rating, favorite, updated_at) VALUES (1, 'keep', 4, 1, 'n')")
    conn.execute("INSERT INTO subjects (id, display_name, user_locked, created_at) VALUES (1, 'Aki', 1, 'n')")
    conn.execute("INSERT INTO subjects (id, created_at) VALUES (2, 'n')")
    for occ, (asset, subject, assignment) in enumerate([(1, 1, "manual"), (2, 2, "auto")], start=1):
        conn.execute("""INSERT INTO occurrences (id, asset_id, prominence, is_main, subject_id, assignment,
                        analysis_version, created_at) VALUES (?, ?, 1.0, 1, ?, ?, 2, 'n')""",
                     (occ, asset, subject, assignment))
        conn.execute("""INSERT INTO occurrence_vectors (occurrence_id, kind, model_version, vector)
                        VALUES (?, 'face_arc', 'arcface-w600k-r50', ?)""", (occ, np.ones(4, "<f4").tobytes()))
        conn.execute("""INSERT INTO measurements (asset_id, occurrence_id, extractor, extractor_version, input_source,
                        values_json, computed_at) VALUES (?, ?, 'quality', 5, 'raw_full', '{"tech_iqa": 0.7}', 'n')""",
                     (asset, occ))
    conn.close()


def _dump(path: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        return [tuple(r) for r in conn.execute(sql)]
    finally:
        conn.close()


USER_ROWS = ("SELECT * FROM decisions ORDER BY asset_id",
             "SELECT id, display_name, user_locked, merged_into, created_at FROM subjects ORDER BY id",
             "SELECT * FROM subject_pairs ORDER BY a, b",
             # what the user assigned by hand (automatic assignments may move aside: DATA-1)
             "SELECT id, asset_id, subject_id, assignment, excluded_subject_id FROM occurrences "
             "WHERE assignment = 'manual' ORDER BY id")


def test_v7_session_upgrades_keeps_old_results_as_unknown_source_and_backs_up(tmp_path: Path) -> None:
    path = tmp_path / "project.snorlu.db"
    _v7_session(path)
    before = {q: _dump(path, q) for q in USER_ROWS}
    conn = db.connect(path)
    try:
        assert db.current_version(conn) == 8
        assert provenance.unknown_source_summary(conn) == {"occurrences": 2, "occurrence_vectors": 2,
                                                           "measurements": 2, "asset_vectors": 0}
    finally:
        conn.close()
    assert {q: _dump(path, q) for q in USER_ROWS} == before  # user data unchanged by the upgrade
    backup = path.with_name(path.name + ".v7.bak")
    assert backup.exists()
    assert _dump(backup, "PRAGMA user_version") == [(7,)]
    assert {q: _dump(backup, q) for q in USER_ROWS} == before


def test_restoring_the_v7_backup_on_a_copy_and_its_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "project.snorlu.db"
    _v7_session(path)
    db.connect(path).close()  # upgraded to v8, backup written
    conn = db.connect(path)
    conn.execute("UPDATE decisions SET flag = 'reject' WHERE asset_id = 1")  # an edit made after the upgrade
    conn.close()
    # an older app (schema v7) refuses the upgraded file and leaves it untouched
    monkeypatch.setattr(db, "MIGRATIONS", db.MIGRATIONS[:7])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 7)
    with pytest.raises(db.SchemaTooNewError):
        db.connect(path)
    assert _dump(path, "PRAGMA user_version") == [(8,)]
    # going back = the backup, restored on a copy: it opens in the older app, with the data from before the upgrade
    restored = tmp_path / "copy" / "project.snorlu.db"
    restored.parent.mkdir()
    shutil.copy2(path.with_name(path.name + ".v7.bak"), restored)
    conn = db.connect(restored)
    try:
        assert db.current_version(conn) == 7
        assert conn.execute("SELECT flag FROM decisions WHERE asset_id = 1").fetchone()[0] == "keep"
    finally:
        conn.close()
    # the limit: what was changed after the upgrade (here P -> X) is not in the backup
    assert _dump(path, "SELECT flag FROM decisions WHERE asset_id = 1") == [("reject",)]


def test_new_results_carry_their_run_and_the_weights_really_opened(tmp_path: Path) -> None:
    from app.workers.analyze_job import STAGE, AnalyzeJob

    LOAD_LOG.clear()
    LOAD_LOG.handed_out("person_detector_s", tmp_path / "yolox_s.onnx", "a" * 64)
    LOAD_LOG.provider(tmp_path / "yolox_s.onnx", "CPUExecutionProvider")
    LOAD_LOG.handed_out("face_detector", tmp_path / "yunet.onnx", "b" * 64)
    LOAD_LOG.provider(tmp_path / "yunet.onnx", "opencv")
    with Project.create(tmp_path / "session", "New") as project:
        conn = project.conn
        conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/p', 'n')")
        conn.execute("""INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size,
                        mtime_ns, quick_hash, added_at, updated_at)
                        VALUES (1, 'x.jpg', '.jpg', 'raster', 'verified', 1, 1, 'x', 'n', 'n')""")
        conn.execute("""INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at)
                        VALUES (1, ?, 2, 'pending', 0, 'n')""", (STAGE,))
        job = AnalyzeJob(project)
        with project.transaction() as c:
            job._run_id = provenance.start_run(c, STAGE)
            assert provenance.record_models(c, job._run_id, ("person_detector_s", "face_detector",
                                                              "face_embedder")) == ["person_detector_s", "face_detector"]
        feats = [OccurrenceFeatures((0.1, 0.1, 0.5, 0.9), 0.9, None, None, None, np.ones(8, np.float32), 1.0, True,
                                    None)]
        job._store(1, feats)
        assert conn.execute("SELECT run_id FROM occurrences").fetchone()[0] == job._run_id
        assert conn.execute("SELECT run_id FROM occurrence_vectors WHERE kind = 'outfit'").fetchone()[0] == job._run_id
        assert provenance.run_models(conn, job._run_id) == [
            {"model_id": "face_detector", "sha256": "b" * 64, "provider": "opencv"},
            {"model_id": "person_detector_s", "sha256": "a" * 64, "provider": "CPUExecutionProvider"}]
        assert provenance.unknown_source_summary(conn)["occurrences"] == 0
    LOAD_LOG.clear()
