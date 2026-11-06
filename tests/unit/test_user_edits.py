"""C6 (LIC-1 S6): the user's corrections survive the upgrade and new analyses; DATA-1 hides only the groups the
app made on its own with ArcFace."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from app.identity.features import OccurrenceFeatures
from app.storage import db
from app.storage.project import Project
from tests.unit.test_provenance import USER_ROWS, _dump, _v7_session


def _more_subjects(path: Path) -> None:
    """Adds to the 3.0.0 session: a named subject with only automatic members, and two subjects marked different."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("INSERT INTO subjects (id, display_name, user_locked, created_at) VALUES (3, 'Bé Na', 1, 'n')")
    conn.execute("INSERT INTO subjects (id, created_at) VALUES (4, 'n')")
    conn.execute("INSERT INTO subjects (id, created_at) VALUES (5, 'n')")
    conn.execute("INSERT INTO subject_pairs (a, b, relation, created_at) VALUES (4, 5, 'different', 'n')")
    for occ, subject in ((3, 3), (4, 4), (5, 5)):
        conn.execute("""INSERT INTO occurrences (id, asset_id, prominence, is_main, subject_id, assignment,
                        analysis_version, created_at) VALUES (?, 2, 0.5, 0, ?, 'auto', 2, 'n')""", (occ, subject))
    conn.close()


def test_data1_hides_only_the_automatic_groups_nobody_edited(tmp_path: Path) -> None:
    path = tmp_path / "project.snorlu.db"
    _v7_session(path)
    _more_subjects(path)
    before = {q: _dump(path, q) for q in USER_ROWS}
    db.connect(path).close()
    assert {q: _dump(path, q) for q in USER_ROWS} == before
    rows = {r[0]: r[1:] for r in _dump(path, "SELECT id, subject_id, assignment, legacy_subject_id, legacy_assignment "
                                              "FROM occurrences")}
    assert rows[1] == (1, "manual", None, None)  # assigned by hand: untouched
    assert rows[2] == (None, "none", 2, "auto")  # subject 2: automatic only, not edited -> hidden, kept aside
    assert rows[3] == (3, "auto", None, None)  # named (locked) subject: kept
    assert rows[4] == (4, "auto", None, None) and rows[5] == (5, "auto", None, None)  # "different" pair: kept


def test_rerun_never_drops_a_photo_the_user_assigned(tmp_path: Path) -> None:
    from app.workers.analyze_job import AnalyzeJob

    with Project.create(tmp_path / "s", "x") as project:
        conn = project.conn
        conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/p', 'n')")
        conn.execute("""INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size,
                        mtime_ns, quick_hash, added_at, updated_at)
                        VALUES (1, 'x.jpg', '.jpg', 'raster', 'verified', 1, 1, 'x', 'n', 'n')""")
        conn.execute("INSERT INTO subjects (id, display_name, user_locked, created_at) VALUES (1, 'Aki', 1, 'n')")
        conn.execute("""INSERT INTO occurrences (id, asset_id, person_box, prominence, is_main, subject_id, assignment,
                        analysis_version, created_at) VALUES (1, 1, '[0.0,0.0,0.2,0.2]', 1, 1, 1, 'manual', 2, 'n')""")
        conn.execute("""INSERT INTO occurrences (id, asset_id, person_box, prominence, is_main, assignment,
                        analysis_version, created_at) VALUES (2, 1, '[0.0,0.6,0.2,0.2]', 1, 0, 'auto', 2, 'n')""")
        # the new detection finds one person elsewhere in the photo: neither old box matches it
        feats = [OccurrenceFeatures((0.6, 0.1, 0.3, 0.8), 0.9, None, None, None, np.ones(8, np.float32), 1.0, True,
                                    None)]
        AnalyzeJob(project)._store(1, feats)
        left = {r[0]: r[1:] for r in conn.execute("SELECT id, subject_id, assignment FROM occurrences")}
        assert left[1] == (1, "manual")  # the user's assignment is kept
        assert 2 not in left  # an automatic box no longer detected goes
        assert len(left) == 2
