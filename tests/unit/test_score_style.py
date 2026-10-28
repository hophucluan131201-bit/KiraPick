"""Display of scores: one number, colour bands, hard-defect mark and the one status chip per photo."""

from __future__ import annotations

from app.quality.rank import Ranked, rank
from app.quality.score import Score
from app.quality.score import score as rubric
from app.ui.score_style import COLORS, REVIEW_WARNINGS, band, chip_for, display_value, hard_defect


def _score(**parts: float) -> Score:
    warnings = ["lệch nét / rung"] if parts.get("focus", 100) < 30 else []
    full = {"focus": None, "eyes": None, "face": None, "exposure": None, "framing": None, "aesthetic": None, **parts}
    return Score(80.0, full, 1.0, warnings)


def _r(s: Score) -> Ranked:
    return rank(s, None, [])


def test_value_rounds_half_up_and_bands() -> None:
    assert display_value(Ranked(74.5, None, 74.5)) == 75
    assert display_value(Ranked(74.49, None, 74.49)) == 74
    assert band(75) == "good" and band(74.9) == "fair" and band(45) == "fair" and band(44.9) == "poor"
    assert band(None) == "none" and display_value(None) is None
    assert display_value(Ranked(None, None, None)) is None
    assert set(COLORS) == {"good", "fair", "poor", "none", "accent", "suggestion"}


def test_chip_priority_user_first() -> None:
    s = _score(focus=10)  # hard problem
    assert chip_for("keep", 1, s, _r(s), True).kind == "keep"
    assert chip_for("reject", None, s, _r(s), False).kind == "reject"
    assert chip_for(None, 1, s, _r(s), False).kind == "suggested"
    assert chip_for(None, None, s, _r(s), False).kind == "review"
    ok = _score(focus=90)
    assert chip_for(None, None, ok, _r(ok), True).kind == "review"  # uncertain person
    assert chip_for(None, None, ok, _r(ok), False) is None


def test_hard_defect_follows_rank_thresholds_and_artistic_exception() -> None:
    assert hard_defect(_score(eyes=15), None) and not hard_defect(_score(eyes=16), None)
    assert hard_defect(_score(focus=29.9), None) and not hard_defect(_score(focus=30), None)
    assert not hard_defect(_score(focus=10), Ranked(10, 90, 50, artistic=True))


def test_unscored_photo_shows_dash_and_no_ai_chip() -> None:
    assert display_value(None) is None and chip_for(None, None, None, None, False) is None
    assert chip_for("keep", None, None, None, False).kind == "keep"


def test_review_warnings_are_the_rubric_strings() -> None:
    """The chip reads the rubric's own warning texts: they must stay in sync."""
    produced = set()
    produced |= set(rubric({"eye_sharp": 0.05}).warnings)
    produced |= set(rubric({"body_sharp": 0.05}).warnings)
    produced |= set(rubric({"blink": 0.9}).warnings)
    produced |= set(rubric({"face_clip": 0.5, "face_luma": 60}).warnings)
    produced |= set(rubric({"area": 0.3, "cut_head": True}).warnings)
    assert set(REVIEW_WARNINGS) <= produced
    face_only = _score(face=90)
    face_only.warnings.append("mắt nhắm hoặc nhìn xuống (nếu cố ý thì bỏ qua)")
    assert chip_for(None, None, face_only, _r(face_only), False).kind == "review"
