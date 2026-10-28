"""Quality stage v5: CLIP vector, LAION, style tags, technical and face quality per photo."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.ai.clip_version import CLIP_VERSION
from app.storage.project import Project
from app.storage.vectors import load_vectors
from app.workers import quality_job
from app.workers.quality_job import Extras


class FakeClip:
    device = "cpu"
    check: dict = {}

    def embed(self, bgr: np.ndarray) -> np.ndarray:
        v = np.zeros(768, np.float32)
        v[0] = 1.0
        return v

    def laion(self, emb: np.ndarray) -> float:
        return 6.1

    def tags(self, emb: np.ndarray) -> list[tuple[str, float]]:
        return [("low_key", 0.05)]


class FakeTech:
    def score(self, bgr: np.ndarray) -> float:
        return 0.71


class FakeFace:
    def score(self, bgr: np.ndarray, face: tuple) -> float | None:
        return 0.66


class Broken:
    def embed(self, bgr: np.ndarray) -> np.ndarray:
        raise RuntimeError("GPU lost")

    def score(self, *a: object) -> float:
        raise RuntimeError("GPU lost")


def _project(tmp_path: Path, with_person: bool) -> tuple[Project, int]:
    project = Project.create(tmp_path / "s", "t")
    conn = project.conn
    src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
    aid = int(conn.execute(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at) VALUES (?, 'a.jpg', 'jpg', 'raster', 'full', 1, 1, 'h', 'ok', "
        "'t', 't')", (src,)).lastrowid)
    conn.execute("INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at) "
                 "VALUES (?, 'quality', 5, 'pending', 0, 't')", (aid,))
    if with_person:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(occurrences)")}
        values = {"asset_id": aid, "person_box": json.dumps([0.3, 0.1, 0.4, 0.8]), "person_score": 0.9,
                  "face_box": json.dumps([0.45, 0.15, 0.1, 0.1]), "face_score": 0.3, "is_main": 1,
                  "prominence": 1.0, "analysis_version": 1, "created_at": "t"}
        values = {k: v for k, v in values.items() if k in cols}
        conn.execute(f"INSERT INTO occurrences ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
                     list(values.values()))
    return project, aid


def _values(project: Project) -> list[dict]:
    return [json.loads(r[0]) for r in project.conn.execute("SELECT values_json FROM measurements")]


def test_one_photo_gets_every_new_value(tmp_path: Path) -> None:
    project, aid = _project(tmp_path, with_person=True)
    img = np.full((600, 900, 3), 120, np.uint8)
    quality_job._store(project, aid, img, "raster", None, None, None, None, Extras(FakeClip(), FakeTech(), FakeFace()))
    (v,) = _values(project)
    assert v["laion_mos"] == 6.1 and v["tech_iqa"] == 0.71 and v["face_iqa"] == 0.66
    assert v["style_tags"] == [["low_key", 0.05]]
    assert set(load_vectors(project.conn, "clip", CLIP_VERSION)) == {aid}
    project.close()


def test_a_failing_model_leaves_its_value_empty(tmp_path: Path) -> None:
    project, aid = _project(tmp_path, with_person=True)
    img = np.full((600, 900, 3), 120, np.uint8)
    quality_job._store(project, aid, img, "raster", None, None, None, None, Extras(Broken(), Broken(), Broken()))
    (v,) = _values(project)
    assert v["laion_mos"] is None and v["tech_iqa"] is None and v["face_iqa"] is None and v["style_tags"] == []
    state = project.conn.execute("SELECT state FROM stage_status WHERE asset_id = ?", (aid,)).fetchone()[0]
    assert state == "done"
    project.close()


def test_photo_without_people_still_gets_its_clip_vector(tmp_path: Path) -> None:
    project, aid = _project(tmp_path, with_person=False)
    quality_job._store(project, aid, np.full((400, 400, 3), 90, np.uint8), "raster", None, None, None, None,
                       Extras(FakeClip(), FakeTech(), FakeFace()))
    assert set(load_vectors(project.conn, "clip", CLIP_VERSION)) == {aid}
    assert _values(project) == []
    project.close()


def test_missing_models_mean_no_extras(tmp_path: Path) -> None:
    project, aid = _project(tmp_path, with_person=True)
    quality_job._store(project, aid, np.full((400, 600, 3), 90, np.uint8), "raster", None, None, None, None,
                       Extras(None, None, None))
    (v,) = _values(project)
    assert v["laion_mos"] is None and v["tech_iqa"] is None and v["face_iqa"] is None
    assert load_vectors(project.conn, "clip", CLIP_VERSION) == {}
    project.close()


def test_stage_version_is_5() -> None:
    assert quality_job.STAGE_VERSION == 5
