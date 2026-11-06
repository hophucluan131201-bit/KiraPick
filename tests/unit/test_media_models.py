"""Media model policy (design §12): only cleared weights load, never the non-commercial ones, build gating, report B."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry, load_manifest
from app.media.models import MediaModelNotAllowed, MediaRegistry, load_policy

ROOT = Path(__file__).resolve().parents[2]
NON_COMMERCIAL = {"face_embedder_arcface", "aesthetic", "tech_iqa", "face_iqa"}


def test_policy_ids_exist_in_the_manifest() -> None:
    specs = load_manifest()
    policy = load_policy()
    assert set(policy.models) <= set(specs)
    assert policy.never <= set(specs)


def test_non_commercial_weights_are_never_loadable() -> None:
    policy = load_policy()
    assert NON_COMMERCIAL <= policy.never
    specs = load_manifest()
    for model in policy.models.values():
        if model.loadable:
            lic = specs[model.id].license.lower()
            assert "noncommercial" not in lic.replace("-", "") and "non-commercial" not in lic, model.id


def test_owner_decision_mod1_clip_is_approved_with_risk() -> None:
    policy = load_policy()
    assert policy.models["clip_l14_image"].status == "approved_with_risk"
    assert policy.models["clip_prompts"].status == "approved_with_risk"


@pytest.mark.parametrize("model_id", sorted(NON_COMMERCIAL | {"body_reid", "laion_aesthetic", "not_a_model"}))
def test_registry_refuses_before_opening_anything(model_id: str, tmp_path: Path) -> None:
    reg = MediaRegistry(ModelRegistry(tmp_path))  # an empty folder: a refused id never reaches the file check
    with pytest.raises(MediaModelNotAllowed):
        reg.require(model_id)
    assert reg.loaded == {}


def test_pending_weight_is_refused_until_cleared(tmp_path: Path) -> None:
    reg = MediaRegistry(ModelRegistry(tmp_path))
    assert reg.policy.models["face_detector"].status == "pending"
    with pytest.raises(MediaModelNotAllowed, match="pending"):
        reg.require("face_detector")
    assert not reg.available("face_detector")


def test_allowed_weight_is_loaded_and_recorded(tmp_path: Path) -> None:
    import hashlib

    from app.ai.models import ModelSpec

    data = b"weights"
    sha = hashlib.sha256(data).hexdigest()
    (tmp_path / "clip.onnx").write_bytes(data)
    spec = ModelSpec("clip_l14_image", "CLIP", "clip.onnx", sha, len(data), "MIT", "", "", "onnxruntime")
    reg = MediaRegistry(ModelRegistry(tmp_path, {"clip_l14_image": spec}))
    assert reg.available("clip_l14_image")
    assert reg.require("clip_l14_image") == tmp_path / "clip.onnx"
    assert reg.report_loaded() == {"clip_l14_image": {"sha256": sha, "status": "approved_with_risk"}}


def test_build_gating_by_milestone() -> None:
    policy = load_policy()
    # today: YOLOX-S and YuNet are pending without fallback -> milestone 1 is blocked; SFace joins at milestone 2
    assert policy.blocking(0) == []
    assert set(policy.blocking(1)) == {"person_detector_s", "face_detector"}
    assert set(policy.blocking(2)) == {"person_detector_s", "face_detector", "face_embedder"}


def test_policy_rejects_bad_files(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"models": [{"id": "x", "status": "maybe", "needed_for": "", "terms": ""}]}))
    with pytest.raises(ValueError, match="unknown status"):
        load_policy(path)
    path.write_text(json.dumps({"models": [{"id": "x", "status": "verified", "needed_for": "", "terms": ""}],
                                "never": ["x"]}))
    with pytest.raises(ValueError, match="never-allowed"):
        load_policy(path)


FORBIDDEN_IMPORTS = {"app.ai.identity_plus", "app.ai.aesthetic", "app.ai.iqa", "app.ai.clip_aesthetic",
                     "app.workers.embed_job", "app.workers.quality_job", "app.workers.analyze_job"}


def test_media_code_never_imports_the_shared_pipelines() -> None:
    """Media must not reach ArcFace / TOPIQ / LAION through the personal-mode pipelines (design §12, item 2)."""
    for path in sorted((ROOT / "app" / "media").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module} | {f"{node.module}.{a.name}" for a in node.names}
            elif isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            else:
                continue
            assert not names & FORBIDDEN_IMPORTS, f"{path.relative_to(ROOT)} imports {names & FORBIDDEN_IMPORTS}"


def test_media_code_loads_models_only_through_the_media_registry() -> None:
    for path in sorted((ROOT / "app" / "media").rglob("*.py")):
        if path.name == "models.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "ModelRegistry(" not in text, f"{path.name} builds a ModelRegistry directly"


def test_report_b_lists_files_and_flags_unknown(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("media_model_report", ROOT / "scripts" / "media_model_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    specs = load_manifest()
    (tmp_path / specs["face_embedder_arcface"].file).write_bytes(b"x")
    (tmp_path / specs["clip_l14_image"].file).write_bytes(b"y")
    report = mod.build_report(tmp_path, 0)
    roles = {r["id"]: r["media"] for r in report["files"]}
    assert roles["face_embedder_arcface"] == "never in Media"
    assert roles["clip_l14_image"] == "Media: approved_with_risk"
    assert report["not_in_manifest"] == []
    (tmp_path / "stray.onnx").write_bytes(b"z")
    assert mod.main(["--models-dir", str(tmp_path)]) == 1
    (tmp_path / "stray.onnx").unlink()
    assert mod.main(["--models-dir", str(tmp_path), "--milestone", "1"]) == 2
    assert mod.main(["--models-dir", str(tmp_path), "--milestone", "0"]) == 0
