"""How scores look: the one number, its colour band, the hard-defect mark and the photo's status chip.

Display only: the numbers come unchanged from the rubric (app.quality.score) and the ranking
(app.quality.rank). No Qt widgets here, so every rule is testable on its own.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

from app.quality.rank import EYES_CLOSED, FOCUS_DEFECT, Ranked
from app.quality.score import GOOD, POOR, Score

log = logging.getLogger(__name__)
_warned: set[str] = set()

Band = Literal["good", "fair", "poor", "none"]
ChipKind = Literal["keep", "reject", "suggested", "review"]

COLORS: dict[str, str] = {
    "good": "#3FB950", "fair": "#D29922", "poor": "#F85149", "none": "#8B949E",
    "accent": "#2F81F7", "suggestion": "#E3B341",
}
# Rubric warnings that ask for a second look. The rubric has no warning codes, only these texts, and
# Part 1 must not change it; tests/unit/test_score_style.py fails if a text here stops being produced.
REVIEW_WARNINGS = ("lệch nét / rung", "người không nét", "mắt nhắm hoặc nhìn xuống (nếu cố ý thì bỏ qua)",
                   "mặt bị cháy sáng", "đầu chạm mép ảnh")


@dataclass(frozen=True, slots=True)
class Chip:
    kind: ChipKind
    text: str
    color: str


_CHIPS = {
    "keep": Chip("keep", "✅ Chọn", COLORS["good"]),
    "reject": Chip("reject", "❌ Loại", COLORS["poor"]),
    "suggested": Chip("suggested", "⭐ Đề xuất", COLORS["suggestion"]),
    "review": Chip("review", "⚠ Xem lại", COLORS["fair"]),
}


def shown(value: float | None) -> int | None:
    """A 0..100 number as displayed: rounded half-up; not finite or outside 0..100 -> None ("—").

    Scores are 0..100 by construction; anything else is a data error and is shown as "not scored",
    never silently as 0 or 100 (it is logged, without photo details)."""
    if value is None:
        return None
    if not math.isfinite(value) or not -0.5 < value < 100.5:
        kind = "not finite" if not math.isfinite(value) else "outside 0..100"
        if kind not in _warned:  # once per kind: repaints call this for every visible card
            _warned.add(kind)
            log.warning("score %s not displayed (further ones not logged)", kind)
        return None
    return min(100, max(0, int(math.floor(value + 0.5))))


def display_value(ranked: Ranked | None) -> int | None:
    """The number on the grid badge and in the score ring: the ranking value, rounded half-up."""
    return shown(ranked.value) if ranked is not None else None


def band(value: float | None) -> Band:
    """Colour band of a number, judged on the number as shown (74.5 is shown 75: good)."""
    v = shown(value)
    if v is None:
        return "none"
    return "good" if v >= GOOD else "fair" if v >= POOR else "poor"


def display_band(ranked: Ranked | None) -> Band:
    """Band of the badge / ring number; the same function serves both, so they always agree."""
    return band(display_value(ranked))


def hard_defect(score: Score | None, ranked: Ranked | None) -> bool:
    """The ranking's cap thresholds (eyes closed, focus missed), unless the artistic exception lifted it."""
    if score is None or (ranked is not None and ranked.artistic):
        return False
    eyes, focus = score.parts.get("eyes"), score.parts.get("focus")
    return (eyes is not None and eyes <= EYES_CLOSED) or (focus is not None and focus < FOCUS_DEFECT)


def chip_for(flag: str | None, suggested: bool, score: Score | None, ranked: Ranked | None,
             uncertain: bool) -> Chip | None:
    """One chip per photo; the user's decision always wins over AI hints, and the AI never rejects.

    ``suggested``: the photo is in the picks table. That table only ever holds the newest
    "⭐ Chọn ảnh" run (app.quality.select.save_run deletes older runs), so callers pass
    ``asset_id in picks`` and never an older suggestion."""
    if flag == "keep":
        return _CHIPS["keep"]
    if flag == "reject":
        return _CHIPS["reject"]
    if suggested:
        return _CHIPS["suggested"]
    measured_problem = score is not None and (
        hard_defect(score, ranked) or any(w in REVIEW_WARNINGS for w in score.warnings))
    if measured_problem or uncertain:
        return _CHIPS["review"]
    return None
