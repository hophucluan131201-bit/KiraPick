"""Check a KiraPick package folder against the allow-list (LIC-1 S8, acceptance P1-P4). No network, no photos.

    python scripts/check_package.py <folder> --edition directml|cuda|openvino [--json report.json]

<folder> is a built dist\\KiraPick folder, an installed folder, or an unzipped portable package. Checks:
  P1  models\\ holds exactly the verified weights of configs/model-policy.json, each with a pinned SHA-256;
  P2  no other weight file (.onnx .pth .pt .npz .task .tflite .safetensors .bin in models\\) anywhere;
  P3  no FFmpeg, no TensorRT provider, no NVIDIA DLL twice, no cuDNN (LIC-7 b: the user installs it);
  P4  docs\\licenses\\ holds every licence text scripts/collect_licenses.py collects for the edition, and the shipped
      notices name no weight that is not in the package.
Exit 0: all pass; 1: a check failed (a cuDNN DLL in the package is a failure: LIC-7 b).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.models import load_manifest  # noqa: E402
from app.ai.policy import load_model_policy  # noqa: E402

WEIGHT_SUFFIXES = {".onnx", ".pth", ".pt", ".npz", ".task", ".tflite", ".safetensors"}
FORBIDDEN_DLLS = {"opencv_videoio_ffmpeg4140_64.dll", "onnxruntime_providers_tensorrt.dll"}
# notices may still name removed weights only in this historical sentence, never as shipped components
REMOVED_NAMES = ("w600k_r50", "ArcFace", "TOPIQ", "topiq_", "YoutuReID", "person_reid_youtu", "clip_l14_image",
                 "laion_aesthetic")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def check(folder: Path, edition: str, policy=None) -> dict:  # noqa: ANN001 - a ModelPolicy (tests pass their own)
    from scripts.collect_licenses import EDITION_STATIC, REQUIRED_STATIC

    policy, specs = policy or load_model_policy(), load_manifest()
    expected = {specs[i].file: i for i in policy.ids("verified")}
    out: dict = {"folder": str(folder), "edition": edition, "failures": [], "notes": []}
    fail = out["failures"].append
    models = folder / "models"
    present = sorted(p.name for p in models.iterdir() if p.is_file()) if models.is_dir() else []
    out["models"] = {}
    for name in present:
        model_id = expected.get(name)
        if model_id is None:
            fail(f"P1 models\\{name}: not a verified weight of the allow-list")
            continue
        sha, size = _sha(models / name), (models / name).stat().st_size
        ok = policy.entry(model_id).accepts(sha, size)
        out["models"][name] = {"id": model_id, "sha256": sha, "bytes": size, "pinned": ok}
        if not ok:
            fail(f"P1 models\\{name}: SHA-256 {sha} not pinned for {model_id}")
    for name in sorted(set(expected) - set(present)):
        fail(f"P1 models\\{name} ({expected[name]}) missing")
    stray = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in WEIGHT_SUFFIXES
             and p.parent != models]
    for p in stray:
        fail(f"P2 weight file outside models\\: {p.relative_to(folder)}")
    dlls = [p for p in folder.rglob("*.dll")]
    for p in dlls:
        if p.name.lower() in FORBIDDEN_DLLS:
            fail(f"P3 {p.relative_to(folder)} must not be shipped")
    by_name: dict[str, list[Path]] = {}
    for p in dlls:
        if any(part.lower() == "nvidia" for part in p.relative_to(folder).parts):
            by_name.setdefault(p.name.lower(), [])
    for p in dlls:
        if p.name.lower() in by_name:
            by_name[p.name.lower()].append(p)
    for name, copies in sorted(by_name.items()):
        if len(copies) > 1:
            fail(f"P3 {name} shipped {len(copies)} times: " + ", ".join(str(c.relative_to(folder)) for c in copies))
    cudnn = sorted({p.name for p in dlls if p.name.lower().startswith("cudnn")})
    for name in cudnn:  # LIC-7 b (owner, 2026-11-07): cuDNN is not distributed, the user installs it
        fail(f"P3 {name}: cuDNN must not be shipped (LIC-7 b)")
    if edition == "cuda" and not (folder / "docs" / "HUONG_DAN_CUDNN.txt").is_file():
        fail("P4 docs\\HUONG_DAN_CUDNN.txt missing (CUDA edition: how to install cuDNN 9)")
    licences = folder / "docs" / "licenses"
    need = list(REQUIRED_STATIC) + EDITION_STATIC.get(edition, []) + [
        "onnxruntime-LICENSE.txt", "onnxruntime-ThirdPartyNotices.txt", "opencv-python-LICENSE.txt",
        "LibRaw-LICENSE.txt", "Python-LICENSE.txt", "python-packages.txt"]
    for name in need:
        if not (licences / name).is_file():
            fail(f"P4 docs\\licenses\\{name} missing")
    if edition == "cuda" and not list(licences.glob("NVIDIA-*-License.txt")):
        fail("P4 docs\\licenses\\NVIDIA-*-License.txt missing (CUDA edition)")
    notices = folder / "docs" / "THIRD_PARTY_NOTICES.md"
    if not notices.is_file():
        fail("P4 docs\\THIRD_PARTY_NOTICES.md missing")
    else:
        shipped = notices.read_text(encoding="utf-8").split("## Not shipped", 1)[0]
        for word in REMOVED_NAMES:
            if word in shipped:
                fail(f"P4 THIRD_PARTY_NOTICES.md names '{word}' as shipped")
    out["ok"] = not out["failures"]
    out["cudnn"] = cudnn
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--edition", choices=("directml", "cuda", "openvino"), default="directml")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    report = check(args.folder, args.edition)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for f in report["failures"]:
        print("FAIL " + f)
    for n in report["notes"]:
        print("NOTE " + n)
    print(f"{'PASS' if report['ok'] else 'FAIL'}: {len(report['models'])} weights, {len(report['failures'])} failures")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
