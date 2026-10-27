"""Re-create models/converted/*.onnx from Google's MediaPipe Face Landmarker (DEV ONLY, needs Internet).

    python -m venv conv && conv/bin/pip install tensorflow-cpu==2.20.0 onnx onnxruntime
    conv/bin/pip install --no-deps tf2onnx==1.16.1
    conv/bin/python scripts/convert_mediapipe.py

Downloads face_landmarker.task (Apache-2.0), converts the landmark and blendshape
TFLite models to ONNX (opset 17), checks them against the TFLite interpreter and
prints the SHA-256 to put in configs/model-manifest.json. The app never runs this.
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


def main() -> int:
    import numpy as np
    import onnxruntime as ort
    import tensorflow as tf

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        task = Path(tmp) / "face_landmarker.task"
        urllib.request.urlretrieve(TASK_URL, task)  # noqa: S310 - fixed https URL
        zipfile.ZipFile(task).extractall(tmp)
        shim = Path(tmp) / "tf2onnx_shim.py"
        shim.write_text(_SHIM)
        for name, target in MODELS.items():
            tflite = Path(tmp) / f"{name}.tflite"
            onnx_path = OUT / target
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
