"""TasteService: the trained taste model applied to photos of the open session."""

from __future__ import annotations

import numpy as np

from app.learning.taste import TasteExample, TasteStatus, train
from app.learning.taste_service import TasteService
from app.quality.score import score

DIM = 768
GOOD = {"eye_sharp": 0.7, "face_quality": 0.7, "face_clip": 0.0, "face_luma": 50, "area": 0.3, "blink": 0.05}


def _vec(i: int) -> np.ndarray:
    v = np.zeros(DIM, np.float32)
    v[i] = 1.0
    return v


def _ready_status() -> TasteStatus:
    rng = np.random.default_rng(0)
    ex = []
    for i in range(80):
        label = 1 if i % 2 == 0 else -1
        v = _vec(0 if label == 1 else 1) + rng.normal(0, 0.05, DIM)
        ex.append(TasteExample(label, 1.0, f"d{(i // 2) % 4}", v / np.linalg.norm(v), {"focus": 70.0}))
    status = train(ex)
    assert status.ready
    return status


def test_not_ready_means_no_taste_and_technical_ranking() -> None:
    svc = TasteService()
    svc.clips = {1: _vec(0)}
    s = score(GOOD)
    assert svc.taste(1, s) is None
    r = svc.ranked(1, s, 0.5)
    assert r.taste is None and r.value == s.total


def test_ready_model_scores_photos_with_a_clip_vector() -> None:
    svc = TasteService()
    svc.set_status(_ready_status())
    svc.clips = {1: _vec(0), 2: _vec(1)}
    s = score(GOOD)
    liked, disliked = svc.taste(1, s), svc.taste(2, s)
    assert liked is not None and disliked is not None and liked > 70 > disliked
    assert svc.taste(3, s) is None  # no CLIP vector for this photo
    assert svc.ranker(0.5)(1, s).value > svc.ranker(0.5)(2, s).value


def test_explanations_are_vietnamese_phrases() -> None:
    svc = TasteService()
    svc.set_status(_ready_status())
    lines = svc.explain({"backlit_flare": _vec(0), "eyes_closed": _vec(1)})
    text = " ".join(lines)
    assert "ngược sáng" in text and "nhắm mắt" in text
