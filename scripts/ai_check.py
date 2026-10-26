"""Check that the AI models really run on this machine (GPU and CPU) and time them.

    .\\.venv\\Scripts\\python scripts\\ai_check.py "D:\\Photos\\Some shoot" --limit 20

Read-only for photos. Prints: ONNX Runtime providers, whether CUDA actually
executed, per-model timings (median/p95) on CPU and GPU, and GPU memory use
from nvidia-smi. Numbers are measurements on THIS machine only.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import runtime  # noqa: E402
from app.ai.detect import FaceDetector, FaceEmbedder, PersonDetector, pil_to_bgr  # noqa: E402
from app.ai.models import ModelRegistry, ModelState  # noqa: E402
from app.ingest.preview import load_image  # noqa: E402
from app.ingest.scanner import scan_folder  # noqa: E402


def gpu_mem_used_mb() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=False).stdout.strip()
        return int(out.splitlines()[0]) if out else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def stats(ms: list[float]) -> str:
    if not ms:
        return "-"
    ms = sorted(ms)
    return f"median {statistics.median(ms):.0f} ms, p95 {ms[max(0, int(len(ms) * 0.95) - 1)]:.0f} ms (n={len(ms)})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    info = runtime.configure()
    print(f"ONNX Runtime {info.ort_version}; providers: {', '.join(info.available)}")
    if info.preload_error:
        print(f"CUDA DLL preload error: {info.preload_error}")
    registry = ModelRegistry()
    for s in registry.all_status():
        print(f"  model {s.spec.id:18} {s.state.value}")
    if any(s.state is not ModelState.READY for s in registry.all_status()):
        print("Chưa đủ mô hình. Chạy: python scripts/fetch_models.py")
        return 1

    entries = [e for e in scan_folder(args.folder).entries][: args.limit]
    images = [pil_to_bgr(load_image(e.path, max_long_side=1600, min_long_side=1600).image) for e in entries]
    print(f"{len(images)} ảnh từ {args.folder}")

    faces = FaceDetector(registry)
    embedder = FaceEmbedder(registry)
    for label, prefer_gpu in (("GPU", True), ("CPU", False)):
        before = gpu_mem_used_mb()
        detector = PersonDetector.load(registry, prefer_gpu=prefer_gpu)
        print(f"\n[{label}] person detector on: {detector.device.upper()}"
              + (f"  ({detector.session.fallback_reason})" if detector.session.fallback_reason else ""))
        if prefer_gpu and detector.device != "cuda":
            print("  → GPU KHÔNG chạy được; xem lý do ở trên.")
        detector.detect(images[0])  # warm-up (CUDA kernels, cuDNN autotune)
        t_person, t_face, t_emb, n_person, n_face = [], [], [], 0, 0
        for img in images:
            t = time.perf_counter()
            persons = detector.detect(img)
            t_person.append((time.perf_counter() - t) * 1000)
            if label == "GPU":
                t = time.perf_counter()
                found = faces.detect(img)
                t_face.append((time.perf_counter() - t) * 1000)
                t = time.perf_counter()
                for f in found:
                    embedder.embed(img, f)
                t_emb.append((time.perf_counter() - t) * 1000)
                n_face += len(found)
            n_person += len(persons)
        after = gpu_mem_used_mb()
        print(f"  person detection: {stats(t_person)}; {n_person} người")
        if t_face:
            print(f"  face detection (CPU/OpenCV): {stats(t_face)}; {n_face} khuôn mặt")
            print(f"  face embedding (CPU/OpenCV): {stats(t_emb)}")
        if before is not None and after is not None:
            print(f"  GPU memory used: {before} → {after} MiB")
        del detector
    return 0


if __name__ == "__main__":
    sys.exit(main())
