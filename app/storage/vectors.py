"""Per-photo vectors (e.g. CLIP) stored in the session as float16."""

from __future__ import annotations

import sqlite3

import numpy as np


def save_vector(conn: sqlite3.Connection, asset_id: int, kind: str, version: str, vec: np.ndarray) -> None:
    conn.execute(
        """INSERT INTO asset_vectors (asset_id, kind, model_version, vector) VALUES (?, ?, ?, ?)
           ON CONFLICT (asset_id, kind) DO UPDATE SET model_version = excluded.model_version,
           vector = excluded.vector""",
        (asset_id, kind, version, np.asarray(vec, "<f2").tobytes()))


def load_vectors(conn: sqlite3.Connection, kind: str, version: str) -> dict[int, np.ndarray]:
    return {int(r[0]): np.frombuffer(r[1], "<f2").astype(np.float32) for r in conn.execute(
        "SELECT asset_id, vector FROM asset_vectors WHERE kind = ? AND model_version = ?", (kind, version))}


def load_vector(conn: sqlite3.Connection, asset_id: int, kind: str, version: str) -> np.ndarray | None:
    row = conn.execute("SELECT vector FROM asset_vectors WHERE asset_id = ? AND kind = ? AND model_version = ?",
                       (asset_id, kind, version)).fetchone()
    return None if row is None else np.frombuffer(row[0], "<f2").astype(np.float32)
