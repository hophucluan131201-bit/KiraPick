"""Top-bar workflow steps: ✓ done / ◐ partly done, one test per row of the spec table."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.quality.select import Pick, save_run
from app.storage import decisions, exports
from app.storage.project import Project
from app.storage.workflow import STEPS, StepState, steps
from app.workers import analyze_job, embed_job, quality_job


@pytest.fixture
def conn(tmp_path: Path):  # noqa: ANN201
    with Project.create(tmp_path / "s", "t") as project:
        project.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')")
        yield project.conn


def _photos(conn: sqlite3.Connection, n: int, status: str = "ok") -> list[int]:
    start = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    return [int(conn.execute(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at) VALUES (1, ?, 'jpg', 'raster', 'full', 1, 1, ?, ?, 't', 't')",
        (f"{start + i}.jpg", f"h{start + i}", status)).lastrowid) for i in range(n)]


def _stage(conn: sqlite3.Connection, ids: list[int], stage: str, version: int, state: str = "done") -> None:
    conn.executemany("INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at) "
                     "VALUES (?, ?, ?, ?, 1, 't') ON CONFLICT (asset_id, stage) DO UPDATE SET state = excluded.state,"
                     " stage_version = excluded.stage_version", [(a, stage, version, state) for a in ids])


DETECT, EMBED, QUALITY = ("detect", analyze_job.STAGE_VERSION), ("embed", embed_job.STAGE_VERSION), \
    ("quality", quality_job.STAGE_VERSION)


def test_empty_session(conn: sqlite3.Connection) -> None:
    s = steps(conn, importing=None)
    assert list(s) == list(STEPS) and all(v == StepState(False, None) for v in s.values())


def test_import_running_then_done(conn: sqlite3.Connection) -> None:
    assert steps(conn, importing=(340, 1082))["import"] == StepState(False, "340/1.082")
    _photos(conn, 3)
    assert steps(conn, importing=None)["import"] == StepState(True, None)


def test_import_paused_or_interrupted_is_partial(conn: sqlite3.Connection) -> None:
    _photos(conn, 3)
    conn.execute("INSERT INTO jobs (kind, state, created_at, updated_at) VALUES ('import', 'paused', 't', 't')")
    assert steps(conn, importing=None)["import"] == StepState(False, "tạm dừng")
    conn.execute("INSERT INTO jobs (kind, state, created_at, updated_at) VALUES ('import', 'done', 't2', 't2')")
    assert steps(conn, importing=None)["import"].done  # the newest import job counts


def test_people_partial_then_done(conn: sqlite3.Connection) -> None:
    ids = _photos(conn, 4)
    _stage(conn, ids[:2], *DETECT)
    _stage(conn, ids[:2], *EMBED)
    assert steps(conn, importing=None)["people"] == StepState(False, "2/4")
    _stage(conn, ids[2:], *DETECT)
    assert steps(conn, importing=None)["people"] == StepState(False, "2/4")  # detected but not embedded yet
    _stage(conn, ids[2:], *EMBED)
    assert steps(conn, importing=None)["people"] == StepState(True, None)


def test_failed_photos_count_as_processed(conn: sqlite3.Connection) -> None:
    ids = _photos(conn, 3)
    _stage(conn, ids[:2], *DETECT)
    _stage(conn, ids[:2], *EMBED)
    _stage(conn, ids[2:], *DETECT, state="failed")  # never gets an embed stage
    _photos(conn, 1, status="error")  # unreadable photos are not analysed at all
    assert steps(conn, importing=None)["people"] == StepState(True, None)
    _stage(conn, ids[:1], *QUALITY)
    _stage(conn, ids[1:2], *QUALITY, state="failed")
    assert steps(conn, importing=None)["quality"] == StepState(True, None)


def test_quality_partial_counts_detected_photos(conn: sqlite3.Connection) -> None:
    ids = _photos(conn, 5)
    assert steps(conn, importing=None)["quality"] == StepState(False, None)  # nothing detected yet
    _stage(conn, ids[:4], *DETECT)
    _stage(conn, ids[:1], *QUALITY)
    assert steps(conn, importing=None)["quality"] == StepState(False, "1/4")


def test_outdated_stage_version_is_not_done(conn: sqlite3.Connection) -> None:
    """After an update changes how photos are analysed, old results do not count as done."""
    ids = _photos(conn, 2)
    _stage(conn, ids, "detect", DETECT[1] - 1)
    assert steps(conn, importing=None)["people"] == StepState(False, "0/2")


def test_pick_partial_with_run_only_then_done_with_one_keep(conn: sqlite3.Connection) -> None:
    ids = _photos(conn, 2)
    assert steps(conn, importing=None)["pick"] == StepState(False, None)
    save_run(conn, [Pick(ids[0], None, 1, 80.0, {})], {"mode": "all"})
    assert steps(conn, importing=None)["pick"] == StepState(False, "có đề xuất")
    decisions.set_flag(conn, ids[1], "keep")
    assert steps(conn, importing=None)["pick"] == StepState(True, None)


def test_reject_alone_is_not_a_pick(conn: sqlite3.Connection) -> None:
    ids = _photos(conn, 1)
    decisions.set_flag(conn, ids[0], "reject")
    assert not steps(conn, importing=None)["pick"].done


def test_export_done_after_a_recorded_run(conn: sqlite3.Connection) -> None:
    assert steps(conn, importing=None)["export"] == StepState(False, None)
    exports.record(conn, 1, 2)
    assert steps(conn, importing=None)["export"] == StepState(True, None)


def test_thousands_use_dots() -> None:
    from app.storage.workflow import fraction

    assert fraction(1234, 10500) == "1.234/10.500" and fraction(0, 7) == "0/7"


def test_photo_that_became_unreadable_after_detection_is_not_waited_for(conn: sqlite3.Connection) -> None:
    ids = _photos(conn, 2)
    _stage(conn, ids, *DETECT)
    _stage(conn, ids, *EMBED)
    _stage(conn, ids[:1], *QUALITY)
    conn.execute("UPDATE assets SET status = 'missing' WHERE id = ?", (ids[1],))
    s = steps(conn, importing=None)
    assert s["people"].done and s["quality"].done


def test_steps_are_fast_on_10000_photos(conn: sqlite3.Connection) -> None:
    import time

    ids = _photos(conn, 10_000)
    _stage(conn, ids, *DETECT)
    _stage(conn, ids, *EMBED)
    _stage(conn, ids[:6000], *QUALITY)
    t = time.perf_counter()
    s = steps(conn, importing=None)
    elapsed = time.perf_counter() - t
    assert s["quality"] == StepState(False, "6.000/10.000")
    assert elapsed < 0.25, elapsed
