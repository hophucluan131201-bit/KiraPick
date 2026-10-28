"""Timing of the workflow step query on a big session (marker `perf`: not part of the default run)."""

from __future__ import annotations

import sqlite3
import time

import pytest

from app.storage.workflow import StepState, steps
from tests.unit.test_workflow_steps import DETECT, EMBED, QUALITY, _photos, _stage, conn  # noqa: F401 - fixture

pytestmark = pytest.mark.perf


def test_steps_are_fast_on_10000_photos(conn: sqlite3.Connection) -> None:  # noqa: F811
    ids = _photos(conn, 10_000)
    _stage(conn, ids, *DETECT)
    _stage(conn, ids, *EMBED)
    _stage(conn, ids[:6000], *QUALITY)
    t = time.perf_counter()
    s = steps(conn, importing=None)
    elapsed = time.perf_counter() - t
    assert s["quality"] == StepState(False, "6.000/10.000")
    assert elapsed < 0.25, elapsed
