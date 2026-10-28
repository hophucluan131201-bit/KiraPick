"""Display of scores: one number, colour bands, hard-defect mark and the one status chip per photo."""

from __future__ import annotations

from app.quality.rank import Ranked, rank
from app.quality.score import Score
from app.quality.score import score as rubric
from app.ui.score_style import COLORS, REVIEW_WARNINGS, band, chip_for, display_band, display_value, hard_defect


def _score(**parts: float) -> Score:
    warnings = ["lệch nét / rung"] if parts.get("focus", 100) < 30 else []
    full = {"focus": None, "eyes": None, "face": None, "exposure": None, "framing": None, "aesthetic": None, **parts}
    return Score(80.0, full, 1.0, warnings)


def _r(s: Score) -> Ranked:
    return rank(s, None, [])


def test_value_rounds_half_up_and_bands() -> None:
    assert display_value(Ranked(74.5, None, 74.5)) == 75
    assert display_value(Ranked(74.49, None, 74.49)) == 74
    assert band(75) == "good" and band(74.4) == "fair" and band(45) == "fair" and band(44.4) == "poor"
    assert band(None) == "none" and display_value(None) is None
    assert display_value(Ranked(None, None, None)) is None
    assert set(COLORS) == {"good", "fair", "poor", "none", "accent", "suggestion"}


def test_chip_priority_user_first() -> None:
    s = _score(focus=10)  # hard problem
    assert chip_for("keep", True, s, _r(s), True).kind == "keep"
    assert chip_for("reject", False, s, _r(s), False).kind == "reject"
    assert chip_for(None, True, s, _r(s), False).kind == "suggested"
    assert chip_for(None, False, s, _r(s), False).kind == "review"
    ok = _score(focus=90)
    assert chip_for(None, False, ok, _r(ok), True).kind == "review"  # uncertain person
    assert chip_for(None, False, ok, _r(ok), False) is None


def test_hard_defect_follows_rank_thresholds_and_artistic_exception() -> None:
    assert hard_defect(_score(eyes=15), None) and not hard_defect(_score(eyes=16), None)
    assert hard_defect(_score(focus=29.9), None) and not hard_defect(_score(focus=30), None)
    assert not hard_defect(_score(focus=10), Ranked(10, 90, 50, artistic=True))


def test_unscored_photo_shows_dash_and_no_ai_chip() -> None:
    assert display_value(None) is None and chip_for(None, False, None, None, False) is None
    assert chip_for("keep", False, None, None, False).kind == "keep"


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
    assert chip_for(None, False, face_only, _r(face_only), False).kind == "review"


def test_displayed_number_and_its_colour_agree() -> None:
    """74.5 is shown as 75, so it must be coloured as 75 (good), on the badge and in the ring alike."""
    r = Ranked(74.5, None, 74.5)
    assert display_value(r) == 75 and display_band(r) == "good"
    assert display_band(Ranked(44.5, None, 44.5)) == "fair"  # shown 45
    assert display_band(Ranked(44.49, None, 44.49)) == "poor"  # shown 44
    assert band(74.5) == "good"  # a criterion bar showing 75 uses the same rounding
    assert display_band(None) == "none"


def test_invalid_numbers_show_as_not_scored_never_zero() -> None:
    for bad in (float("nan"), float("inf"), float("-inf"), -0.6, 100.6, 250.0):
        r = Ranked(bad, None, bad)
        assert display_value(r) is None and display_band(r) == "none" and band(bad) == "none", bad
    assert display_value(Ranked(0.0, None, 0.0)) == 0 and display_value(Ranked(100.0, None, 100.0)) == 100
    assert display_value(Ranked(-0.4, None, -0.4)) == 0  # float noise at the edge rounds into range
    nan_parts = _score(eyes=float("nan"), focus=float("nan"))
    assert not hard_defect(nan_parts, None)  # an unreadable part is not a defect


def test_suggestion_only_from_the_newest_run_and_never_over_a_decision(tmp_path) -> None:  # noqa: ANN001
    """`suggested` comes from the picks table, and saving a run removes every older run (and its picks)."""
    from app.quality.select import Pick, save_run
    from app.storage.project import Project
    with Project.create(tmp_path / "s", "t") as project:
        conn = project.conn
        src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
        old, new = (int(conn.execute(
            "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
            "quick_hash, status, added_at, updated_at) VALUES (?, ?, 'jpg', 'raster', 'full', 1, 1, 'h', 'ok', 't', 't')",
            (src, name)).lastrowid) for name in ("a.jpg", "b.jpg"))
        save_run(conn, [Pick(old, None, 1, 80.0, {})], {"mode": "all"})
        save_run(conn, [Pick(new, None, 1, 70.0, {})], {"mode": "all"})
        suggested = {r[0] for r in conn.execute("SELECT asset_id FROM picks")}
        assert suggested == {new}
        assert conn.execute("SELECT COUNT(*) FROM pick_runs").fetchone()[0] == 1
    ok = _score(focus=90)
    assert chip_for(None, old in suggested, ok, _r(ok), False) is None  # old suggestion: no chip
    assert chip_for(None, new in suggested, ok, _r(ok), False).kind == "suggested"
    assert chip_for("reject", True, ok, _r(ok), False).kind == "reject"  # the user's Loại wins
    assert chip_for("keep", True, ok, _r(ok), False).kind == "keep"


def test_artistic_exception_keeps_the_review_chip_but_drops_the_defect_mark() -> None:
    s = _score(focus=10)  # has the "lệch nét / rung" warning
    artistic = Ranked(60.0, 90.0, 75.0, artistic=True)
    assert not hard_defect(s, artistic)
    assert chip_for(None, False, s, artistic, False).kind == "review"


def test_unscored_but_uncertain_person_asks_for_review() -> None:
    assert chip_for(None, False, None, None, True).kind == "review"


def test_rubric_to_ranking_to_display() -> None:
    """End to end on the real rubric and ranking (no AI formula is touched here)."""
    sharp = rubric({"eye_sharp": 0.75, "blink": 0.05, "face_quality": 0.8, "face_clip": 0.0, "face_luma": 60,
                    "area": 0.3})
    blurred = rubric({"eye_sharp": 0.05, "blink": 0.05, "face_quality": 0.8, "face_clip": 0.0, "face_luma": 60,
                      "area": 0.3})
    rs, rb = rank(sharp, None, []), rank(blurred, None, [])
    assert display_value(rs) == int(sharp.total + 0.5) and display_band(rs) == "good"
    assert hard_defect(blurred, rb) and chip_for(None, False, blurred, rb, False).kind == "review"
    assert chip_for(None, False, sharp, rs, False) is None
    with_taste = rank(blurred, 95.0, [])  # taste cannot lift a hard defect above the technical score
    assert with_taste.capped and display_value(with_taste) == display_value(rb)


def test_invalid_score_is_logged_once_not_on_every_repaint(caplog) -> None:  # noqa: ANN001
    import logging

    from app.ui import score_style

    score_style._warned.clear()
    with caplog.at_level(logging.WARNING, logger="app.ui.score_style"):
        for _ in range(50):  # a grid repaint calls this for every visible card
            display_value(Ranked(float("nan"), None, float("nan")))
    assert len(caplog.records) == 1
