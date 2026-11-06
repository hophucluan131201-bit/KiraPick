"""Re-create models/converted/*.onnx from Google's MediaPipe Face Landmarker (DEV ONLY, needs Internet).

    python -m venv conv && conv/bin/pip install tensorflow-cpu==2.20.0 onnx onnxruntime
    conv/bin/pip install --no-deps tf2onnx==1.16.1
    conv/bin/python scripts/convert_mediapipe.py

Downloads face_landmarker.task (Apache-2.0), converts the landmark and blendshape
TFLite models to ONNX (opset 17), checks them against the TFLite interpreter and
prints the SHA-256 to put in configs/model-manifest.json. The app never runs this.

    conv/bin/python scripts/convert_mediapipe.py --check

LIC-1 S9: converts into a temporary folder (the repository files are not touched), checks the downloaded .task
against TASK_SHA256, and proves that each file in models/converted/ (the files the allow-list pins) is a conversion
of exactly that .task: the same weights (every initializer, by value), the same operators, and the same outputs on
the same inputs. tf2onnx is not byte-reproducible (node and initializer names, order and folding change from run
to run), so the files themselves are compared by content, not by hash. Exit 2: the .task differs; exit 3: a file differs.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TASK_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
TASK_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"  # read 2026-11-06
OUT = Path(__file__).resolve().parents[1] / "models" / "converted"
MODELS = {"face_landmarks_detector": "mediapipe_face_landmarks_v2.onnx",
          "face_blendshapes": "mediapipe_face_blendshapes_v2.onnx"}
_SHIM = """import sys, numpy as np
class _Cast:  # numpy 2 removed np.cast; tf2onnx 1.16 still uses np.cast[dtype](x)
    def __getitem__(self, dtype):
        return lambda x: np.asarray(x, dtype=dtype)
np.cast = _Cast()
from tf2onnx import convert
sys.exit(convert.main())
"""


def _same_content(fresh: Path, pinned: Path, x) -> tuple[bool, str]:  # noqa: ANN001
    """Same weights (multiset of initializer values) and the same outputs on ``x`` and two more inputs."""
    import numpy as np
    import onnx
    import onnxruntime as ort
    from onnx import numpy_helper

    a, b = onnx.load(str(fresh)), onnx.load(str(pinned))

    def weights(m):  # noqa: ANN001, ANN202
        return sorted(hashlib.sha256(numpy_helper.to_array(t).tobytes() + str(t.data_type).encode()).hexdigest()
                      for t in m.graph.initializer)

    if weights(a) != weights(b):
        return False, "weights differ"
    # (tf2onnx may also fold or order operators differently between runs: the outputs decide)
    sessions = [ort.InferenceSession(str(p), providers=["CPUExecutionProvider"]) for p in (fresh, pinned)]
    diff = 0.0
    for seed in range(3):
        xs = x if seed == 0 else (np.random.default_rng(seed).random(x.shape).astype(np.float32) * float(x.max()))
        outs = [sorted(s.run(None, {s.get_inputs()[0].name: xs}), key=lambda arr: arr.size) for s in sessions]
        diff = max(diff, *(float(np.abs(p.reshape(-1) - q.reshape(-1)).max()) for p, q in zip(*outs, strict=True)))
    return diff <= 1e-5, f"{len(a.graph.initializer)} weights equal, outputs on 3 inputs differ by {diff:.1e}"


def main(argv: list[str] | None = None) -> int:
    import numpy as np
    import onnxruntime as ort
    import tensorflow as tf

    check = "--check" in (sys.argv[1:] if argv is None else argv)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out" if check else OUT
        out.mkdir(parents=True, exist_ok=True)
        task = Path(tmp) / "face_landmarker.task"
        urllib.request.urlretrieve(TASK_URL, task)  # noqa: S310 - fixed https URL
        task_sha = hashlib.sha256(task.read_bytes()).hexdigest()
        print(f"face_landmarker.task sha256 {task_sha}")
        if task_sha != TASK_SHA256:
            print("the downloaded .task is not the one the conversion was made from")
            return 2
        zipfile.ZipFile(task).extractall(tmp)
        shim = Path(tmp) / "tf2onnx_shim.py"
        shim.write_text(_SHIM)
        for name, target in MODELS.items():
            tflite = Path(tmp) / f"{name}.tflite"
            onnx_path = out / target
            subprocess.run([sys.executable, str(shim), "--tflite", str(tflite), "--output", str(onnx_path),
                            "--opset", "17"], check=True)
            it = tf.lite.Interpreter(model_path=str(tflite))
            it.allocate_tensors()
            inp = it.get_input_details()[0]
            x = np.random.default_rng(0).random(inp["shape"]).astype(np.float32)
            x *= 1 if name == "face_landmarks_detector" else 256
            it.set_tensor(inp["index"], x)
            it.invoke()
            ref = max((it.get_tensor(o["index"]) for o in it.get_output_details()), key=lambda a: a.size)
            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            got = max(sess.run(None, {sess.get_inputs()[0].name: x}), key=lambda a: a.size)
            diff = float(np.abs(ref.reshape(-1) - got.reshape(-1)).max())
            digest = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
            print(f"{target}: max diff vs TFLite {diff:.2e}, size {onnx_path.stat().st_size}, sha256 {digest}")
            if diff > 1e-2:
                return 1
            if check:
                same, why = _same_content(onnx_path, OUT / target, x)
                print(f"{target}: {'same content as' if same else 'DIFFERS from'} models/converted ({why})")
                if not same:
                    return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
