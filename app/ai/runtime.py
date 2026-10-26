"""ONNX Runtime setup: offline-only providers, GPU first, CPU fallback.

- Providers are an explicit allow-list (CUDA, CPU). ONNX Runtime also ships an
  Azure (cloud) execution provider; it is never requested.
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

ALLOWED_PROVIDERS = ("CUDAExecutionProvider", "CPUExecutionProvider")
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
    return RuntimeInfo(ort.__version__, available, "CUDAExecutionProvider" in available, _preload_error)


@dataclass(frozen=True, slots=True)
class Session:
    session: ort.InferenceSession
    device: str  # "cuda" | "cpu"
    fallback_reason: str | None


def create_session(model: Path, *, prefer_gpu: bool = True, gpu_mem_limit_mb: int = DEFAULT_GPU_MEM_LIMIT_MB,
                   cpu_threads: int = 0) -> Session:
    info = configure()
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    if cpu_threads:
        opts.intra_op_num_threads = cpu_threads
    providers: list[str | tuple[str, dict[str, object]]] = []
    if prefer_gpu and info.gpu_listed:
        providers.append(("CUDAExecutionProvider", {
            "device_id": 0,
            "gpu_mem_limit": gpu_mem_limit_mb * 1024 * 1024,
            "arena_extend_strategy": "kSameAsRequested",
            "cudnn_conv_algo_search": "HEURISTIC",
        }))
    providers.append("CPUExecutionProvider")
    assert all((p if isinstance(p, str) else p[0]) in ALLOWED_PROVIDERS for p in providers)
    reason = None
    try:
        session = ort.InferenceSession(str(model), sess_options=opts, providers=providers)
    except Exception as exc:  # noqa: BLE001 - a broken CUDA setup must not stop the app
        if len(providers) == 1:
            raise
        reason = f"CUDA không khởi tạo được ({type(exc).__name__}); dùng CPU"
        session = ort.InferenceSession(str(model), sess_options=opts, providers=["CPUExecutionProvider"])
    used = session.get_providers()[0]
    if prefer_gpu and info.gpu_listed and used != "CUDAExecutionProvider" and reason is None:
        reason = "ONNX Runtime không dùng được CUDA cho mô hình này; dùng CPU"
    elif prefer_gpu and not info.gpu_listed:
        reason = "Bản ONNX Runtime đang cài không có CUDA; dùng CPU"
    return Session(session, "cuda" if used == "CUDAExecutionProvider" else "cpu", reason)
