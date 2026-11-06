"""Where each analysis result came from (schema v8).

Every analysis stage that writes results starts an ``analysis_runs`` row, and records in ``analysis_run_models`` the
weights it really opened: model id, SHA-256 of the file itself and the provider ONNX Runtime / OpenCV used (from
app.ai.policy.LOAD_LOG). Occurrences, vectors and measurements written by that stage carry its ``run_id``.

Results from before schema v8 have ``run_id IS NULL``: their source is unknown ("không rõ nguồn"). They are kept,
never deleted, but not used (PROV-1 (b), see app.storage.provenance.unknown_source_summary and the callers).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from app import __version__
from app.ai.policy import LOAD_LOG
from app.storage.project import utc_now

# Tables whose rows are analysis results and carry a run_id (NULL = written before v8, source unknown)
RESULT_TABLES = ("occurrences", "occurrence_vectors", "measurements", "asset_vectors")


def start_run(conn: sqlite3.Connection, stage: str, mode: str = "personal") -> int:
    return int(conn.execute("INSERT INTO analysis_runs (started_at, app_version, mode, stage) VALUES (?, ?, ?, ?)",
                            (utc_now(), __version__, mode, stage)).lastrowid)


def record_models(conn: sqlite3.Connection, run_id: int, model_ids: Iterable[str]) -> list[str]:
    """Record the weights of ``model_ids`` this process really opened (id, SHA-256, provider); returns the ids."""
    opened = LOAD_LOG.report()["opened"]
    recorded = []
    for model_id in model_ids:
        entry = opened.get(model_id)
        if entry is None:
            continue
        for provider in entry["providers"] or ["?"]:
            conn.execute("""INSERT OR IGNORE INTO analysis_run_models (run_id, model_id, sha256, provider)
                            VALUES (?, ?, ?, ?)""", (run_id, model_id, entry["sha256"], provider))
        recorded.append(model_id)
    return recorded


def run_models(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT model_id, sha256, provider FROM analysis_run_models WHERE run_id = ? ORDER BY model_id, provider",
        (run_id,))]


def unknown_source_summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Rows written before v8 (no run_id), per table: the session shows 'không rõ nguồn' while any remain."""
    return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t} WHERE run_id IS NULL").fetchone()[0])  # noqa: S608
            for t in RESULT_TABLES}
