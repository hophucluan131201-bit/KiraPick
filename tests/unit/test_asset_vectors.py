"""Per-photo vectors (CLIP) in the session database."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.storage import db
from app.storage.project import Project
from app.storage.vectors import load_vectors, save_vector


def _asset(project: Project) -> int:
    conn = project.conn
    src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
    return int(conn.execute(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at) VALUES (?, 'a.jpg', 'jpg', 'raster', 'full', 1, 1, 'h', 'ok', 't', 't')", (src,)).lastrowid)


def test_round_trip_in_float16(tmp_path: Path) -> None:
    with Project.create(tmp_path / "s", "t") as project:
        aid = _asset(project)
        v = np.random.default_rng(0).normal(size=768).astype(np.float32)
        v /= np.linalg.norm(v)
        save_vector(project.conn, aid, "clip", "v1", v)
        got = load_vectors(project.conn, "clip", "v1")
        assert set(got) == {aid} and got[aid].dtype == np.float32
        assert float(got[aid] @ v) / float(np.linalg.norm(got[aid])) >= 0.999
        assert load_vectors(project.conn, "clip", "v2") == {}  # another model version is not returned
        save_vector(project.conn, aid, "clip", "v2", v)  # replaced, not duplicated
        assert set(load_vectors(project.conn, "clip", "v2")) == {aid}


def test_schema_has_asset_vectors() -> None:
    assert db.SCHEMA_VERSION >= 5
    assert any("asset_vectors" in sql for _, sql in db.MIGRATIONS)
