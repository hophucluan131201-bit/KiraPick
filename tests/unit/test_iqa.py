"""TOPIQ technical quality (KonIQ) and face quality (CGFIQA) wrappers, with stand-in models."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
from onnx import TensorProto, helper  # noqa: E402

from app.ai import iqa  # noqa: E402


def mean_model(path: Path) -> Path:
    """(1,3,h,w) -> its mean as a (1,1) score: brighter = 'better' (enough to check the plumbing)."""
    nodes = [helper.make_node("ReduceMean", ["image"], ["score"], axes=[1, 2, 3], keepdims=1),
             helper.make_node("Reshape", ["score", "shape"], ["out"])]
    shape = helper.make_tensor("shape", TensorProto.INT64, [2], [1, 1])
    g = helper.make_graph(nodes, "m", [helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, "h", "w"])],
                          [helper.make_tensor_value_info("out", TensorProto.FLOAT, [1, 1])], [shape])
    onnx.save(helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)], ir_version=8), path)
    return path


@pytest.fixture
def reg(tmp_path: Path) -> SimpleNamespace:
    p = mean_model(tmp_path / "m.onnx")
    return SimpleNamespace(require=lambda _id: p)


def test_technical_iqa_scores_the_whole_photo(reg: SimpleNamespace) -> None:
    model = iqa.TechnicalIQA(reg, prefer_gpu=False)
    bright = model.score(np.full((400, 600, 3), 200, np.uint8))
    dark = model.score(np.full((400, 600, 3), 50, np.uint8))
    assert bright == pytest.approx(200 / 255, abs=0.01) and dark < bright


def test_face_iqa_reads_only_the_face(reg: SimpleNamespace) -> None:
    model = iqa.FaceIQA(reg, prefer_gpu=False)
    img = np.zeros((1000, 1000, 3), np.uint8)
    img[400:600, 400:600] = 255  # a bright face in a dark photo
    face = (0.45, 0.45, 0.1, 0.1)  # x, y, w, h as fractions; crop = 1.5x box
    got = model.score(img, face)
    assert got is not None and got > 0.4
    assert model.score(img, (0.0, 0.0, 0.01, 0.01)) is None  # 10 px face: too small to judge


def test_aesthetic_still_uses_its_own_model_id(reg: SimpleNamespace) -> None:
    seen = []
    r = SimpleNamespace(require=lambda i: seen.append(i) or reg.require(i))
    from app.ai.aesthetic import AestheticModel

    AestheticModel(r, prefer_gpu=False)
    iqa.TechnicalIQA(r, prefer_gpu=False)
    iqa.FaceIQA(r, prefer_gpu=False)
    assert seen == ["aesthetic", "tech_iqa", "face_iqa"]
