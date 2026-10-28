"""Learning store v6: one taste example per photo, with its CLIP vector, label and weight."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.learning import store as store_module
from app.learning.store import LearningStore
from app.learning.teacher import Teacher, label_for, photo_key
from app.storage.decisions import Decision


@pytest.mark.parametrize(("decision", "expected"), [
    (Decision("keep", 0, False), (1, 1.0)),
    (Decision(None, 3, False), (1, 1.0)),
    (Decision(None, 4, False), (1, 1.5)),
    (Decision("keep", 5, False), (1, 1.5)),
    (Decision(None, 0, True), (1, 1.5)),
    (Decision("reject", 0, False), (-1, 1.0)),
    (Decision(None, 1, False), (-1, 1.0)),
    (Decision(None, 2, False), None),
    (Decision(None, 0, False), None),
    (Decision("reject", 5, False), (1, 1.5)),  # stars/❤ are the stronger, later statement
])
def test_label_for(decision: Decision, expected: tuple[int, float] | None) -> None:
    assert label_for(decision.flag, decision.rating, decision.favorite) == expected


def _clip(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=768)
    return v / np.linalg.norm(v)


def test_one_row_per_photo_holding_the_last_decision(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    teacher = Teacher(store)
    key = photo_key("session-A", 7)
    for d in (Decision("keep"), Decision("reject"), Decision("reject", 5)):
        teacher.decided(key, d, {"focus": 70.0}, _clip(1), "g1")
    rows = store.conn.execute("SELECT label, weight, stars FROM culling_feedback").fetchall()
    assert rows == [(1, 1.5, 5)]
    teacher.decided(key, Decision(), {"focus": 70.0}, _clip(1), "g1")  # cleared: nothing to learn
    assert store.culling_count() == 0
    store.close()


def test_client_picks_are_light(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    Teacher(store).client_picked(photo_key("s", 1), {"focus": 50.0}, _clip(2), "g")
    ex = store.taste_examples("openai-clip-l14-v1")
    assert [(e.label, e.weight) for e in ex] == [(1, 0.3)]
    store.close()


def test_taste_examples_filter_by_clip_version(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    t = Teacher(store)
    t.decided(photo_key("s", 1), Decision("keep"), {"focus": 80.0}, _clip(3), "g")
    store.conn.execute("UPDATE culling_feedback SET clip_version = 'old-clip'")
    t.decided(photo_key("s", 2), Decision("reject"), {"focus": 20.0}, _clip(4), "g")
    ex = sorted(store.taste_examples("openai-clip-l14-v1"), key=lambda e: e.label)
    assert [e.clip is None for e in ex] == [False, True]  # a vector from another CLIP is not used
    assert ex[0].parts["focus"] == 20.0 and ex[0].clip is not None
    assert np.allclose(ex[0].clip, _clip(4), atol=2e-3)
    store.close()


def test_v5_store_upgrades_without_loss(tmp_path: Path) -> None:
    old = sqlite3.connect(tmp_path / "learning.db")
    old.executescript(store_module._SCHEMA)
    old.executescript(store_module._SCHEMA_V2)
    old.executescript(store_module._SCHEMA_V3)
    old.executescript(store_module._SCHEMA_V4)
    old.executescript(store_module._SCHEMA_V5)
    old.execute("""INSERT INTO culling_feedback (created_on, app_version, profile_version, decision, ai_rank, total,
                   focus) VALUES ('2026-10-01', '2.1', 'p', 'keep', 1, 80, 75)""")
    old.execute("PRAGMA user_version = 5")
    old.commit()
    old.close()
    store = LearningStore(tmp_path)
    assert store.culling_count() == 1
    ex = store.taste_examples("openai-clip-l14-v1")
    assert len(ex) == 1 and ex[0].label == 1 and ex[0].weight == 1.0 and ex[0].clip is None
    assert ex[0].parts["focus"] == 75
    store.close()
