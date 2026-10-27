"""Grouping rules on synthetic embeddings with known ground truth."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.identity import actions
from app.identity.cluster import FACE_STRONG, Occ, group, merge_suggestions, recluster
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
    groups = group(occs).groups
    assert _members(groups, occs) == [[1, 2, 3], [4, 5]]


def test_two_people_in_one_photo_are_never_merged() -> None:
    a = _person()
    twin_look = _shot(a, 0.1)  # e.g. twins / identical makeup in the same photo
    occs = [_occ(1, 10, _shot(a, 0.1)), _occ(2, 10, twin_look)]
    groups = group(occs).groups
    assert _members(groups, occs) == [[1], [2]]


def test_no_chaining_through_a_middle_face() -> None:
    a, c = _person(), _person()
    middle = _unit(a + c)  # resembles both
    occs = [_occ(1, 1, a), _occ(2, 2, middle), _occ(3, 3, c)]
    groups = group(occs).groups
    assert not any({1, 3} <= set(m) for m in _members(groups, occs)), "A and C must not end up together"


RED = _unit(np.r_[np.ones(10), np.zeros(118)])
BLUE = _unit(np.r_[np.zeros(118), np.ones(10)])
PINK = _unit(np.r_[np.ones(9), np.zeros(118), np.ones(1) * 1.2])  # ~0.88 like RED: similar colours


def test_faceless_photo_joins_by_outfit_within_time_window_as_suggestion() -> None:
    a = _person()
    occs = [
        _occ(1, 1, _shot(a), RED, t=0), _occ(2, 2, _shot(a), RED, t=30),
        _occ(3, 3, None, RED, t=120),       # back view, same outfit, 2 min later -> joins, only suggested
        _occ(4, 4, None, RED, t=60 * 60),   # same outfit an hour later -> nothing
        _occ(5, 5, None, BLUE, t=60),       # other outfit -> nothing
    ]
    result = group(occs)
    assert _members(result.groups, occs) == [[1, 2, 3]]
    assert {occs[i].id for i in result.weak} == {3} and not result.suggestions


def test_faceless_photos_form_a_person_only_together() -> None:
    occs = [_occ(1, 1, None, BLUE, t=0), _occ(2, 2, None, BLUE, t=40), _occ(3, 3, None, RED, t=60)]
    result = group(occs)
    assert _members(result.groups, occs) == [[1, 2]]  # lone face-less photo 3 is no person of its own
    assert {occs[i].id for i in result.weak} == {1, 2}


def test_same_look_links_a_weaker_face_but_lookalike_cosplayers_stay_apart() -> None:
    """Calibration case: two cosplayers in similar pink, minutes apart, faces ~0.5 similar."""
    a, b = _person(), _person()
    straggler = _blend(a, 0.58)  # same person, unusual angle: face too weak alone
    other = _blend(a, 0.50)  # another cosplayer with similar makeup
    occs = [
        _occ(1, 1, a, RED, t=0), _occ(2, 2, _shot(a, 0.2), RED, t=60),
        _occ(3, 3, straggler, RED, t=200),  # same outfit + face >= 0.55 -> same person
        _occ(4, 4, other, PINK, t=120),  # similar outfit but face < 0.55 -> stays apart
        _occ(5, 5, _shot(b), BLUE, t=150),
    ]
    assert float(RED @ PINK) > 0.85
    groups = group(occs).groups
    assert _members(groups, occs) == [[1, 2, 3], [4], [5]]


def test_same_outfit_far_apart_in_time_does_not_link() -> None:
    a = _person()
    occs = [_occ(1, 1, a, RED, t=0), _occ(2, 2, _blend(a, 0.58), RED, t=3600)]
    assert _members(group(occs).groups, occs) == [[1], [2]]


def test_manual_and_excluded_constraints() -> None:
    a = _person()
    occs = [
        _occ(1, 1, _shot(a), assignment="manual", subject_id=7),
        _occ(2, 2, _shot(a)),
        _occ(3, 3, _shot(a), excluded=7),  # user removed this photo from subject 7
    ]
    groups = group(occs).groups
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


def _add(p: Project, asset: int, face: np.ndarray | None, *, minute: int = 0, main: int = 1,
         outfit: np.ndarray | None = None) -> int:
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
    if outfit is not None:
        conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'outfit', 't', ?)", (occ, outfit.astype("<f4").tobytes()))
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
    near = _blend(a, 0.50)  # similar-ish face (heavy makeup?), below the automatic level
    _add(project, 1, a, outfit=RED)
    _add(project, 2, near, minute=1, outfit=_blend(RED, 0.78))  # outfit close, but not enough to link
    recluster(project)
    subjects = list(_subjects(project))
    assert len(subjects) == 2
    sims = merge_suggestions(project.conn)
    assert len(sims) == 1 and sims[0].similarity < FACE_STRONG and sims[0].look == pytest.approx(0.78, abs=0.01)
    actions.mark_different(project.conn, *subjects)
    assert merge_suggestions(project.conn) == []
    recluster(project)
    assert len(_subjects(project)) == 2


def test_lookalike_faces_in_different_costumes_are_not_asked_about(project: Project) -> None:
    """Owner's report: face 0.55, clearly different costumes -> do not ask."""
    a = _person()
    _add(project, 1, a, outfit=RED)
    _add(project, 2, _blend(a, 0.55), minute=1, outfit=BLUE)
    recluster(project)
    assert len(_subjects(project)) == 2
    assert merge_suggestions(project.conn) == []


