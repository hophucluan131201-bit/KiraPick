"""How scores look: the one number, its colour band, the hard-defect mark and the photo's status chip.

Display only: the numbers come unchanged from the rubric (app.quality.score) and the ranking
(app.quality.rank). No Qt widgets here, so every rule is testable on its own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.quality.rank import EYES_CLOSED, FOCUS_DEFECT, Ranked
from app.quality.score import GOOD, POOR, Score

Band = Literal["good", "fair", "poor", "none"]
ChipKind = Literal["keep", "reject", "suggested", "review"]

COLORS: dict[str, str] = {
    "good": "#3FB950", "fair": "#D29922", "poor": "#F85149", "none": "#8B949E",
    "accent": "#2F81F7", "suggestion": "#E3B341",
}
# Rubric warnings that ask for a second look (exact texts from app.quality.score).
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


def display_value(ranked: Ranked | None) -> int | None:
    """The number on the grid badge and in the score ring: the ranking value, rounded half-up."""
    if ranked is None or ranked.value is None:
        return None
    return int(math.floor(ranked.value + 0.5))


def band(value: float | None) -> Band:
    if value is None:
        return "none"
    return "good" if value >= GOOD else "fair" if value >= POOR else "poor"


def hard_defect(score: Score | None, ranked: Ranked | None) -> bool:
    """The ranking's cap thresholds (eyes closed, focus missed), unless the artistic exception lifted it."""
    if score is None or (ranked is not None and ranked.artistic):
        return False
    eyes, focus = score.parts.get("eyes"), score.parts.get("focus")
    return (eyes is not None and eyes <= EYES_CLOSED) or (focus is not None and focus < FOCUS_DEFECT)


def chip_for(flag: str | None, pick_rank: int | None, score: Score | None, ranked: Ranked | None,
             uncertain: bool) -> Chip | None:
    """One chip per photo; the user's decision always wins over AI hints, and the AI never rejects."""
    if flag == "keep":
        return _CHIPS["keep"]
    if flag == "reject":
        return _CHIPS["reject"]
    if pick_rank is not None:
        return _CHIPS["suggested"]
    measured_problem = score is not None and (
        hard_defect(score, ranked) or any(w in REVIEW_WARNINGS for w in score.warnings))
    if measured_problem or uncertain:
        return _CHIPS["review"]
    return None
