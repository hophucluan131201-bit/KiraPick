"""Learning examples from the user's people corrections."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.identity import actions
from app.identity.cluster import recluster
from app.learning.store import LearningStore
from app.learning.teacher import Teacher
from app.storage.project import Project
from tests.unit.test_identity_cluster import RED, _add, _blend, _person, _shot, _subjects


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "s", "x")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    yield p
    p.close()


def test_corrections_become_examples_with_numbers_only(project: Project, tmp_path: Path) -> None:
    a, b = _person(), _person()
    for asset in (1, 2):
        _add(project, asset, _shot(a), outfit=RED)
    _add(project, 3, _blend(a, 0.5), minute=3, outfit=RED)  # same person, unusual face: split
    _add(project, 4, _shot(b), minute=5)
    recluster(project)
    subj = {tuple(v): s for s, v in _subjects(project).items()}
    store = LearningStore(tmp_path / "learning")
    teacher = Teacher(store)

    with project.transaction() as conn:  # the user merges the straggler
        teacher.merged(conn, subj[(1, 2)], subj[(3,)])
        actions.merge_subjects(conn, subj[(1, 2)], subj[(3,)])
        teacher.different(conn, subj[(1, 2)], subj[(4,)])
        actions.mark_different(conn, subj[(1, 2)], subj[(4,)])
    rows = store.conn.execute("SELECT kind, same, face, outfit, dt_s FROM identity_feedback ORDER BY id").fetchall()
    merges = [r for r in rows if r[0] == "merge"]
    assert len(merges) == 2 and all(r[1] == 1 for r in merges)
    assert all(abs(r[2] - 0.5) < 0.2 and r[3] > 0.99 and r[4] == 180 for r in merges)
    assert {r[0] for r in rows if r[1] == 0} == {"different"}
    assert store.identity_counts() == {"same": 2, "different": 3}

    columns = {r[1] for r in store.conn.execute("PRAGMA table_info(identity_feedback)")}
    assert not columns & {"path", "file", "name", "asset_id", "capture_time"}  # nothing identifying

    with project.transaction() as conn:  # remove photo 2: it is someone else after all
        teacher.removed(conn, subj[(1, 2)], [2])
        actions.remove_photos_from_subject(conn, subj[(1, 2)], [2])
    assert store.identity_counts()["different"] == 5  # photo 2 vs photos 1 and 3

    store.forget()
    assert store.identity_counts() == {"same": 0, "different": 0}
    store.close()


def test_learning_never_blocks_a_correction(project: Project, tmp_path: Path) -> None:
    a = _person()
    _add(project, 1, _shot(a))
    _add(project, 2, _shot(a))
    recluster(project)
    [sid] = _subjects(project)
    store = LearningStore(tmp_path / "learning")
    store.conn.close()  # broken store (disk gone, file locked ...)
    teacher = Teacher(store)
    with project.transaction() as conn:
        teacher.removed(conn, sid, [2])
        assert actions.remove_photos_from_subject(conn, sid, [2]) == 1
    assert Teacher(None).merged(project.conn, sid, sid) is None  # no store: nothing happens


def test_store_from_a_newer_app_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "learning"
    LearningStore(folder).close()
    conn = sqlite3.connect(folder / "learning.db")
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    with pytest.raises(RuntimeError):
        LearningStore(folder)


def test_examples_use_closest_photos_in_time_and_cap() -> None:
    from app.identity.cluster import Occ
    from app.learning.teacher import evidence

    f = np.ones(4, np.float32) / 2
    a = [Occ(i, i, float(i), f, None, "auto", 1, None) for i in range(30)]
    b = [Occ(100 + i, 100 + i, 1000.0 + i, f, None, "auto", 2, None) for i in range(30)]
    pairs = evidence(a, b, limit=10)
    assert len(pairs) == 10 and pairs[0].dt_s == 1000 - 29 and pairs[0].outfit is None


def test_keep_reject_examples_and_upgrade_from_v1(tmp_path: Path) -> None:
    from app.quality.score import score

    folder = tmp_path / "learning"
    folder.mkdir()
    old = sqlite3.connect(folder / "learning.db")  # a v1 store (people examples only) from the previous app
    from app.learning import store as store_module

    old.executescript(store_module._SCHEMA)
    old.execute("INSERT INTO identity_feedback (created_on, app_version, face_version, outfit_version, kind, same) "
                "VALUES ('2026-10-27', 'x', 'f', 'o', 'merge', 1)")
    old.execute("PRAGMA user_version = 1")
    old.commit()
    old.close()
    store = LearningStore(folder)
    assert store.identity_counts()["same"] == 1  # kept through the upgrade
    teacher = Teacher(store)
    s = score({"eye_sharp": 0.5, "face_quality": 0.6, "face_clip": 0.0, "face_luma": 50, "area": 0.3})
    from app.learning.teacher import photo_key
    from app.storage.decisions import Decision

    teacher.decided(photo_key("s", 1), Decision("keep"), s.parts, None, "g")
    teacher.decided(photo_key("s", 2), Decision("reject"), s.parts, None, "g")
    teacher.decided(photo_key("s", 3), Decision(None), s.parts, None, "g")  # nothing chosen teaches nothing
    rows = store.conn.execute("SELECT decision, label, focus FROM culling_feedback ORDER BY id").fetchall()
    assert rows == [("keep", 1, s.parts["focus"]), ("reject", -1, s.parts["focus"])]
    store.forget()
    assert store.culling_count() == 0
    store.close()
