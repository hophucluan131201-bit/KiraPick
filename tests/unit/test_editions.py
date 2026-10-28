"""Editions: DirectML (official), CUDA and OpenVINO (betas) share one code base."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai import runtime

ROOT = Path(__file__).resolve().parents[2]


def test_openvino_is_an_allowed_offline_accelerator() -> None:
    assert "OpenVINOExecutionProvider" in runtime.ALLOWED_PROVIDERS
    assert runtime.GPU_PROVIDERS["OpenVINOExecutionProvider"] == "openvino"
    attempts = runtime._gpu_attempts(["OpenVINOExecutionProvider", "CPUExecutionProvider"], 1024)
    assert attempts == [("openvino", [("OpenVINOExecutionProvider", {"device_type": "CPU"}), "CPUExecutionProvider"])]


def test_openvino_used_only_when_faster_than_plain_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    timings = {"cpu": 100.0, "openvino": 60.0}

    def fake_create(model, prefer_gpu=True, **_k):  # noqa: ANN001, ANN202
        device = "openvino" if prefer_gpu else "cpu"
        return SimpleNamespace(device=device, ms=timings[device])

    monkeypatch.setattr(runtime, "configure", lambda: SimpleNamespace(available=["OpenVINOExecutionProvider",
                                                                                 "CPUExecutionProvider"]))
    monkeypatch.setattr(runtime, "create_session", fake_create)
    monkeypatch.setattr(runtime, "_time_session", lambda s, runs: s.ms)
    runtime._speed_cache.clear()
    use, note = runtime.gpu_speed_check(Path("m.onnx"))
    assert use and "OpenVINO" in note
    timings["openvino"] = 95.0  # not clearly faster: plain CPU
    runtime._speed_cache.clear()
    use, note = runtime.gpu_speed_check(Path("m.onnx"))
    assert not use and "không nhanh hơn" in note
    runtime._speed_cache.clear()


def test_edition_requirements_pin_one_onnxruntime_build() -> None:
    builds = {"directml": "onnxruntime-directml", "cuda": "onnxruntime-gpu", "openvino": "onnxruntime-openvino"}
    for edition, package in builds.items():
        text = (ROOT / "packaging" / f"requirements-{edition}.txt").read_text(encoding="utf-8")
        found = re.findall(r"^(onnxruntime[\w-]*)(?:\[[^\]]*\])?==", text, re.M)
        assert found == [package], (edition, found)


def test_edition_versions_and_names() -> None:
    from app.edition import EDITION, release_name, version_for

    assert EDITION in ("directml", "cuda", "openvino")
    assert version_for("2.2.0", "directml") == "2.2.0"
    assert version_for("2.2.0", "cuda") == "2.2.0a"
    assert version_for("2.2.0", "openvino") == "2.2.0b"
    assert release_name("2.2.0a", "cuda") == "KiraPick 2.2.0a – NVIDIA CUDA (beta)"
    assert release_name("2.2.0b", "openvino") == "KiraPick 2.2.0b – OpenVINO (beta)"
    assert release_name("2.2.0", "directml") == "KiraPick 2.2.0"
    assert release_name("2.2.0b1", "directml") == "KiraPick 2.2.0b1 (beta)"
