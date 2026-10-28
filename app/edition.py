"""Which ONNX Runtime build this copy of KiraPick ships with (rewritten by scripts/build_windows.ps1).

- directml: the official installer (any DirectX 12 graphics card, CPU fallback);
- cuda: beta for NVIDIA cards (onnxruntime-gpu + CUDA/cuDNN DLLs), version suffix "a";
- openvino: beta for Intel CPUs (onnxruntime-openvino), version suffix "b".
"""

from __future__ import annotations

import re

EDITION = "directml"
SUFFIX = {"directml": "", "cuda": "a", "openvino": "b"}
TITLES = {"cuda": "NVIDIA CUDA", "openvino": "OpenVINO"}


def version_for(base: str, edition: str) -> str:
    return base + SUFFIX[edition]


def release_name(version: str, edition: str) -> str:
    if edition == "directml":
        return f"KiraPick {version}" + (" (beta)" if re.search(r"(a|b|rc)\d+$", version) else "")
    return f"KiraPick {version} – {TITLES[edition]} (beta)"
