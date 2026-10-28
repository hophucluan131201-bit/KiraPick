"""CLIP ViT-L/14 image embedding + LAION aesthetic head + style prompts (with tiny stand-in models)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
from onnx import TensorProto, helper, numpy_helper  # noqa: E402

from app.ai import clip_aesthetic as ca  # noqa: E402
from app.ai.models import ModelState, ModelUnavailableError  # noqa: E402


def _save(model, path: Path) -> Path:  # noqa: ANN001
    onnx.save(model, path)
    return path


def fake_clip(path: Path) -> Path:
    """(1,3,224,224) -> mean colour per channel -> fixed 3x768 projection."""
    w = np.zeros((3, 768), np.float32)
    w[0, 0], w[1, 1], w[2, 2] = 1.0, 2.0, 3.0
    w[:, 3] = 0.5
    nodes = [helper.make_node("ReduceMean", ["image"], ["m"], axes=[2, 3], keepdims=0),
             helper.make_node("MatMul", ["m", "w"], ["embedding"])]
    g = helper.make_graph(nodes, "clip", [helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, 224, 224])],
                          [helper.make_tensor_value_info("embedding", TensorProto.FLOAT, [1, 768])],
                          [numpy_helper.from_array(w, "w")])
    return _save(helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)], ir_version=8), path)


def fake_head(path: Path) -> Path:
    """(1,768) -> 5 + 2 * x[0]."""
    w = np.zeros((768, 1), np.float32)
    w[0, 0] = 2.0
    g = helper.make_graph([helper.make_node("Gemm", ["emb", "w", "b"], ["score"])], "head",
                          [helper.make_tensor_value_info("emb", TensorProto.FLOAT, [1, 768])],
                          [helper.make_tensor_value_info("score", TensorProto.FLOAT, [1, 1])],
                          [numpy_helper.from_array(w, "w"), numpy_helper.from_array(np.array([5.0], np.float32), "b")])
    return _save(helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)], ir_version=8), path)


def fake_prompts(path: Path) -> Path:
    vecs = np.zeros((2, 768), np.float32)
    vecs[0, 0] = 1.0
    vecs[1, 1] = 1.0
    np.savez(path, ids=np.array(["low_key", "backlit_flare"]), texts=np.array(["a", "b"]), vectors=vecs,
             thresholds=np.array([0.2, 0.99], np.float32))
    return path


def registry(tmp_path: Path, missing: str | None = None) -> SimpleNamespace:
    files = {"clip_l14_image": fake_clip(tmp_path / "clip.onnx"), "laion_aesthetic": fake_head(tmp_path / "head.onnx"),
             "clip_prompts": fake_prompts(tmp_path / "prompts.npz")}

    def require(model_id: str) -> Path:
        if model_id == missing:
            raise ModelUnavailableError(SimpleNamespace(state=ModelState.MISSING, path=Path("x"),
                                                        spec=SimpleNamespace(name=model_id)))
        return files[model_id]
    return SimpleNamespace(require=require)


def test_preprocess_is_a_centre_crop_with_clip_normalisation() -> None:
    img = np.full((200, 300, 3), 255, np.uint8)  # BGR, landscape: the sides are cropped
    img[:, :90] = 0  # left 30 % black
    x = ca.preprocess(img)
    assert x.shape == (1, 3, 224, 224) and x.dtype == np.float32
    white = (1.0 - np.array(ca.MEAN)) / np.array(ca.STD)
    black = (0.0 - np.array(ca.MEAN)) / np.array(ca.STD)
    assert np.allclose(x[0, :, 112, 200], white, atol=0.02)
    assert np.allclose(x[0, :, 112, 10], black, atol=0.02)  # 0.3 * 336 - 56 = 44.8 px of black survive


def test_embed_is_unit_length_and_laion_reads_it(tmp_path: Path) -> None:
    model = ca.ClipAesthetic(registry(tmp_path), prefer_gpu=False)
    emb = model.embed(np.full((300, 400, 3), 128, np.uint8))
    assert emb.shape == (768,) and abs(float(np.linalg.norm(emb)) - 1.0) < 1e-5
    assert model.laion(emb) == pytest.approx(5 + 2 * float(emb[0]), abs=1e-4)
    assert model.device == "cpu"


def test_tags_above_their_threshold_sorted(tmp_path: Path) -> None:
    model = ca.ClipAesthetic(registry(tmp_path), prefer_gpu=False)
    emb = np.zeros(768, np.float32)
    emb[0], emb[1] = 0.6, 0.8
    assert model.tags(emb) == [("low_key", pytest.approx(0.6))]  # backlit 0.8 < its 0.99 threshold


def test_missing_prompts_only_disable_tags(tmp_path: Path) -> None:
    model = ca.ClipAesthetic(registry(tmp_path, missing="clip_prompts"), prefer_gpu=False)
    assert model.tags(np.ones(768, np.float32) / np.sqrt(768)) == []


def test_missing_clip_is_an_unavailable_capability(tmp_path: Path) -> None:
    with pytest.raises(ModelUnavailableError):
        ca.ClipAesthetic(registry(tmp_path, missing="clip_l14_image"), prefer_gpu=False)


def test_artistic_tags_are_known_prompt_ids() -> None:
    assert {"low_key", "silhouette", "motion_blur_intentional", "soft_dreamy", "backlit_flare"} <= ca.ARTISTIC_TAGS


def test_tags_use_the_margin_over_the_neutral_prompt(tmp_path: Path) -> None:
    reg = registry(tmp_path)
    vecs = np.zeros((1, 768), np.float32)
    vecs[0, 0] = 1.0
    neg = np.zeros((1, 768), np.float32)
    neg[0, 1] = 1.0
    np.savez(tmp_path / "prompts.npz", ids=np.array(["low_key"]), texts=np.array(["a"]), vectors=vecs, negatives=neg,
             thresholds=np.array([0.02], np.float32))
    model = ca.ClipAesthetic(reg, prefer_gpu=False)
    emb = np.zeros(768, np.float32)
    emb[0], emb[1] = 0.6, 0.59
    assert model.tags(emb) == []  # 0.01 margin: not enough
    emb[1] = 0.5
    assert model.tags(emb) == [("low_key", pytest.approx(0.1))]


def test_gpu_embedding_must_match_the_cpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A graphics card giving a different embedding would silently skew taste and LAION: use the CPU then."""
    reg = registry(tmp_path)
    real = ca.create_session

    def fake(path, prefer_gpu=True, **k):  # noqa: ANN001, ANN202
        s = real(path, prefer_gpu=False, **k)
        if prefer_gpu and Path(path).name == "clip.onnx":
            s.device = "directml"
            inner = s.session

            class Skewed:  # the "GPU" returns a different vector
                def get_inputs(self):  # noqa: ANN202
                    return inner.get_inputs()

                def run(self, names, feeds):  # noqa: ANN001, ANN202
                    out = inner.run(names, feeds)
                    return [out[0][:, ::-1].copy()]
            s.session = Skewed()
        return s

    monkeypatch.setattr(ca, "create_session", fake)
    model = ca.ClipAesthetic(reg, prefer_gpu=True)
    assert model.device == "cpu" and "khác CPU" in model.check["problem"]
