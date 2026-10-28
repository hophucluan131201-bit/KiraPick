"""State of the five workflow steps shown in the top bar: ✓ done, ◐ partly done (with a short text), or plain.

Read-only and cheap (a few COUNT queries); the window calls it after imports, analyses, decisions and exports.
Steps never lock anything: they only say how far the session got and which step is next.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.storage import exports

STEPS = ("import", "people", "quality", "pick", "export")


@dataclass(frozen=True, slots=True)
class StepState:
    done: bool
    partial: str | None  # e.g. "340/1.082", "tạm dừng", "có đề xuất"; None when done or not started


_NOT_STARTED = StepState(False, None)
_DONE = StepState(True, None)


def fraction(done: int, total: int) -> str:
    """"1.234/10.500": Vietnamese thousands separator."""
    return f"{done:,}/{total:,}".replace(",", ".")


def _stage_versions() -> dict[str, int]:
    # The analysis modules own their versions; imported here (not at module load) to keep storage light.
    from app.workers import analyze_job, embed_job, quality_job

    return {analyze_job.STAGE: analyze_job.STAGE_VERSION, embed_job.STAGE: embed_job.STAGE_VERSION,
            quality_job.STAGE: quality_job.STAGE_VERSION}


def _processed(conn: sqlite3.Connection, stage: str, version: int, of: str) -> tuple[int, int]:
    """(photos of the set ``of`` with ``stage`` done or failed at the current version, photos in the set)."""
    total = conn.execute(f"SELECT COUNT(*) FROM ({of})").fetchone()[0]
    done = conn.execute(
        f"""SELECT COUNT(*) FROM stage_status st WHERE st.stage = ? AND st.stage_version >= ?
              AND st.state IN ('done', 'failed') AND st.asset_id IN ({of})""", (stage, version)).fetchone()[0]
    return int(done), int(total)


def _progress(done: int, total: int) -> StepState:
    if total and done >= total:
        return _DONE
    return StepState(False, fraction(done, total)) if total else _NOT_STARTED


def steps(conn: sqlite3.Connection, *, importing: tuple[int, int] | None) -> dict[str, StepState]:
    """``importing``: (done, total) while an import runs in this window, else None."""
    v = _stage_versions()
    readable = "SELECT id FROM assets WHERE status = 'ok'"
    out: dict[str, StepState] = {}

    photos = conn.execute("SELECT COUNT(*) FROM assets WHERE status NOT IN ('missing', 'duplicate')").fetchone()[0]
    last_job = conn.execute("SELECT state FROM jobs WHERE kind = 'import' ORDER BY id DESC LIMIT 1").fetchone()
    if importing is not None:
        out["import"] = StepState(False, fraction(*importing))
    elif last_job is not None and last_job[0] in ("running", "paused"):  # paused, or stopped by a crash
        out["import"] = StepState(False, "tạm dừng")
    elif last_job is not None and last_job[0] == "failed":  # the import stopped on an error: not finished
        out["import"] = StepState(False, "có lỗi khi nhập")
    else:
        out["import"] = _DONE if photos else _NOT_STARTED

    det_done, ok = _processed(conn, "detect", v["detect"], readable)
    detected = f"""SELECT asset_id FROM stage_status WHERE stage = 'detect' AND state = 'done'
                   AND stage_version >= {int(v['detect'])} AND asset_id IN ({readable})"""
    emb_done, emb_total = _processed(conn, "embed", v["embed"], detected)
    # A photo counts for "people" once detection ended for it and, if detected, its vectors exist.
    people_done = det_done - (emb_total - emb_done)
    out["people"] = _progress(people_done, ok)

    # Over every readable photo, so the step cannot finish while detection is still running: a photo is
    # processed once measured (done or failed), or when detection failed on it (nothing to measure).
    q_done, _ = _processed(conn, "quality", v["quality"], detected)
    det_failed, _ = _processed(conn, "detect", v["detect"], f"""SELECT asset_id FROM stage_status
        WHERE stage = 'detect' AND state = 'failed' AND asset_id IN ({readable})""")
    out["quality"] = _progress(q_done + det_failed, ok) if det_done or q_done else _NOT_STARTED

    kept = conn.execute("SELECT 1 FROM decisions WHERE flag = 'keep' AND subject_id IS NULL LIMIT 1").fetchone()
    has_run = conn.execute("SELECT 1 FROM pick_runs LIMIT 1").fetchone()
    out["pick"] = _DONE if kept else StepState(False, "có đề xuất") if has_run else _NOT_STARTED

    out["export"] = _DONE if exports.count(conn) else _NOT_STARTED
    return out
