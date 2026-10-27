"""AI runtime/model tests. Inference tests need the weights (scripts/fetch_models.py) and skip otherwise."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.ai import runtime
from app.ai.models import ModelRegistry, ModelState, ModelUnavailableError, load_manifest

REG = ModelRegistry()
HAVE_MODELS = all(s.state is ModelState.READY for s in REG.all_status())
needs_models = pytest.mark.skipif(not HAVE_MODELS, reason="model weights not fetched")
PHOTOS = Path(__file__).resolve().parents[2] / "test_photos"


def test_manifest_pins_every_model_with_license_and_hash() -> None:
    specs = load_manifest()
    assert {"face_detector", "face_embedder", "person_detector_s", "person_detector_m"} <= set(specs)
    for spec in specs.values():
        assert len(spec.sha256) == 64 and spec.size > 0 and spec.license
        assert spec.url.startswith("https://") or (spec.url.startswith("repo:") and
                                                   (Path(__file__).parents[2] / spec.url[5:]).is_file())


def test_registry_reports_missing_and_tampered_files(tmp_path: Path) -> None:
    good = tmp_path / "m.onnx"
    good.write_bytes(b"model-bytes")
    manifest = tmp_path / "manifest.json"
    import hashlib

    manifest.write_text(json.dumps({"models": [
        {"id": "a", "name": "A", "file": "m.onnx", "sha256": hashlib.sha256(b"model-bytes").hexdigest(),
         "size": 11, "license": "MIT", "url": "https://x", "provenance": "test", "runtime": "onnxruntime"},
        {"id": "b", "name": "B", "file": "absent.onnx", "sha256": "0" * 64, "size": 1, "license": "MIT",
         "url": "https://x", "provenance": "test", "runtime": "onnxruntime"},
    ]}))
    reg = ModelRegistry(tmp_path, load_manifest(manifest))
    assert reg.status("a").state is ModelState.READY
    assert reg.status("b").state is ModelState.MISSING
    good.write_bytes(b"model-bytEs")  # same size, different content
    assert reg.status("a").state is ModelState.CORRUPT
    with pytest.raises(ModelUnavailableError):
        reg.require("a")


def test_runtime_is_offline_only() -> None:
    info = runtime.configure()
    assert "CPUExecutionProvider" in info.available
    assert runtime.ALLOWED_PROVIDERS == ("CUDAExecutionProvider", "DmlExecutionProvider",
                                         "CPUExecutionProvider")  # local only: never Azure/cloud


@needs_models
def test_sessions_never_use_cloud_providers() -> None:
    s = runtime.create_session(REG.require("person_detector_s"), prefer_gpu=True)
    assert set(s.session.get_providers()) <= set(runtime.ALLOWED_PROVIDERS)
    assert s.device in ("cuda", "directml", "cpu")


@needs_models
def test_detectors_on_synthetic_image_find_nothing() -> None:
    from app.ai.detect import FaceDetector, PersonDetector

    blank = np.full((900, 1200, 3), 128, np.uint8)
    assert PersonDetector.load(REG, prefer_gpu=False).detect(blank) == []
    assert FaceDetector(REG).detect(blank) == []


def _bgr(rel: str) -> np.ndarray:
    from app.ai.detect import pil_to_bgr
    from app.ingest.preview import load_image

    path = PHOTOS / rel
    if not path.exists():
        pytest.skip(f"sample {rel} absent")
    return pil_to_bgr(load_image(path, max_long_side=1600, min_long_side=1600).image)


@needs_models
def test_portrait_has_main_person_with_face_and_stable_embedding() -> None:
    import cv2

    from app.ai.detect import FaceDetector, FaceEmbedder, PersonDetector, associate

    img = _bgr("user_nikon/DSC_0051.NEF")  # single cosplayer, portrait orientation
    persons = PersonDetector.load(REG, prefer_gpu=False).detect(img)
    faces = FaceDetector(REG).detect(img)
    assert len(persons) == 1 and persons[0][1] > 0.8
    assert len(faces) == 1 and faces[0].score > 0.85
    det = associate(persons, faces)
    assert len(det) == 1 and det[0].face is faces[0]

    emb = FaceEmbedder(REG)
    v1 = emb.embed(img, faces[0])
    assert v1.shape == (128,) and abs(float(np.linalg.norm(v1)) - 1) < 1e-5
    smaller = cv2.resize(img, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)
    [face_small] = FaceDetector(REG).detect(smaller)
    v2 = emb.embed(smaller, face_small)
    assert float(v1 @ v2) > 0.8, "same face at another resolution must stay very similar"


@needs_models
def test_group_photo_has_several_people_and_faces() -> None:
    from app.ai.detect import FaceDetector, PersonDetector

    img = _bgr("user_nikon_crop/DSC_0010.NEF")  # maid-cafe booth, several people
    assert len(PersonDetector.load(REG, prefer_gpu=False).detect(img)) >= 3
    assert len(FaceDetector(REG).detect(img)) >= 2


@needs_models
def test_photo_without_people() -> None:
    from app.ai.detect import FaceDetector, PersonDetector

    img = _bgr("public/iss030e122639.NEF")  # Earth from the ISS
    assert PersonDetector.load(REG, prefer_gpu=False).detect(img) == []
    assert FaceDetector(REG).detect(img) == []


class _FakeSession:
    def __init__(self, model: str, sess_options=None, providers=None) -> None:  # noqa: ANN001
        name = providers[0] if isinstance(providers[0], str) else providers[0][0]
        opts = {} if isinstance(providers[0], str) else providers[0][1]
        if name in _FakeSession.broken or (name == "DmlExecutionProvider" and "device_filter" in opts
                                           and _FakeSession.old_dml):
            raise RuntimeError("cannot create")
        self.providers = [name, "CPUExecutionProvider"] if name != "CPUExecutionProvider" else [name]
        self.sess_options = sess_options

    def get_providers(self) -> list[str]:
        return self.providers

    broken: set[str] = set()
    old_dml = False


@pytest.fixture
def fake_ort(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    monkeypatch.setattr(runtime.ort, "InferenceSession", _FakeSession)
    monkeypatch.setattr(runtime, "configure", lambda: runtime.RuntimeInfo(
        "x", ["DmlExecutionProvider", "CPUExecutionProvider"], True, None))
    _FakeSession.broken, _FakeSession.old_dml = set(), False
    return _FakeSession


def test_directml_is_used_when_available(fake_ort) -> None:  # noqa: ANN001
    s = runtime.create_session(Path("m.onnx"), prefer_gpu=True)
    assert s.device == "directml" and s.fallback_reason is None
    assert s.session.sess_options.enable_mem_pattern is False  # required by DirectML


def test_older_directml_without_device_filter_still_works(fake_ort) -> None:  # noqa: ANN001
    fake_ort.old_dml = True
    assert runtime.create_session(Path("m.onnx"), prefer_gpu=True).device == "directml"


def test_broken_gpu_falls_back_to_cpu_with_a_reason(fake_ort) -> None:  # noqa: ANN001
    fake_ort.broken = {"DmlExecutionProvider"}
    s = runtime.create_session(Path("m.onnx"), prefer_gpu=True)
    assert s.device == "cpu" and "directml" in s.fallback_reason and "CPU" in s.fallback_reason
    assert runtime.create_session(Path("m.onnx"), prefer_gpu=False).fallback_reason is None
