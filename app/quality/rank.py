"""Ranking value: the technical score blended with the personal taste score.

value = (1 - w) * technical + w * taste (w = 0 while taste is not ready). A hard defect (eyes
closed, focus part below 30) caps the value at the technical score, unless the photo carries an
artistic style tag (intentional blur, low-key, silhouette, …) and taste is at least 70: then the
owner's taste may lift it ("ngoại lệ nghệ thuật").
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.clip_aesthetic import ARTISTIC_TAGS
from app.quality.score import Score

DEFAULT_TASTE_WEIGHT = 0.5
ARTISTIC_TASTE = 70.0
EYES_CLOSED = 15.0
FOCUS_DEFECT = 30.0


@dataclass(frozen=True, slots=True)
class Ranked:
    tech: float | None
    taste: float | None
    value: float | None
    capped: bool = False
    artistic: bool = False


def rank(score: Score, taste: float | None, tags: list[str], w: float = DEFAULT_TASTE_WEIGHT) -> Ranked:
    tech = score.total
    if tech is None:
        return Ranked(None, taste, None)
    if taste is None:
        return Ranked(tech, None, tech)
    value = (1 - w) * tech + w * taste
    eyes, focus = score.parts.get("eyes"), score.parts.get("focus")
    defect = (eyes is not None and eyes <= EYES_CLOSED) or (focus is not None and focus < FOCUS_DEFECT)
    if defect:
        if taste >= ARTISTIC_TASTE and any(t in ARTISTIC_TAGS for t in tags):
            return Ranked(tech, taste, round(value, 1), artistic=True)
        return Ranked(tech, taste, round(min(value, tech), 1), capped=True)
    return Ranked(tech, taste, round(value, 1))
