"""Which ONNX Runtime build this copy of KiraPick ships with (rewritten by scripts/build_windows.ps1).

- directml: the official installer (any DirectX 12 graphics card, CPU fallback);
- cuda: NVIDIA cards (onnxruntime-gpu + CUDA/cuDNN DLLs), version suffix "a" (official since 3.0.0a);
- openvino: beta for Intel CPUs (onnxruntime-openvino), version suffix "b".
"""

from __future__ import annotations

import re

EDITION = "directml"
SUFFIX = {"directml": "", "cuda": "a", "openvino": "b"}
TITLES = {"cuda": "NVIDIA CUDA", "openvino": "OpenVINO"}


def version_for(base: str, edition: str) -> str:
    return base + SUFFIX[edition]


def is_prerelease(version: str, edition: str) -> bool:
    """A beta / release candidate (2.2.0b1, 3.0.0b1a); OpenVINO is always a beta. CUDA "3.0.0a" is official."""
    return edition == "openvino" or re.search(r"(a|b|rc)\d+[ab]?$", version) is not None


def release_name(version: str, edition: str) -> str:
    name = f"KiraPick {version}" if edition == "directml" else f"KiraPick {version} – {TITLES[edition]}"
    return name + (" (beta)" if is_prerelease(version, edition) else "")
