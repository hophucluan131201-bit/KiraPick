"""C5 (LIC-1 S5, PROV-1 b): a 3.0.0 session and learning.db open in this build without using what the removed or
unverified weights produced, and without deleting anything.

U4: stored ArcFace / ReID vectors, TOPIQ values and results of unknown source are not used; the analysis is asked
to run again; user rows are unchanged. U5: learning.db keeps its ArcFace / ReID columns and values, but they are
neither read nor written. U15: focus learning works without the TOPIQ technical value.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from app.learning.store import DB_NAME, LearningStore, PairEvidence
from app.storage import db, provenance, workflow
from tests.unit.test_provenance import USER_ROWS, _dump, _v7_session


def _upgraded(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    path = tmp_path / "project.snorlu.db"
    _v7_session(path)
    return path, db.connect(path)


def test_old_session_results_are_not_used_and_the_analysis_is_asked_again(tmp_path: Path) -> None:
    from app.identity.cluster import SFACE_HSV, load_occurrences, session_profile
    from app.quality.score import occurrence_scores

    path, conn = _upgraded(tmp_path)
    try:
        assert session_profile(conn) is SFACE_HSV
        conn.execute("UPDATE assets SET status = 'ok'")  # readable photos (the fixture leaves the default)
        occs = load_occurrences(conn)
        assert occs and all(o.face is None and o.face_arc is None and o.body is None for o in occs)
        assert occurrence_scores(conn) == {}  # measurements of unknown source: not scored
        states = {r[0] for r in conn.execute("SELECT DISTINCT state FROM stage_status WHERE stage IN ('detect', "
                                             "'quality')")}
        assert states <= {"pending"}
        steps = workflow.steps(conn, importing=None)
        # the automatic occurrence (assignment 'auto') of unknown source asks for a new run; measurements too
        assert steps["people"] == workflow.StepState(False, workflow.UNKNOWN_SOURCE)
        assert steps["quality"] == workflow.StepState(False, workflow.UNKNOWN_SOURCE)
        assert provenance.unknown_source_summary(conn)["occurrence_vectors"] == 2  # kept, not deleted
    finally:
        conn.close()


def test_old_values_of_unverified_weights_are_dropped_from_scoring() -> None:
    from app.quality.score import score, usable_values

    v = {"eye_sharp": 0.8, "aesthetic_mos": 6.5, "tech_iqa": 0.9, "face_iqa": 0.9, "laion_mos": 6.0,
         "style_tags": [["low_key", 0.1]]}
    u = usable_values(v)
    assert u["eye_sharp"] == 0.8
    assert all(u[k] is None for k in ("aesthetic_mos", "tech_iqa", "face_iqa", "laion_mos", "style_tags"))
    assert "aesthetic" not in {k for k, val in score(u).parts.items() if val is not None}


def test_learning_db_arcface_columns_are_kept_but_never_read_or_written(tmp_path: Path) -> None:
    """U5."""
    from app.identity.cluster import SFACE_HSV
    from app.learning.tuning import tune

    store = LearningStore(tmp_path / "learning")
    store.add_identity("merge", True, [PairEvidence(0.6, 0.9, 10.0, face_arc=0.8, body=0.7)], "sface", "hsv",
                       "arcface-w600k-r50", "youtu")  # as 3.0.0 wrote it
    [ex] = store.identity_examples()
    assert ex.pair.face == 0.6 and ex.pair.face_arc is None and ex.pair.body is None  # not read
    tune([ex], SFACE_HSV)  # tuning on SFace only, no error
    store.close()
    conn = sqlite3.connect(tmp_path / "learning" / DB_NAME)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(identity_feedback)")}
        assert {"face_arc", "body"} <= cols  # columns kept
        assert conn.execute("SELECT face_arc, body FROM identity_feedback").fetchone() == (0.8, 0.7)  # values kept
    finally:
        conn.close()


def test_focus_learning_without_the_topiq_value() -> None:
    """U15."""
    from app.learning import focus

    assert "tech_iqa" not in focus.FEATURES
    ex = [focus.FocusExample(i % 3, f"d{i % 4}", "cam", {"eye_sharp": 0.9 - 0.3 * (i % 3), "tech_iqa": 0.5,
                                                         "face_sharp": None, "body_sharp": None, "sharp_scale": 1.0})
          for i in range(30)]
    model = focus._fit_model(ex)
    assert 0 <= model.score({"eye_sharp": 0.9, "tech_iqa": 0.1}) <= 100


def test_user_rows_survive_open_and_rerun_marking(tmp_path: Path) -> None:
    path = tmp_path / "project.snorlu.db"
    _v7_session(path)
    before = {q: _dump(path, q) for q in USER_ROWS}
    db.connect(path).close()
    assert {q: _dump(path, q) for q in USER_ROWS} == before
    np.testing.assert_equal(_dump(path, "SELECT COUNT(*) FROM measurements"), [(2,)])
