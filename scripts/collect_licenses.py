"""Collect the licence texts and notices a KiraPick package must carry (LIC-1 S10). Build time only, no network.

    python scripts/collect_licenses.py --dest dist/installer-notes/licenses --edition directml|cuda|openvino

Copies packaging/licenses/* (texts kept in the repository: Apache-2.0, GPL-3.0 + LGPL-3.0 for Qt, LGPL-2.1, CC BY 4.0
for eDifFIQA, MIT and BSD-3 for YuNet, Lucide's ISC + MIT for the icons, the DirectML terms) and, from the packages installed in the build
environment, the texts that must match the shipped version exactly: ONNX Runtime LICENSE + ThirdPartyNotices,
opencv-python LICENSE + LICENSE-3RD-PARTY, rawpy + LibRaw, the Python licence, NVIDIA's licence of every CUDA / cuDNN
wheel (CUDA edition), and a table of every Python package with its declared licence. Exit 1 if a required text is
missing. Names and versions only; never reads photos.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "packaging" / "licenses"
# Every package must carry these (file name in the licences folder -> what it covers)
REQUIRED_STATIC = {
    "Apache-2.0.txt": "YOLOX-S / -M (Megvii), MediaPipe Face Landmarker (Google), OpenCV, ONNX Runtime parts",
    "MIT-YuNet.txt": "YuNet face detector (Shiqi Yu)",
    "BSD-3-Clause-libfacedetection.train.txt": "YuNet training repository (Shiqi Yu)",
    "CC-BY-4.0.txt": "eDifFIQA(T) face quality (Žiga Babnik), used unchanged",
    "LGPL-3.0.txt": "Qt 6 / PySide6 (with GPL-3.0, which it supplements)",
    "GPL-3.0.txt": "referenced by LGPL-3.0",
    "LGPL-2.1.txt": "LibRaw (in rawpy)",
    "Lucide-LICENSE.txt": "Lucide icons 1.72.0 (ISC; the Feather-derived icons MIT, Cole Bemis)",
}
EDITION_STATIC = {"directml": ["DirectML-LICENSE.txt", "DirectML-ThirdPartyNotices.txt"], "cuda": [], "openvino": []}


def _dist_file(dist: str, *names: str) -> Path | None:
    try:
        files = md.distribution(dist).files or []
    except md.PackageNotFoundError:
        return None
    for f in files:
        if Path(str(f)).name in names:
            return Path(f.locate())
    return None


def collect(dest: Path, edition: str) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    for name in list(REQUIRED_STATIC) + EDITION_STATIC.get(edition, []):
        src = STATIC / name
        if src.exists():
            shutil.copyfile(src, dest / name)
        else:
            missing.append(name)
    ort = {"directml": "onnxruntime-directml", "cuda": "onnxruntime-gpu", "openvino": "onnxruntime-openvino"}[edition]
    if _dist_file(ort, "LICENSE") is None and _dist_file("onnxruntime", "LICENSE") is not None:
        ort = "onnxruntime"  # a development machine with the plain CPU build
    wanted = [(ort, ("LICENSE",), "onnxruntime-LICENSE.txt"),
              (ort, ("ThirdPartyNotices.txt",), "onnxruntime-ThirdPartyNotices.txt"),
              ("opencv-python-headless", ("LICENSE.txt",), "opencv-python-LICENSE.txt"),
              ("opencv-python-headless", ("LICENSE-3RD-PARTY.txt",), "opencv-LICENSE-3RD-PARTY.txt"),
              ("rawpy", ("LICENSE",), "rawpy-LICENSE.txt"),
              ("rawpy", ("LICENSE.LibRaw",), "LibRaw-LICENSE.txt")]
    for dist, names, target in wanted:
        src = _dist_file(dist, *names)
        if src is None or not src.exists():
            missing.append(target)
        else:
            shutil.copyfile(src, dest / target)
    import sysconfig

    candidates = [Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"]
    python_licence = next((c for c in candidates if c.exists()), candidates[0])  # Windows: the first one
    if python_licence.exists():
        shutil.copyfile(python_licence, dest / "Python-LICENSE.txt")
    else:
        missing.append("Python-LICENSE.txt")
    if edition == "cuda":
        nvidia = [d for d in md.distributions() if (d.metadata["Name"] or "").lower().startswith("nvidia-")]
        if not nvidia:
            missing.append("NVIDIA licences")
        for d in nvidia:
            src = next((Path(f.locate()) for f in d.files or [] if Path(str(f)).name == "License.txt"), None)
            if src is None:
                missing.append(f"{d.metadata['Name']} License.txt")
            else:
                shutil.copyfile(src, dest / f"NVIDIA-{d.metadata['Name']}-{d.version}-License.txt")
    rows = sorted({(d.metadata["Name"] or "?", d.version, d.metadata.get("License-Expression")
                    or d.metadata.get("License") or "") for d in md.distributions()}, key=lambda r: r[0].lower())
    (dest / "python-packages.txt").write_text(
        "Python packages in this build (name, version, declared licence)\n\n"
        + "\n".join(f"{n} {v}: {(lic or 'see the package').splitlines()[0][:120]}" for n, v, lic in rows) + "\n",
        encoding="utf-8")
    index = ["Licence texts shipped with KiraPick (see THIRD_PARTY_NOTICES.md for what each covers)", ""]
    index += [f"{name}: {what}" for name, what in REQUIRED_STATIC.items()]
    index += sorted(p.name for p in dest.iterdir() if p.name not in REQUIRED_STATIC and p.name != "INDEX.txt")
    (dest / "INDEX.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    return missing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--edition", choices=("directml", "cuda", "openvino"), default="directml")
    args = ap.parse_args(argv)
    missing = collect(args.dest, args.edition)
    for m in missing:
        print(f"MISSING licence text: {m}")
    print(f"{len(list(args.dest.iterdir()))} files in {args.dest}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
