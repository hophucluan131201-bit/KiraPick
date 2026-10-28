"""'Which do you prefer?': two similar photos of one subject whose ranking is closest."""

from __future__ import annotations

import numpy as np

from app.learning.pairs import next_pair


def _v(*xs: float) -> np.ndarray:
    v = np.zeros(768, np.float32)
    v[: len(xs)] = xs
    return v / np.linalg.norm(v)


def test_closest_ranking_among_similar_photos_of_one_subject() -> None:
    subjects = {1: 7, 2: 7, 3: 7, 4: 8}
    clips = {1: _v(1, 0.1), 2: _v(1, 0.12), 3: _v(1, 0.3), 4: _v(1, 0.11)}
    ranked = {1: 80.0, 2: 70.0, 3: 79.0, 4: 80.5}
    # 1-3 is closest in rank but less similar than the 0.9 cut? cos(1,3) ~ 0.98: allowed; |80-79| = 1 wins
    assert next_pair(subjects, clips, ranked, set()) == (1, 3)
    assert next_pair(subjects, clips, ranked, {frozenset((1, 3))}) == (2, 3)  # not asked twice


def test_different_subjects_or_looks_are_never_compared() -> None:
    subjects = {1: 7, 2: 8}
    clips = {1: _v(1, 0), 2: _v(1, 0)}
    assert next_pair(subjects, clips, {1: 50.0, 2: 50.0}, set()) is None
    subjects = {1: 7, 2: 7}
    clips = {1: _v(1, 0), 2: _v(0, 1)}  # cosine 0: another look
    assert next_pair(subjects, clips, {1: 50.0, 2: 50.0}, set()) is None


def test_photos_without_vector_or_rank_are_skipped() -> None:
    subjects = {1: 7, 2: 7, 3: 7}
    clips = {1: _v(1), 2: _v(1)}
    assert next_pair(subjects, clips, {1: 50.0, 3: 50.0}, set()) is None
