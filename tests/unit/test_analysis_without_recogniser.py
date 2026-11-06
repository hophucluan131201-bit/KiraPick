"""U9 / U1 on the real pipeline: with every 3.0.0 weight file present in the dev folder (ArcFace, ReID, TOPIQ, SFace
original, YOLOX-M fp32...), the people and quality analysis open only verified weights, run without a face
recogniser, group nobody automatically, and record their runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.models import ModelRegistry
from app.ai.policy import LOAD_LOG

REG = ModelRegistry()


@pytest.mark.skipif(not REG.can_detect(), reason="verified detection weights not present")
def test_analysis_opens_only_verified_weights_and_groups_by_hand_only(tmp_path: Path) -> None:
    from app.selftest import _synthetic_photo
    from app.storage import provenance
    from app.storage.project import Project
    from app.workers.analyze_job import AnalyzeJob
    from app.workers.import_job import ImportJob

    assert not REG.can_recognise()  # SFace is pending
    shoot = tmp_path / "shoot"
    shoot.mkdir()
    for i in range(2):
        _synthetic_photo(shoot / f"T_{i}.jpg", i)
    LOAD_LOG.clear()
    with Project.create(tmp_path / "session", "t") as project:
        ImportJob(project, shoot).run()
        people = AnalyzeJob(project, REG, prefer_gpu=False).run(mode="people")
        quality = AnalyzeJob(project, REG, prefer_gpu=False).run(mode="quality")
        assert people.failed == 0 and quality.measure_failed == 0
        assert people.grouping is False
        conn = project.conn
        assert conn.execute("SELECT COUNT(*) FROM occurrences WHERE subject_id IS NOT NULL").fetchone()[0] == 0
        runs = {r[0]: r[1] for r in conn.execute("SELECT stage, id FROM analysis_runs WHERE stage != 'test'")}
        assert "detect" in runs and "quality" in runs
        detect_models = {m["model_id"] for m in provenance.run_models(conn, runs["detect"])}
        assert {"person_detector_s", "face_detector"} <= detect_models and "face_embedder" not in detect_models
    opened = set(LOAD_LOG.report()["opened"])
    assert opened and all(REG.policy.verified(i) for i in opened), opened
    assert not opened & {"face_embedder", "face_embedder_arcface", "body_reid", "aesthetic", "tech_iqa", "face_iqa",
                         "clip_l14_image", "laion_aesthetic", "clip_prompts"}
    LOAD_LOG.clear()
