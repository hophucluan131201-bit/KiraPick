"""The learning store writes like the session databases (Task 14: per-commit disk flushes cost 20+ ms on Windows)."""

from __future__ import annotations

from pathlib import Path

from app.learning.store import LearningStore


def test_learning_store_uses_wal_without_a_flush_per_commit(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning")
    assert store.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert store.conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
    store.conn.close()
    again = LearningStore(tmp_path / "learning")  # an existing store opens the same way, data kept
    assert again.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    again.conn.close()
