"""The shared allow-list (configs/model-policy.json): only verified weights with a pinned SHA-256 are handed out.

U1-a: with every weight file of 3.0.0 present, only the verified ones are READY; U2: a renamed file is refused by its
hash; side files cannot make a file acceptable; U3: KIRAPICK_MODELS_DIR pointing elsewhere goes through the same check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry, ModelState, ModelUnavailableError, default_models_dir, load_manifest
from app.ai.policy import LOAD_LOG, ModelPolicy, Pinned, PolicyEntry, load_model_policy

SHIPPED_IN_300 = {  # model ids of the 15 weight files installed by 3.0.0 / 3.0.0a (inventory run 42199575662)
    "person_detector_s", "person_detector_m", "face_detector", "face_embedder", "face_quality", "face_mesh",
    "face_blendshapes", "face_embedder_arcface", "body_reid", "aesthetic", "tech_iqa", "face_iqa",
    "clip_l14_image", "laion_aesthetic", "clip_prompts"}
VERIFIED = {"person_detector_s", "person_detector_m", "face_detector", "face_quality", "face_mesh", "face_blendshapes"}
PENDING = {"face_embedder", "clip_l14_image", "clip_prompts", "laion_aesthetic", "body_reid"}
NEVER = {"face_embedder_arcface", "aesthetic", "tech_iqa", "face_iqa"}


def _fake_weights(folder: Path) -> tuple[dict, ModelPolicy]:
    """One synthetic file per 3.0.0 weight, and the real policy with the verified hashes replaced by the fakes'."""
    specs = load_manifest()
    real = load_model_policy()
    entries = dict(real.entries)
    for model_id in SHIPPED_IN_300:
        data = f"weights of {model_id}".encode()
        (folder / specs[model_id].file).write_bytes(data)
        e = real.entries[model_id]
        if e.verified:
            entries[model_id] = PolicyEntry(e.id, e.status, e.modes,
                                            (Pinned(hashlib.sha256(data).hexdigest(), len(data)),), e.terms, e.media)
    return specs, ModelPolicy(entries)


def test_policy_covers_the_manifest_and_matches_the_proposed_list() -> None:
    specs, policy = load_manifest(), load_model_policy()
    assert set(policy.entries) == set(specs)
    assert set(policy.ids("verified")) == VERIFIED
    assert set(policy.ids("pending")) == PENDING
    assert set(policy.ids("never")) == NEVER
    for model_id in VERIFIED:
        assert policy.entries[model_id].pinned, model_id


def test_only_verified_weights_are_ready_with_all_300_files_present(tmp_path: Path) -> None:
    """U1-a."""
    specs, policy = _fake_weights(tmp_path)
    reg = ModelRegistry(tmp_path, specs, policy)
    states = {i: reg.status(i).state for i in SHIPPED_IN_300}
    assert {i for i, s in states.items() if s is ModelState.READY} == VERIFIED
    assert all(states[i] is ModelState.BLOCKED for i in PENDING | NEVER)
    for purpose in ("identity_plus", "quality_plus", "aesthetic"):
        assert not reg.ready(purpose), purpose
    for model_id in PENDING | NEVER:
        with pytest.raises(ModelUnavailableError, match="không được phép"):
            reg.require(model_id)


def test_refused_weights_are_logged_with_a_reason(tmp_path: Path) -> None:
    specs, policy = _fake_weights(tmp_path)
    LOAD_LOG.clear()
    reg = ModelRegistry(tmp_path, specs, policy)
    reg.all_status()
    skipped = LOAD_LOG.report()["skipped"]
    assert set(skipped) == PENDING | NEVER
    assert "không bao giờ" in skipped["face_embedder_arcface"]["reason"]
    assert "chờ xác minh" in skipped["clip_l14_image"]["reason"]


def test_renamed_file_is_refused_by_its_hash(tmp_path: Path) -> None:
    """U2: ArcFace weights saved under an allowed file name are not accepted."""
    specs, policy = _fake_weights(tmp_path)
    arc = (tmp_path / specs["face_embedder_arcface"].file).read_bytes()
    (tmp_path / specs["person_detector_s"].file).write_bytes(arc)
    reg = ModelRegistry(tmp_path, specs, policy)
    assert reg.status("person_detector_s").state is ModelState.CORRUPT
    with pytest.raises(ModelUnavailableError):
        reg.require("person_detector_s")


def test_side_files_cannot_make_a_file_acceptable(tmp_path: Path) -> None:
    specs, policy = _fake_weights(tmp_path)
    for model_id in ("person_detector_m", "face_embedder"):
        path = tmp_path / specs[model_id].file
        path.write_bytes(b"something else")
        sha = hashlib.sha256(b"something else").hexdigest()
        path.with_name(path.name + ".sha256").write_text(f"{sha} {len(b'something else')} fp16w-of:{specs[model_id].sha256}")
    reg = ModelRegistry(tmp_path, specs, policy)
    assert reg.status("person_detector_m").state is ModelState.CORRUPT
    assert reg.status("face_embedder").state is ModelState.BLOCKED


def test_models_dir_from_the_environment_goes_through_the_same_check(tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """U3."""
    specs, policy = _fake_weights(tmp_path)
    (tmp_path / "stray.onnx").write_bytes(b"unknown")
    monkeypatch.setenv("KIRAPICK_MODELS_DIR", str(tmp_path))
    assert default_models_dir() == tmp_path
    reg = ModelRegistry(manifest=specs, policy=policy)
    assert reg.models_dir == tmp_path
    assert {i for i in SHIPPED_IN_300 if reg.status(i).state is ModelState.READY} == VERIFIED
    # with the real policy (real pinned hashes) none of the synthetic files is accepted
    real = ModelRegistry(manifest=specs)
    assert not any(real.status(i).state is ModelState.READY for i in SHIPPED_IN_300)


def test_handed_out_weight_is_recorded_with_the_hash_of_the_file(tmp_path: Path) -> None:
    specs, policy = _fake_weights(tmp_path)
    LOAD_LOG.clear()
    reg = ModelRegistry(tmp_path, specs, policy)
    path = reg.require("face_detector")
    opened = LOAD_LOG.report()["opened"]
    assert opened["face_detector"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert opened["face_detector"]["file"] == path.name


NEVER_LOADERS = {"ArcFaceEmbedder", "BodyEmbedder", "AestheticModel", "TechnicalIQA", "FaceIQA", "Embedders"}
OWN_MODULES = {"identity_plus.py", "aesthetic.py", "iqa.py", "embed_job.py"}


def test_no_app_code_builds_the_never_or_reid_loaders() -> None:
    """C4: the ArcFace / YoutuReID / TOPIQ load paths are gone: nothing outside their own modules constructs them,
    and the analysis no longer calls the embed stage."""
    import ast

    root = Path(__file__).resolve().parents[2] / "app"
    for path in sorted(root.rglob("*.py")):
        if path.name in OWN_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                assert name not in NEVER_LOADERS, f"{path.relative_to(root)} builds {name}"
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "embed_job":
                assert node.attr not in ("run", "available"), f"{path.relative_to(root)} calls embed_job.{node.attr}"
