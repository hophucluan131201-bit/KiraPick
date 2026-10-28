"""Store the large ONNX models' weights as float16 (BUILD TIME; needs the ``onnx`` package).

    python scripts/shrink_models.py --dest build/models      # run after fetch_models / convert_topiq

Each large float32 weight becomes float16 on disk plus a Cast back to float32, so the model
still computes in float32 (same operators, same providers, CPU / DirectML / CUDA) and only
the weight values are rounded (relative error <= 2^-11). The file is about half as big.
Every model is checked against the original on fixed test inputs before it replaces it
(embeddings: cosine >= 0.9999; other outputs: max error <= 1% of the output's range or size),
and a ``<file>.sha256`` sidecar ("<sha256> <size> fp16w-of:<original sha256>") is written
so the app's registry verifies the shrunk file. Models whose check fails stay untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import helper, numpy_helper

ROOT = Path(__file__).resolve().parents[1]
MIN_ELEMENTS = 1024  # small tensors (biases, norms) stay float32
# model id -> kind of output check
TARGETS = {
    "face_embedder_arcface": "embedding",
    "body_reid": "embedding",
    "face_embedder": "embedding",
    "aesthetic": "values",
    "person_detector_m": "values",
    "clip_l14_image": "embedding",
    "tech_iqa": "values",
    "face_iqa": "values",
}
SIZE_FREE = ("aesthetic", "tech_iqa")  # inputs of any size: checked on two photo shapes
SUFFIX = "fp16w"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def shrink(model: onnx.ModelProto) -> onnx.ModelProto:
    graph = model.graph
    casts, kept = [], []
    for init in graph.initializer:
        if init.data_type == onnx.TensorProto.FLOAT and np.prod(init.dims, dtype=np.int64) >= MIN_ELEMENTS:
            arr = numpy_helper.to_array(init)
            half = numpy_helper.from_array(arr.astype(np.float16), init.name + "__fp16")
            kept.append(half)
            casts.append(helper.make_node("Cast", [half.name], [init.name], to=onnx.TensorProto.FLOAT,
                                          name=init.name + "__to_fp32"))
        else:
            kept.append(init)
    del graph.initializer[:]
    graph.initializer.extend(kept)
    nodes = list(graph.node)
    del graph.node[:]
    graph.node.extend(casts + nodes)
    graph_inputs = {i.name for i in graph.input}
    if any(c.output[0] in graph_inputs for c in casts):  # old exporters list weights as inputs too
        keep_inputs = [i for i in graph.input if i.name not in {c.output[0] for c in casts}]
        del graph.input[:]
        graph.input.extend(keep_inputs)
    return model


def _inputs(session: ort.InferenceSession, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    feeds = {}
    for i in session.get_inputs():
        shape = [d if isinstance(d, int) else {0: 1}.get(n, 224 if len(i.shape) == 4 else 1)
                 for n, d in enumerate(i.shape)]
        feeds[i.name] = rng.uniform(-1, 1, shape).astype(np.float32)
    return feeds


def check(original: Path, shrunk: Path, kind: str, shapes: list[dict] | None = None) -> tuple[bool, str]:
    a = ort.InferenceSession(str(original), providers=["CPUExecutionProvider"])
    b = ort.InferenceSession(str(shrunk), providers=["CPUExecutionProvider"])
    worst = 1.0 if kind == "embedding" else 0.0
    for seed in range(4):
        feeds = _inputs(a, seed) if not shapes else {k: np.random.default_rng(seed).uniform(-1, 1, v).astype(np.float32)
                                                     for k, v in shapes[seed % len(shapes)].items()}
        for x, y in zip(a.run(None, feeds), b.run(None, feeds)):
            x, y = np.asarray(x, np.float64).reshape(-1), np.asarray(y, np.float64).reshape(-1)
            if kind == "embedding":
                worst = min(worst, float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-12)))
            else:
                worst = max(worst, float(np.abs(x - y).max() / max(float(np.ptp(x)), float(np.abs(x).max()), 1e-6)))
    ok = worst >= 0.9999 if kind == "embedding" else worst <= 0.01
    return ok, (f"cosine {worst:.6f}" if kind == "embedding" else f"max error {worst:.4%} of range")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=Path, required=True, help="folder with the fetched model files")
    args = parser.parse_args()
    manifest = {m["id"]: m for m in json.loads((ROOT / "configs" / "model-manifest.json").read_text("utf-8"))["models"]}
    failures = 0
    for model_id, kind in TARGETS.items():
        spec = manifest.get(model_id)
        path = args.dest / spec["file"] if spec else None
        if path is None or not path.is_file():
            print(f"BỎ QUA {model_id}: không có file")
            continue
        sidecar = path.with_name(path.name + ".sha256")
        if sidecar.is_file() and SUFFIX in sidecar.read_text():
            print(f"OK     {path.name}: đã thu gọn")
            continue
        source_sha = _sha256(path)
        shrunk = path.with_name(path.stem + ".fp16w.tmp.onnx")
        onnx.save(shrink(onnx.load(str(path))), str(shrunk))
        shapes = [{"input": (1, 3, 384, 384)}, {"input": (1, 3, 384, 576)}] if model_id in SIZE_FREE else None
        if shapes:
            name = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]).get_inputs()[0].name
            shapes = [{name: s["input"]} for s in shapes]
        ok, detail = check(path, shrunk, kind, shapes)
        before, after = path.stat().st_size, shrunk.stat().st_size
        if not ok:
            shrunk.unlink()
            print(f"GIỮ    {path.name}: kiểm tra không đạt ({detail}) — giữ bản gốc")
            failures += 1
            continue
        shrunk.replace(path)
        sidecar.write_text(f"{_sha256(path)} {path.stat().st_size} {SUFFIX}-of:{source_sha}\n")
        print(f"THU GỌN {path.name}: {before / 1e6:.0f} -> {after / 1e6:.0f} MB ({detail})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