def test_recluster_marks_faceless_members_as_suggested(project: Project) -> None:
    a = _person()
    _add(project, 1, _shot(a), outfit=RED)
    _add(project, 2, _shot(a), minute=1, outfit=RED)
    back = _add(project, 3, None, minute=2, outfit=RED)
    report = recluster(project)
    assert list(_subjects(project).values()) == [[1, 2, 3]]
    row = project.conn.execute("SELECT assignment, confidence FROM occurrences WHERE id = ?", (back,)).fetchone()
    assert row["assignment"] == "suggested" and row["confidence"] > 0.85
    assert (report.auto, report.suggested) == (2, 1)


def test_lookalike_faces_hours_apart_need_the_same_outfit() -> None:
    """Owner's report: a Peach cosplayer and a Miku cosplayer, hours apart, merged by one 0.67 face pair."""
    a, b = _person(), _person()
    hours = 3 * 3600
    lookalike = _blend(a, 0.67)
    occs = [_occ(1, 1, a, RED, t=0), _occ(2, 2, _shot(a, 0.2), RED, t=30),
            _occ(3, 3, lookalike, BLUE, t=hours), _occ(4, 4, _shot(b), BLUE, t=hours + 20)]
    assert _members(group(occs).groups, occs) == [[1, 2], [3], [4]]
    # The same person coming back hours later in the same costume is still recognised.
    back = [_occ(1, 1, a, RED, t=0), _occ(2, 2, _blend(a, 0.70), RED, t=hours)]
    assert _members(group(back).groups, back) == [[1, 2]]


def test_far_apart_groups_need_a_high_average_face_similarity() -> None:
    a, c = _person(), _person()
    hours = 3 * 3600
    bridge = _unit(a + c)  # one photo of C resembles A strongly (~0.7), the others do not
    occs = [_occ(1, 1, a, RED, t=0), _occ(2, 2, _shot(a, 0.2), RED, t=20), _occ(3, 3, _shot(a, 0.2), RED, t=40),
            _occ(4, 4, bridge, RED, t=hours), _occ(5, 5, c, RED, t=hours + 20), _occ(6, 6, _shot(c, 0.2), RED, t=hours + 40)]
    groups = _members(group(occs).groups, occs)
    assert not any({1, 5} <= set(m) for m in groups)


# ---------------------------------------------------------------- outfit descriptor


def _figure(top: tuple[int, int, int], body: tuple[int, int, int], legs: tuple[int, int, int],
            background: tuple[int, int, int] = (40, 40, 40)) -> np.ndarray:
    """A 400x300 BGR photo with a person-shaped box of three colour bands at x 100-200, y 50-350."""
    img = np.zeros((400, 300, 3), np.uint8)
    img[:] = background
    img[50:125, 100:200] = top
    img[125:230, 100:200] = body
    img[230:350, 100:200] = legs
    return img


BOX = (100 / 300, 50 / 400, 100 / 300, 300 / 400)


def test_outfit_descriptor_separates_same_colours_in_other_places() -> None:
    from app.identity.features import outfit_descriptor, outfit_image

    pink, white, purple = (180, 120, 255), (245, 245, 245), (200, 80, 140)
    pink_hair_white_dress = outfit_descriptor(outfit_image(_figure(pink, white, white)), BOX)
    again_other_background = outfit_descriptor(outfit_image(_figure(pink, white, white, (90, 160, 30))), BOX)
    pink_hair_purple_skirt = outfit_descriptor(outfit_image(_figure(pink, white, purple)), BOX)
    white_hair_pink_dress = outfit_descriptor(outfit_image(_figure(white, pink, pink)), BOX)
    assert float(pink_hair_white_dress @ again_other_background) > 0.99  # background beside the person ignored
    assert float(pink_hair_white_dress @ pink_hair_purple_skirt) < 0.8
    assert float(pink_hair_white_dress @ white_hair_pink_dress) < 0.5  # same colours, other places
    assert outfit_descriptor(outfit_image(_figure(pink, white, white)), (0.5, 0.5, 0.001, 0.001)) is None


def test_old_outfit_vectors_are_recomputed_from_thumbnails(project: Project) -> None:
    import cv2

    from app.identity.features import OUTFIT_VERSION
    from app.workers.analyze_job import refresh_outfits

    occ = _add(project, 1, None, outfit=RED)  # stored by the old descriptor ('t')
    project.conn.execute("UPDATE occurrences SET person_box = ? WHERE id = ?", (json.dumps(BOX), occ))
    thumbs = project.cache_dir / "thumbs"
    thumbs.mkdir()
    cv2.imwrite(str(thumbs / "00000001.jpg"), _figure((180, 120, 255), (245, 245, 245), (245, 245, 245)))
    project.conn.execute("INSERT INTO previews VALUES (1, 'thumb', 'thumbs/00000001.jpg', 300, 400, 'raster', 1)")
    _add(project, 2, None)  # no thumbnail, no box change: left alone
    assert refresh_outfits(project) == 1
    version, blob = project.conn.execute(
        "SELECT model_version, vector FROM occurrence_vectors WHERE occurrence_id = ? AND kind = 'outfit'", (occ,)).fetchone()
    assert version == OUTFIT_VERSION and len(np.frombuffer(blob, "<f4")) == 3 * 16 * 4 * 2
    assert refresh_outfits(project) == 0  # up to date
