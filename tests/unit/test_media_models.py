"""Media model policy (design §12) on the shared allow-list: only verified weights load, never the non-commercial
ones, CLIP pending with its fallback (MED-CLIP), build gating, report B."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry, load_manifest
from app.ai.policy import policy_for_tests
from app.media.models import MediaModelNotAllowed, MediaRegistry, media_policy as load_policy

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


def test_med_clip_clip_is_pending_with_the_approved_fallback() -> None:
    """MED-CLIP: the owner's risk acceptance (MOD-1) is a record, not a rights basis: CLIP is pending for paid work."""
    policy = load_policy()
    assert policy.models["clip_l14_image"].status == "pending"
    assert policy.models["clip_prompts"].status == "pending"
    assert policy.models["clip_l14_image"].fallback == "manual content, time-gap moments"
    assert policy.models["clip_prompts"].fallback == "manual content"


def test_media_reports_clip_unavailable_and_its_fallback(tmp_path: Path) -> None:
    """U13: even with the CLIP file present, Media does not load it and reports the fallback in use."""
    specs = load_manifest()
    (tmp_path / specs["clip_l14_image"].file).write_bytes(b"clip")
    reg = MediaRegistry(ModelRegistry(tmp_path))
    assert not reg.available("clip_l14_image")
    with pytest.raises(MediaModelNotAllowed, match="pending"):
        reg.require("clip_l14_image")
    assert reg.fallback_for("clip_l14_image") == "manual content, time-gap moments"
    unavailable = reg.report_unavailable()
    assert unavailable["clip_l14_image"] == {"status": "pending", "state": "blocked",
                                             "fallback": "manual content, time-gap moments"}
    assert reg.loaded == {}


@pytest.mark.parametrize("model_id", sorted(NON_COMMERCIAL | {"body_reid", "laion_aesthetic", "not_a_model"}))
def test_registry_refuses_before_opening_anything(model_id: str, tmp_path: Path) -> None:
    reg = MediaRegistry(ModelRegistry(tmp_path))  # an empty folder: a refused id never reaches the file check
    with pytest.raises(MediaModelNotAllowed):
        reg.require(model_id)
    assert reg.loaded == {}


def test_pending_weight_is_refused_until_cleared(tmp_path: Path) -> None:
    reg = MediaRegistry(ModelRegistry(tmp_path))
    assert reg.policy.models["face_embedder"].status == "pending"
    with pytest.raises(MediaModelNotAllowed, match="pending"):
        reg.require("face_embedder")
    assert not reg.available("face_embedder")
    assert reg.fallback_for("face_embedder") == "manual people only"


def test_allowed_weight_is_loaded_and_recorded(tmp_path: Path) -> None:
    import hashlib

    from app.ai.models import ModelSpec

    data = b"weights"
    sha = hashlib.sha256(data).hexdigest()
    (tmp_path / "yunet.onnx").write_bytes(data)
    spec = ModelSpec("face_detector", "YuNet", "yunet.onnx", sha, len(data), "MIT", "", "", "opencv")
    policy = policy_for_tests({"face_detector": (sha, len(data))})
    reg = MediaRegistry(ModelRegistry(tmp_path, {"face_detector": spec}, policy))
    assert reg.available("face_detector")
    assert reg.require("face_detector") == tmp_path / "yunet.onnx"
    assert reg.report_loaded() == {"face_detector": {"sha256": sha, "status": "verified"}}


def test_media_mode_restriction(tmp_path: Path) -> None:
    """A weight verified for the personal mode only is never loaded by Media."""
    import hashlib

    from app.ai.models import ModelSpec

    data = b"q"
    sha = hashlib.sha256(data).hexdigest()
    (tmp_path / "q.onnx").write_bytes(data)
    spec = ModelSpec("face_quality", "eDifFIQA", "q.onnx", sha, len(data), "CC-BY-4.0", "", "", "opencv")
    policy = policy_for_tests({"face_quality": (sha, len(data))}, modes=("personal",))
    reg = MediaRegistry(ModelRegistry(tmp_path, {"face_quality": spec}, policy))
    with pytest.raises(MediaModelNotAllowed, match="never allowed in Media"):
        reg.require("face_quality")


def test_build_gating_by_milestone() -> None:
    policy = load_policy()
    # YOLOX-S and YuNet are verified (LIST-1 proposal); SFace has a fallback (manual people) -> nothing blocks
    assert policy.blocking(0) == []
    assert policy.blocking(1) == []
    assert policy.blocking(2) == []
    assert {"person_detector_s", "face_detector"} <= set(policy.loadable_ids())


def test_policy_rejects_bad_files() -> None:
    from app.ai.policy import parse_policy

    with pytest.raises(ValueError, match="unknown status"):
        parse_policy({"models": [{"id": "x", "status": "maybe"}]})
    with pytest.raises(ValueError, match="without a pinned"):
        parse_policy({"models": [{"id": "x", "status": "verified", "pinned": []}]})
    with pytest.raises(ValueError, match="must not pin"):
        parse_policy({"models": [{"id": "x", "status": "pending", "pinned": [{"sha256": "a", "size": 1}]}]})
    with pytest.raises(ValueError, match="listed twice"):
        parse_policy({"models": [{"id": "x", "status": "never"}, {"id": "x", "status": "never"}]})


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
    assert roles["clip_l14_image"] == "Media: pending"
    assert report["not_in_manifest"] == []
    (tmp_path / "stray.onnx").write_bytes(b"z")
    assert mod.main(["--models-dir", str(tmp_path)]) == 1
    (tmp_path / "stray.onnx").unlink()
    assert mod.main(["--models-dir", str(tmp_path), "--milestone", "1"]) == 0  # nothing blocks any more
    assert mod.main(["--models-dir", str(tmp_path), "--milestone", "0"]) == 0
