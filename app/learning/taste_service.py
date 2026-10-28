"""The taste model applied to the open session: taste score, ranking and explanations per photo."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

import numpy as np

from app.ai.clip_aesthetic import STYLE_LABELS
from app.ai.clip_version import CLIP_VERSION
from app.learning.taste import MIN_EXAMPLES, TasteStatus
from app.quality.rank import Ranked, rank
from app.quality.score import LABELS, Score
from app.storage.vectors import load_vectors


class TasteService:
    def __init__(self) -> None:
        self.status = TasteStatus(False, f"Chưa đủ dữ liệu: 0/{MIN_EXAMPLES} lựa chọn")
        self.clips: dict[int, np.ndarray] = {}

    def set_status(self, status: TasteStatus) -> None:
        self.status = status

    def load_clips(self, conn: sqlite3.Connection) -> None:
        self.clips = load_vectors(conn, "clip", CLIP_VERSION)

    @property
    def ready(self) -> bool:
        return self.status.ready and self.status.model is not None

    def taste(self, asset_id: int, score: Score) -> float | None:
        clip = self.clips.get(asset_id)
        if not self.ready or clip is None:
            return None
        return self.status.model.predict(clip, score.parts)  # type: ignore[union-attr]

    def ranked(self, asset_id: int, score: Score, w: float) -> Ranked:
        return rank(score, self.taste(asset_id, score), score.tags, w)

    def ranker(self, w: float) -> Callable[[int, Score], Ranked]:
        return lambda asset_id, score: self.ranked(asset_id, score, w)

    def explain(self, prompts: dict[str, np.ndarray]) -> list[str]:
        """What the taste leans to, in words (styles from CLIP prompts, then the technical parts)."""
        model = self.status.model
        if model is None:
            return []
        lines = []
        if prompts:
            concepts = model.concepts(prompts, k=3)
            likes = [STYLE_LABELS.get(n, n) for n, v in concepts if v > 0][:3]
            dislikes = [STYLE_LABELS.get(n, n) for n, v in reversed(concepts) if v < 0][:3]
            if likes:
                lines.append("Bạn hay giữ ảnh: " + ", ".join(likes))
            if dislikes:
                lines.append("Bạn hay loại ảnh: " + ", ".join(dislikes))
        effects = [(LABELS.get(n, n), e) for n, e in model.part_effects() if abs(e) > 1e-3][:3]
        if effects:
            lines.append("Tiêu chí bạn coi trọng: " + ", ".join(f"{n} ({'+' if e > 0 else '−'})" for n, e in effects))
        return lines
