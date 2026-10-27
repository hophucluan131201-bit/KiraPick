"""ONNX Runtime setup: offline-only providers, GPU first, CPU fallback.

- Providers are an explicit allow-list: CUDA (NVIDIA, development installs with
  onnxruntime-gpu), DirectML (any DirectX 12 GPU: NVIDIA, AMD, Intel; the Windows
  installer ships onnxruntime-directml) and CPU. ONNX Runtime also ships an Azure
  (cloud) execution provider; it is never requested.
- Telemetry events (Windows ETW) are disabled before any session is created.
- On Windows the CUDA/cuDNN DLLs come from pip packages inside the venv and
  are loaded with ``onnxruntime.preload_dlls()``.
- A provider being *listed* does not prove it works, so the device actually
  used is read back from the created session.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import onnxruntime as ort

log = logging.getLogger(__name__)

ALLOWED_PROVIDERS = ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider")
GPU_PROVIDERS = {"CUDAExecutionProvider": "cuda", "DmlExecutionProvider": "directml"}
# DirectML: ask for the discrete, high-performance GPU (laptops also have an integrated one).
# Older ONNX Runtime builds reject these keys; then the plain provider is tried.
_DML_PREFERRED_OPTIONS = {"device_id": 0, "performance_preference": "high_performance", "device_filter": "gpu"}
DEFAULT_GPU_MEM_LIMIT_MB = 6144  # leave room for Windows/other apps on an 8 GB card

_configured = False
_preload_error: str | None = None


@dataclass(slots=True)
class RuntimeInfo:
    ort_version: str
    available: list[str]
    gpu_listed: bool
    preload_error: str | None
    notes: list[str] = field(default_factory=list)


def configure() -> RuntimeInfo:
    """Idempotent process-wide setup. Call before creating sessions."""
    global _configured, _preload_error
    if not _configured:
        if hasattr(ort, "disable_telemetry_events"):
            ort.disable_telemetry_events()
        ort.set_default_logger_severity(3)  # errors only; some zoo models emit harmless warnings
        if "CUDAExecutionProvider" in ort.get_available_providers() and hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception as exc:  # noqa: BLE001 - reported, CPU still works
                _preload_error = f"{type(exc).__name__}: {exc}"
                log.warning("CUDA DLL preload failed: %s", _preload_error)
        _configured = True
    available = ort.get_available_providers()
    return RuntimeInfo(ort.__version__, available, any(p in available for p in GPU_PROVIDERS), _preload_error)


@dataclass(frozen=True, slots=True)
class Session:
    session: ort.InferenceSession
    device: str  # "cuda" | "directml" | "cpu"
    fallback_reason: str | None


def _gpu_attempts(available: list[str], gpu_mem_limit_mb: int) -> list[tuple[str, list]]:
    """GPU provider configurations to try, best first: (label, providers)."""
    attempts: list[tuple[str, list]] = []
    if "CUDAExecutionProvider" in available:
        attempts.append(("cuda", [("CUDAExecutionProvider", {
            "device_id": 0,
            "gpu_mem_limit": gpu_mem_limit_mb * 1024 * 1024,
            "arena_extend_strategy": "kSameAsRequested",
            "cudnn_conv_algo_search": "HEURISTIC",
        }), "CPUExecutionProvider"]))
    if "DmlExecutionProvider" in available:
        attempts.append(("directml", [("DmlExecutionProvider", dict(_DML_PREFERRED_OPTIONS)), "CPUExecutionProvider"]))
        attempts.append(("directml", [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]))
    return attempts


def create_session(model: Path, *, prefer_gpu: bool = True, gpu_mem_limit_mb: int = DEFAULT_GPU_MEM_LIMIT_MB,
                   cpu_threads: int = 0) -> Session:
    info = configure()

    def options(directml: bool) -> ort.SessionOptions:
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        if cpu_threads:
            opts.intra_op_num_threads = cpu_threads
        if directml:  # required by the DirectML provider
            opts.enable_mem_pattern = False
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return opts

    errors: list[str] = []
    if prefer_gpu:
        for label, providers in _gpu_attempts(info.available, gpu_mem_limit_mb):
            assert all((p if isinstance(p, str) else p[0]) in ALLOWED_PROVIDERS for p in providers)
            try:
                session = ort.InferenceSession(str(model), sess_options=options(label == "directml"),
                                               providers=providers)
            except Exception as exc:  # noqa: BLE001 - a broken GPU setup must not stop the app
                errors.append(f"{label}: {type(exc).__name__}")
                continue
            used = session.get_providers()[0]
            if used in GPU_PROVIDERS:
                return Session(session, GPU_PROVIDERS[used], None)
            errors.append(f"{label}: không dùng được cho mô hình này")
    session = ort.InferenceSession(str(model), sess_options=options(False), providers=["CPUExecutionProvider"])
    reason = None
    if prefer_gpu:
        reason = (f"Không dùng được card đồ hoạ ({'; '.join(errors)}); dùng CPU" if errors
                  else "Bản ONNX Runtime đang cài không hỗ trợ card đồ hoạ; dùng CPU")
    return Session(session, "cpu", reason)
