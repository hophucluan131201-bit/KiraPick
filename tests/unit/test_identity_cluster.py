"""Grouping rules on synthetic embeddings with known ground truth."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.identity import actions
from app.identity.cluster import AUTO_PAIR, Occ, group, merge_suggestions, recluster
from app.storage.project import Project

RNG = np.random.default_rng(7)


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def _person() -> np.ndarray:
    return _unit(RNG.normal(size=128))


def _shot(identity: np.ndarray, noise: float = 0.4) -> np.ndarray:
    """A face of `identity` in another photo; noise 0.4 -> ~0.86 similarity between two shots."""
    return _unit(identity + _unit(RNG.normal(size=128)) * noise)


def _blend(a: np.ndarray, similarity: float) -> np.ndarray:
    """A different face whose cosine similarity to `a` is exactly `similarity`."""
    other = RNG.normal(size=128)
    other = _unit(other - (other @ a) * a)  # orthogonal to a
    return _unit(similarity * a + (1 - similarity**2) ** 0.5 * other)


def _occ(i: int, asset: int, face=None, outfit=None, t: float | None = 0.0, **kw) -> Occ:  # noqa: ANN001
    return Occ(i, asset, t, face, outfit, kw.get("assignment", "none"), kw.get("subject_id"), kw.get("excluded"))


def _members(groups, occs) -> list[set[int]]:  # noqa: ANN001
    return sorted((sorted({occs[m].id for m in g.members}) for g in groups if g.members), key=lambda s: s[0])


def test_same_people_group_and_strangers_stay_apart() -> None:
    a, b = _person(), _person()
    occs = [_occ(1, 1, _shot(a)), _occ(2, 2, _shot(a)), _occ(3, 3, _shot(a)), _occ(4, 4, _shot(b)), _occ(5, 5, _shot(b))]
    assert float(occs[0].face @ occs[1].face) > 0.8 and abs(float(occs[0].face @ occs[3].face)) < 0.3
    groups, _ = group(occs)
    assert _members(groups, occs) == [[1, 2, 3], [4, 5]]


def test_two_people_in_one_photo_are_never_merged() -> None:
    a = _person()
    twin_look = _shot(a, 0.1)  # e.g. twins / identical makeup in the same photo
    occs = [_occ(1, 10, _shot(a, 0.1)), _occ(2, 10, twin_look)]
    groups, _ = group(occs)
    assert _members(groups, occs) == [[1], [2]]


def test_no_chaining_through_a_middle_face() -> None:
    a, c = _person(), _person()
    middle = _unit(a + c)  # resembles both
    occs = [_occ(1, 1, a), _occ(2, 2, middle), _occ(3, 3, c)]
    groups, _ = group(occs)
    assert not any({1, 3} <= set(m) for m in _members(groups, occs)), "A and C must not end up together"


def test_faceless_photo_only_suggested_by_outfit_within_time_window() -> None:
    a = _person()
    red = _unit(np.r_[np.ones(10), np.zeros(118)])
    blue = _unit(np.r_[np.zeros(118), np.ones(10)])
    occs = [
        _occ(1, 1, _shot(a), red, t=0), _occ(2, 2, _shot(a), red, t=30),
        _occ(3, 3, None, red, t=120),       # back view, same outfit, 2 min later -> suggestion
        _occ(4, 4, None, red, t=60 * 60),   # same outfit an hour later -> nothing
        _occ(5, 5, None, blue, t=60),       # other outfit -> nothing
    ]
    groups, suggestions = group(occs)
    assert _members(groups, occs) == [[1, 2]]
    assert {occs[i].id for i in suggestions} == {3}


def test_manual_and_excluded_constraints() -> None:
    a = _person()
    occs = [
        _occ(1, 1, _shot(a), assignment="manual", subject_id=7),
        _occ(2, 2, _shot(a)),
        _occ(3, 3, _shot(a), excluded=7),  # user removed this photo from subject 7
    ]
    groups, _ = group(occs)
    by_fixed = {g.fixed_subject: sorted(occs[m].id for m in g.members) for g in groups if g.members}
    assert by_fixed[7] == [1, 2]
    assert [3] in by_fixed.values()


# ---------------------------------------------------------------- with a DB


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "s", "x")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    yield p
    p.close()


def _add(p: Project, asset: int, face: np.ndarray | None, *, minute: int = 0, main: int = 1) -> int:
    conn = p.conn
    if not conn.execute("SELECT 1 FROM assets WHERE id = ?", (asset,)).fetchone():
        conn.execute(
            """INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, capture_time, added_at, updated_at)
               VALUES (?, 1, ?, '.nef', 'raw', 'verified', 1, 1, ?, 'ok', ?, 'n', 'n')""",
            (asset, f"DSC_{asset:04d}.NEF", str(asset), f"2026-10-25T10:{minute:02d}:00"),
        )
    occ = int(conn.execute(
        """INSERT INTO occurrences (asset_id, person_box, prominence, is_main, analysis_version, created_at)
           VALUES (?, ?, 1.0, ?, 1, 'n')""", (asset, json.dumps([0.1, 0.1, 0.5, 0.8]), main)).lastrowid)
    if face is not None:
        conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'face', 't', ?)", (occ, face.astype("<f4").tobytes()))
    return occ


def _subjects(p: Project) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for r in p.conn.execute("SELECT subject_id, asset_id FROM occurrences WHERE subject_id IS NOT NULL ORDER BY asset_id"):
        out.setdefault(r[0], []).append(r[1])
    return out


def test_recluster_is_stable_and_respects_corrections(project: Project) -> None:
    a, b = _person(), _person()
    for asset in (1, 2, 3):
        _add(project, asset, _shot(a))
    for asset in (4, 5):
        _add(project, asset, _shot(b))
    _add(project, 6, _shot(b), main=0)  # background passer-by
    recluster(project)
    first = _subjects(project)
    assert sorted(first.values()) == [[1, 2, 3], [4, 5]]
    sid_a = next(s for s, v in first.items() if v == [1, 2, 3])
    sid_b = next(s for s, v in first.items() if v == [4, 5])

    recluster(project)  # running again changes nothing, ids stay
    assert _subjects(project) == first

    actions.rename_subject(project.conn, sid_a, "Aki")
    actions.remove_photos_from_subject(project.conn, sid_a, [3])
    _add(project, 7, _shot(a))  # a new photo of Aki arrives
    recluster(project)
    now = _subjects(project)
    assert now[sid_a] == [1, 2, 7] and 3 not in sum(now.values(), [])
    assert actions.subject_label(project.conn, sid_a) == "Aki"

    actions.merge_subjects(project.conn, sid_a, sid_b)  # user: same person after all
    recluster(project)
    assert _subjects(project) == {sid_a: [1, 2, 4, 5, 7]}


def test_review_suggestions_and_mark_different(project: Project) -> None:
    a = _person()
    near = _blend(a, 0.48)  # similar-ish face (heavy makeup?), between SUGGEST and AUTO_PAIR
    _add(project, 1, a)
    _add(project, 2, near)
    recluster(project)
    subjects = list(_subjects(project))
    assert len(subjects) == 2
    sims = merge_suggestions(project.conn)
    assert len(sims) == 1 and sims[0].similarity < AUTO_PAIR
    actions.mark_different(project.conn, *subjects)
    assert merge_suggestions(project.conn) == []
    recluster(project)
    assert len(_subjects(project)) == 2
