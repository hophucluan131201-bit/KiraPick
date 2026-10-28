"""Ranking = technical score blended with the personal taste score; hard defects cap it."""

from __future__ import annotations

import pytest

from app.quality.rank import rank
from app.quality.score import score
from app.quality.select import Candidate, choose

GOOD = {"eye_sharp": 0.7, "face_quality": 0.7, "face_clip": 0.0, "face_luma": 50, "area": 0.3, "blink": 0.05}
CLOSED = GOOD | {"blink": 0.9}


def test_blend_of_technical_and_taste() -> None:
    s = score(GOOD)
    r = rank(s, 80.0, [], 0.5)
    assert r.value == pytest.approx((s.total + 80.0) / 2, abs=0.05) and not r.capped and r.taste == 80.0


def test_without_taste_the_technical_score_decides() -> None:
    s = score(GOOD)
    assert rank(s, None, [], 0.5).value == s.total


def test_closed_eyes_cap_the_blend_at_the_technical_score() -> None:
    s = score(CLOSED)
    r = rank(s, 95.0, [], 0.5)
    assert r.capped and r.value == s.total and not r.artistic


def test_artistic_tag_and_strong_taste_lift_the_cap() -> None:
    s = score(CLOSED)
    lifted = rank(s, 75.0, ["low_key"], 0.5)
    assert lifted.artistic and not lifted.capped and lifted.value == pytest.approx((s.total + 75.0) / 2, abs=0.05)
    weak = rank(s, 60.0, ["low_key"], 0.5)  # taste below 70: the cap stays
    assert weak.capped and not weak.artistic and weak.value == pytest.approx(min(s.total, (s.total + 60.0) / 2), abs=0.05)


def test_unscored_photo_has_no_rank() -> None:
    assert rank(score({}), 90.0, [], 0.5).value is None


def test_selection_follows_the_blended_rank() -> None:
    a, b = score(GOOD), score(GOOD | {"eye_sharp": 0.6})
    ca = Candidate(1, 1, a, None, None, rank(a, 10.0, [], 0.5).value)
    cb = Candidate(2, 2, b, None, None, rank(b, 95.0, [], 0.5).value)
    assert [c.asset_id for c, _ in choose([ca, cb], 1)] == [2]
