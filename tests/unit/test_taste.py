"""Personal taste model: learns from Keep/Reject/stars, never shows a guess it cannot back up."""

from __future__ import annotations

import numpy as np

from app.learning.taste import TasteExample, train

DIM = 768


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _examples(n: int, rng: np.random.Generator, days: int = 4, random_labels: bool = False) -> list[TasteExample]:
    liked, disliked = np.zeros(DIM), np.zeros(DIM)
    liked[0], disliked[1] = 1.0, 1.0
    out = []
    for i in range(n):
        label = 1 if i % 2 == 0 else -1
        base = liked if label == 1 else disliked
        clip = _unit(base + rng.normal(0, 0.05, DIM))
        parts = {"focus": 80.0 if label == 1 else 60.0, "eyes": None}
        if random_labels:  # nothing in the photo explains the choice
            clip = _unit(rng.normal(0, 1, DIM))
            parts = {"focus": float(rng.uniform(40, 90)), "eyes": None}
        out.append(TasteExample(label, 1.0, f"2026-10-{1 + (i // 2) % days:02d}", clip, parts))
    return out


def test_separable_examples_train_and_pass_the_gate() -> None:
    status = train(_examples(80, np.random.default_rng(0)))
    assert status.ready, status.reason
    assert status.model is not None and status.model.auc >= 0.9
    fresh = np.zeros(DIM)
    fresh[0] = 1.0
    assert status.model.predict(_unit(fresh + 0.01), {"focus": 80.0}) > 70


def test_random_labels_keep_the_gate_closed() -> None:
    status = train(_examples(120, np.random.default_rng(1), random_labels=True))
    assert not status.ready
    assert "độ khớp" in status.reason


def test_too_few_examples() -> None:
    status = train(_examples(30, np.random.default_rng(2)))
    assert not status.ready
    assert status.reason.startswith("Chưa đủ dữ liệu: 30/60")


def test_needs_both_likes_and_dislikes() -> None:
    examples = [e for e in _examples(140, np.random.default_rng(3)) if e.label == 1]
    status = train(examples)
    assert not status.ready and "không thích" in status.reason


def test_folds_are_grouped_by_day() -> None:
    status = train(_examples(80, np.random.default_rng(4), days=3))
    assert status.ready, status.reason


def test_zero_weight_rows_are_ignored() -> None:
    examples = _examples(80, np.random.default_rng(5))
    noise = [TasteExample(-e.label, 0.0, e.day, e.clip, e.parts) for e in examples]
    status = train(examples + noise)
    assert status.ready and status.model is not None and status.model.n == 80


def test_missing_clip_rows_are_skipped() -> None:
    examples = _examples(40, np.random.default_rng(6))
    no_clip = [TasteExample(e.label, 1.0, e.day, None, e.parts) for e in _examples(40, np.random.default_rng(7))]
    status = train(examples + no_clip)
    assert not status.ready and status.reason.startswith("Chưa đủ dữ liệu: 40/60")


def test_concepts_name_what_the_taste_leans_to() -> None:
    status = train(_examples(80, np.random.default_rng(8)))
    assert status.model is not None
    liked, disliked = np.zeros(DIM), np.zeros(DIM)
    liked[0], disliked[1] = 1.0, 1.0
    concepts = status.model.concepts({"ngược sáng": liked, "nhắm mắt": disliked}, k=2)
    assert concepts[0][0] == "ngược sáng" and concepts[0][1] > 0 > concepts[-1][1]
    effects = dict(status.model.part_effects())
    assert effects["focus"] > 0
