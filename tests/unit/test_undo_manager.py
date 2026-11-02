"""F3 Batch 1a/1b: UndoManager — exact restore, persistence, LIFO, bounds, refusal, learning ids and recovery."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.identity import actions
from app.identity.cluster import recluster
from app.learning.store import OP_BASE, RESERVATION_VERSION, LearningStore
from app.learning.teacher import Teacher
from app.storage import decisions
from app.storage.project import Project
from app.storage.project_config import picks_stale, read_config
from app.undo import manager as um
from app.undo.manager import UndoManager, UndoRefused

RNG = np.random.default_rng(3)


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def _add(p: Project, asset: int, face: np.ndarray, minute: int, main: int = 1) -> int:
    conn = p.conn
    if not conn.execute("SELECT 1 FROM assets WHERE id = ?", (asset,)).fetchone():
        conn.execute(
            """INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, capture_time, added_at, updated_at)
               VALUES (?, 1, ?, '.jpg', 'raster', 'verified', 1, 1, ?, 'ok', ?, 'n', 'n')""",
            (asset, f"P_{asset:04d}.JPG", str(asset), f"2026-10-25T10:{minute:02d}:00"))
    occ = int(conn.execute("""INSERT INTO occurrences (asset_id, person_box, prominence, is_main, analysis_version,
                               created_at) VALUES (?, '[0.1,0.1,0.5,0.8]', 1.0, ?, 1, 'n')""", (asset, main)).lastrowid)
    conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'face', 't', ?)", (occ, face.astype("<f4").tobytes()))
    return occ


def _shot(identity: np.ndarray) -> np.ndarray:
    return _unit(identity + _unit(RNG.normal(size=128)) * 0.3)


@pytest.fixture()
def world(tmp_path: Path):
    """Three people, a few photos each, one photo with two of them; grouped automatically; learning available."""
    p = Project.create(tmp_path / "s", "x")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    people = [_unit(RNG.normal(size=128)) for _ in range(3)]
    asset = 0
    for k, person in enumerate(people):
        for _ in range(3):
            asset += 1
            _add(p, asset, _shot(person), minute=k * 10)
    _add(p, 1, _shot(people[1]), minute=0)  # photo 1 also shows person 2
    recluster(p)
    p.conn.commit()
    store = LearningStore(tmp_path / "learning")
    teacher = Teacher(store)
    yield p, teacher, tmp_path
    store.close()
    p.close()


def _rows(p: Project) -> dict:
    c = p.conn
    return {
        "occ": c.execute("SELECT id, subject_id, assignment, confidence, excluded_subject_id FROM occurrences "
                         "ORDER BY id").fetchall(),
        "subj": c.execute("SELECT id, display_name, user_locked, merged_into, created_at FROM subjects "
                          "ORDER BY id").fetchall(),
        "pairs": c.execute("SELECT a, b, relation, created_at FROM subject_pairs ORDER BY a, b").fetchall(),
        "dec": c.execute("SELECT asset_id, flag, rating, favorite, focus, updated_at FROM decisions "
                         "ORDER BY asset_id").fetchall(),
    }


def _subjects(p: Project) -> list[int]:
    return [r[0] for r in p.conn.execute("SELECT id FROM subjects ORDER BY id")]


def _learning_rows(store: LearningStore) -> list[tuple]:
    return [tuple(r) for r in store.conn.execute(
        "SELECT id, kind, same, answer_id, outfit_version = ? FROM identity_feedback ORDER BY id",
        (RESERVATION_VERSION,)).fetchall()]


# ------------------------------------------------------------------ exact restore per action
def test_each_subject_action_undoes_exactly(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2, s3 = _subjects(p)[:3]
    steps = [
        ("rename", lambda c: actions.rename_subject(c, s1, "Mai")),
        ("different", lambda c: (teacher.different(c, s2, s3), actions.mark_different(c, s2, s3))),
        ("unmark", lambda c: actions.unmark_different(c, s2, s3)),
        ("assign", lambda c: (actions.assign_photos_to_subject(c, s1, [4]), teacher.assigned(c, s1, [4]))),
        ("remove", lambda c: (teacher.removed(c, s1, [2]), actions.remove_photos_from_subject(c, s1, [2]))),
        ("create", lambda c: actions.create_subject(c, [3], "Moi", s1)),
        ("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher)),
    ]
    snapshots = []
    for label, fn in steps:
        snapshots.append(_rows(p))
        assert m.subject_action(label, fn) is True, label
    for label, _ in reversed(steps):  # LIFO, each back to exactly the state before it
        assert m.next_label() == label
        m.undo()
        assert _rows(p) == snapshots.pop(), label
    assert not m.can_undo()


def test_merge_carries_different_marks_and_refuses_conflicts(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2, s3 = _subjects(p)[:3]
    m.subject_action("diff", lambda c: actions.mark_different(c, s2, s3))
    before = _rows(p)
    with pytest.raises(actions.MergeConflict):
        m.subject_action("merge", lambda c: actions.merge_look(c, s2, [s3]))
    assert _rows(p) == before and m.next_label() == "diff"  # nothing changed, no entry
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2]))  # s2's mark against s3 moves to s1
    assert actions.are_different(p.conn, s1, s3)
    m.undo()
    assert _rows(p) == before
    m.subject_action("merge2", lambda c: actions.merge_look(c, s2, [s3], unmark_conflicts=True))  # explicit choice
    assert not actions.are_different(p.conn, s2, s3)
    m.undo()
    assert _rows(p) == before


def test_history_survives_reopening_and_decisions_do_not(world) -> None:
    p, teacher, tmp = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]
    original = _rows(p)
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher))
    with p.transaction() as conn:
        before = m.capture_decisions(conn, [5])
        decisions.set_flag(conn, 5, "keep")
    m.push_decisions("keep", before)
    assert m.next_label() == "keep"
    folder = p.folder
    p.close()
    q = Project.open(folder)
    try:
        m2 = UndoManager(q, teacher)
        assert m2.next_label() == "merge" and len(m2) == 1  # the decision entry was memory-only
        m2.undo()
        rows = _rows(q)
        assert rows["occ"] == original["occ"] and rows["subj"] == original["subj"]
        assert decisions.get(q.conn, 5).flag == "keep"  # not undone after reopening (stated in the UI)
    finally:
        q.close()
    p.conn = Project.open(folder).conn  # the fixture closes it


def test_unified_lifo_across_kinds(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1 = _subjects(p)[0]
    order = []
    for i in range(3):
        with p.transaction() as conn:
            before = m.capture_decisions(conn, [1])
            decisions.set_rating(conn, 1, i + 1)
        m.push_decisions(f"rate{i}", before)
        order.append(f"rate{i}")
        m.subject_action(f"name{i}", lambda c, i=i: actions.rename_subject(c, s1, f"N{i}"))
        order.append(f"name{i}")
    seen = []
    while m.can_undo():
        seen.append(m.next_label())
        m.undo()
    assert seen == list(reversed(order))
    assert decisions.get(p.conn, 1).rating == 0 and actions.subject_label(p.conn, s1) == f"Chủ thể {s1}"


def test_decision_undo_restores_row_or_its_absence(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    with p.transaction() as conn:
        decisions.set_flag(conn, 2, "reject")
        decisions.set_focus(conn, 2, "soft")
    original = _rows(p)["dec"]
    with p.transaction() as conn:
        before = m.capture_decisions(conn, [2, 3])
        decisions.set_flag(conn, 2, "keep")
        decisions.set_favorite(conn, 3, True)
        decisions.set_focus(conn, 2, "sharp")
    m.push_decisions("multi", before)
    result = m.undo()
    assert result.kind == "decision" and set(result.asset_ids) == {2, 3}
    assert _rows(p)["dec"] == original  # photo 3 had no row: it has none again


def test_failed_or_empty_action_leaves_no_entry_and_no_reservation(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]
    before, learn_before = _rows(p), _learning_rows(teacher.store)

    def boom(conn) -> None:  # noqa: ANN001
        teacher.merged(conn, s1, s2)
        actions.merge_subjects(conn, s1, s2)
        raise RuntimeError("cancelled half-way")

    with pytest.raises(RuntimeError):
        m.subject_action("boom", boom)
    assert _rows(p) == before and not m.can_undo() and _learning_rows(teacher.store) == learn_before
    assert m.subject_action("noop", lambda c: actions.rename_subject(c, s1, "")) is False  # nothing changed


# ------------------------------------------------------------------ refusal, bounds, renumbering
def test_undo_refused_when_a_moved_photo_was_changed_since(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2, s3 = _subjects(p)[:3]
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2]))
    moved = p.conn.execute("SELECT id FROM occurrences WHERE subject_id = ? AND assignment = 'manual' LIMIT 1",
                           (s1,)).fetchone()[0]
    with p.transaction() as conn:  # a later change outside the history (e.g. an older app version)
        conn.execute("UPDATE occurrences SET subject_id = ? WHERE id = ?", (s3, moved))
    after = _rows(p)
    with pytest.raises(UndoRefused):
        m.undo()
    assert _rows(p) == after and not m.can_undo()  # nothing changed; the entry is gone (told to the user)


def test_released_photos_are_restored_even_if_regrouped_since(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]
    original = _rows(p)
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2]))  # photo 1 shows both: one is released
    recluster(p)
    m.undo()
    assert _rows(p)["subj"] == original["subj"]
    assert {r[0]: r[1] for r in _rows(p)["occ"]} == {r[0]: r[1] for r in original["occ"]}


def test_bounds_keep_the_newest_entries(world, monkeypatch) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1 = _subjects(p)[0]
    for i in range(um.MAX_PERSISTED + 5):
        m.subject_action(f"r{i}", lambda c, i=i: actions.rename_subject(c, s1, f"Ten {i}"))
    journal = read_config(p.conn)[um.JOURNAL_KEY]
    assert len(journal) == um.MAX_PERSISTED and journal[-1]["label"] == f"r{um.MAX_PERSISTED + 4}"
    assert len(json.dumps(journal)) <= um.MAX_BYTES
    monkeypatch.setattr(um, "MAX_BYTES", 10)  # a correction whose undo record cannot be kept is refused
    with pytest.raises(um.UndoTooLarge):
        m.subject_action("big", lambda c: actions.rename_subject(c, s1, "Lon"))
    assert actions.subject_label(p.conn, s1) == f"Ten {um.MAX_PERSISTED + 4}"


def test_oversized_merge_is_refused_and_changes_nothing(world, monkeypatch) -> None:
    """P0: fail closed — no merge without undo protection; session and learning databases unchanged."""
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]
    m.subject_action("r", lambda c: actions.rename_subject(c, s1, "Mai"))
    before, learn_before = _rows(p), _learning_rows(teacher.store)
    journal_before = read_config(p.conn)[um.JOURNAL_KEY]
    monkeypatch.setattr(um, "MAX_BYTES", 400)  # the merge record (~450 bytes here) cannot fit
    with pytest.raises(um.UndoTooLarge):
        m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher))
    assert _rows(p) == before and _learning_rows(teacher.store) == learn_before
    assert read_config(p.conn)[um.JOURNAL_KEY] == journal_before and m.next_label() == "r"
    monkeypatch.setattr(um, "MAX_BYTES", 1_000_000)
    assert m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher))  # fits again


def test_renumbering_clears_the_subject_history(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1 = _subjects(p)[0]
    m.subject_action("r", lambda c: actions.rename_subject(c, s1, "A"))
    with p.transaction() as conn:
        actions.renumber_subjects(conn)
        m.clear_subject_history(conn)
    assert not m.can_undo() and um.JOURNAL_KEY not in read_config(p.conn)


def test_picks_stale_flag_is_set_by_merge_and_undone(world) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]
    run = p.conn.execute("INSERT INTO pick_runs (created_at, params_json) VALUES ('n', '{}')").lastrowid
    p.conn.execute("INSERT INTO picks (run_id, asset_id, subject_id, rank, score, reason_json) VALUES (?, 4, ?, 1, 1, '{}')",
                   (run, s2))
    p.conn.commit()
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2]))
    assert picks_stale(p.conn)
    m.undo()
    assert not picks_stale(p.conn)


# ------------------------------------------------------------------ learning: operation ids and recovery
def test_learning_examples_carry_the_operation_id_and_undo_removes_only_them(world) -> None:
    p, teacher, _ = world
    store = teacher.store
    m = UndoManager(p, teacher)
    s1, s2, s3 = _subjects(p)[:3]
    with p.transaction() as conn:  # an ordinary (non-undoable) answer from before
        teacher.different(conn, s1, s3)
    ordinary = _learning_rows(store)
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher))
    op_rows = [r for r in _learning_rows(store) if r not in ordinary]
    op_ids = {r[3] for r in op_rows}
    assert len(op_ids) == 1 and next(iter(op_ids)) <= OP_BASE
    assert sum(1 for r in op_rows if r[4]) == 1 and all(r[1] == "merge" for r in op_rows)  # 1 reservation
    examples = store.identity_examples()  # reservation rows are never examples
    assert len(examples) == sum(1 for r in _learning_rows(store) if not r[4])
    assert store.identity_counts()["same"] + store.identity_counts()["different"] == len(examples)
    with p.transaction() as conn:  # a later ordinary answer still gets MAX+1 of the positive ids
        teacher.different(conn, s1, s3)
    assert max(r[3] for r in _learning_rows(store)) == max(r[3] for r in ordinary) + 1
    m.undo()
    assert [r for r in _learning_rows(store) if r[3] in op_ids] == []
    assert all(r in _learning_rows(store) for r in ordinary)


def test_two_stores_allocate_distinct_operation_ids(world) -> None:
    _, teacher, tmp = world
    other = LearningStore(tmp / "learning")
    try:
        ids = [teacher.store.reserve_operation(), other.reserve_operation(), teacher.store.reserve_operation()]
    finally:
        other.close()
    assert len(set(ids)) == 3 and all(i <= OP_BASE for i in ids)


def test_crash_after_commit_before_learning_write_is_recovered(world, monkeypatch) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]

    def crash(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise KeyboardInterrupt  # the process dies between the session commit and the learning write

    monkeypatch.setattr(teacher, "write_collected", crash)
    with pytest.raises(KeyboardInterrupt):
        m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher))
    journal = read_config(p.conn)[um.JOURNAL_KEY]
    assert journal[-1]["learning"] == "reserved"
    monkeypatch.undo()
    m2 = UndoManager(p, teacher)  # next open
    assert read_config(p.conn)[um.JOURNAL_KEY][-1]["learning"] == "none"
    op_id = journal[-1]["op_id"]
    m2.undo()
    assert teacher.store.conn.execute("SELECT COUNT(*) FROM identity_feedback WHERE answer_id = ?",
                                      (op_id,)).fetchone()[0] == 0  # the reservation is gone too


def test_crash_between_undo_commit_and_learning_cleanup_is_retried(world, monkeypatch) -> None:
    p, teacher, _ = world
    m = UndoManager(p, teacher)
    s1, s2 = _subjects(p)[:2]
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2], teacher=teacher))
    op_id = read_config(p.conn)[um.JOURNAL_KEY][-1]["op_id"]
    real = teacher.store.delete_operation

    def fail(_op: int) -> int:
        raise OSError("disk")

    monkeypatch.setattr(teacher.store, "delete_operation", fail)
    m.undo()  # the session is restored; the learning cleanup is recorded
    assert read_config(p.conn)[um.CLEANUP_KEY] == [op_id]
    monkeypatch.setattr(teacher.store, "delete_operation", real)
    UndoManager(p, teacher)  # next open: retried
    UndoManager(p, teacher)  # and again: idempotent
    assert um.CLEANUP_KEY not in read_config(p.conn)
    assert teacher.store.conn.execute("SELECT COUNT(*) FROM identity_feedback WHERE answer_id = ?",
                                      (op_id,)).fetchone()[0] == 0


def test_without_learning_the_history_still_works(world) -> None:
    p, _, _ = world
    m = UndoManager(p, Teacher(None))
    s1, s2 = _subjects(p)[:2]
    before = _rows(p)
    m.subject_action("merge", lambda c: actions.merge_look(c, s1, [s2]))
    m.undo()
    assert _rows(p) == before
