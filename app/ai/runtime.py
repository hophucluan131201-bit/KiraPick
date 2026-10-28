"""ONNX Runtime setup: offline-only providers, GPU first, CPU fallback.

- Providers are an explicit allow-list: CUDA (NVIDIA; the CUDA edition ships onnxruntime-gpu),
  DirectML (any DirectX 12 GPU; the main installer ships onnxruntime-directml), OpenVINO
  (Intel CPU; the OpenVINO edition) and CPU. ONNX Runtime also ships an Azure
  (cloud) execution provider; it is never requested.
- Telemetry events (Windows ETW) are disabled before any session is created.
- On Windows the CUDA/cuDNN DLLs come from pip packages inside the venv and
  are loaded with ``onnxruntime.preload_dlls()``.
- A provider being *listed* does not prove it works, so the device actually
  used is read back from the created session.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _openvino_dll_dir() -> None:
    """OpenVINO edition on Windows: its DLLs (openvino/libs) must be findable BEFORE ONNX Runtime loads."""
    if sys.platform != "win32":
        return
    try:
        spec = importlib.util.find_spec("openvino")
        roots = list(spec.submodule_search_locations or []) if spec else []
    except (ImportError, ValueError):
        roots = []
    if getattr(sys, "frozen", False):
        roots.append(str(Path(getattr(sys, "_MEIPASS", "")) / "openvino"))
    for root in roots:
        libs = Path(root) / "libs"
        if libs.is_dir():
            os.add_dll_directory(str(libs))
            os.environ["PATH"] = str(libs) + os.pathsep + os.environ.get("PATH", "")
            return


_openvino_dll_dir()

import onnxruntime as ort  # noqa: E402 - after the DLL directory is set up

log = logging.getLogger(__name__)

ALLOWED_PROVIDERS = ("CUDAExecutionProvider", "DmlExecutionProvider", "OpenVINOExecutionProvider",
                     "CPUExecutionProvider")
# Accelerated providers ("GPU" in the code's naming; OpenVINO runs on the Intel CPU, faster than plain ORT CPU).
GPU_PROVIDERS = {"CUDAExecutionProvider": "cuda", "DmlExecutionProvider": "directml",
                 "OpenVINOExecutionProvider": "openvino"}
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
        if "OpenVINOExecutionProvider" in ort.get_available_providers():
            try:  # Windows: the OpenVINO DLLs come from the openvino pip package
                from onnxruntime.tools import add_openvino_win_libs

                add_openvino_win_libs.add_openvino_libs_to_path()
            except Exception as exc:  # noqa: BLE001 - reported; plain CPU still works
                _preload_error = f"OpenVINO: {type(exc).__name__}: {exc}"
                log.warning("OpenVINO DLL setup failed: %s", _preload_error)
        _configured = True
    available = ort.get_available_providers()
    return RuntimeInfo(ort.__version__, available, any(p in available for p in GPU_PROVIDERS), _preload_error)


@dataclass(slots=True)
class Session:
    session: ort.InferenceSession
    device: str  # "cuda" | "directml" | "cpu"
    fallback_reason: str | None
    model: Path | None = None
    cpu_threads: int = 0
    last_error: str | None = None  # the GPU error that moved this model to the CPU

    def run(self, output_names: list[str] | None, feeds: dict) -> list:
        """Run; if the graphics card fails at run time, continue on the CPU (once, for good).

        A GPU provider can accept a model and still fail on some inputs (an operator or a shape
        the driver cannot handle); the photo must still be measured.
        """
        try:
            return self.session.run(output_names, feeds)
        except Exception as exc:  # noqa: BLE001 - any provider error: try the CPU
            if self.device == "cpu" or self.model is None:
                raise
            name = self.model.name
            self.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            log.warning("GPU (%s) failed on %s: %s; switching this model to the CPU",
                        self.device, name, type(exc).__name__)
            self.session = ort.InferenceSession(str(self.model), sess_options=_options(False, self.cpu_threads),
                                                providers=["CPUExecutionProvider"])
            self.fallback_reason = f"Card đồ hoạ lỗi khi chạy {name} ({type(exc).__name__}); mô hình này chuyển sang CPU"
            self.device = "cpu"
            return self.session.run(output_names, feeds)


def _options(directml: bool, cpu_threads: int = 0, fixed_dims: dict[str, int] | None = None) -> ort.SessionOptions:
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    if cpu_threads:
        opts.intra_op_num_threads = cpu_threads
    for name, value in (fixed_dims or {}).items():  # e.g. {"h": 384, "w": 576}: a graph for one input size
        opts.add_free_dimension_override_by_name(name, value)
    if directml:  # required by the DirectML provider
        opts.enable_mem_pattern = False
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return opts


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
    if "OpenVINOExecutionProvider" in available:
        attempts.append(("openvino", [("OpenVINOExecutionProvider", {"device_type": "CPU"}), "CPUExecutionProvider"]))
    if "DmlExecutionProvider" in available:
        if _dml_device is not None:  # the graphics card measured fastest (gpu_speed_check)
            attempts.append(("directml", [("DmlExecutionProvider", {"device_id": _dml_device}), "CPUExecutionProvider"]))
            return attempts
        attempts.append(("directml", [("DmlExecutionProvider", dict(_DML_PREFERRED_OPTIONS)), "CPUExecutionProvider"]))
        attempts.append(("directml", [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]))
    return attempts


_dml_device: int | None = None  # DXGI adapter index DirectML uses, once measured
gpu_name: str | None = None  # the graphics card the speed check chose (shown to the user)


def list_gpus() -> list[dict]:
    """Graphics adapters in DXGI order (= DirectML device_id), Windows only; [] elsewhere or on error.

    Laptops usually list the integrated GPU (which also draws the screen) first.
    """
    import sys

    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import POINTER, WINFUNCTYPE, byref, c_long, c_uint, c_void_p

        class Guid(ctypes.Structure):
            _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

        class AdapterDesc1(ctypes.Structure):
            _fields_ = [("Description", ctypes.c_wchar * 128), ("VendorId", c_uint), ("DeviceId", c_uint),
                        ("SubSysId", c_uint), ("Revision", c_uint), ("DedicatedVideoMemory", ctypes.c_size_t),
                        ("DedicatedSystemMemory", ctypes.c_size_t), ("SharedSystemMemory", ctypes.c_size_t),
                        ("LuidLow", ctypes.c_uint32), ("LuidHigh", ctypes.c_int32), ("Flags", c_uint)]

        iid = Guid(0x770AAE78, 0xF26F, 0x4DBA, (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87))
        factory = c_void_p()
        if ctypes.windll.dxgi.CreateDXGIFactory1(byref(iid), byref(factory)) != 0:
            return []

        def method(obj: c_void_p, index: int, *argtypes):  # noqa: ANN002, ANN202 - COM vtable call
            vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
            return WINFUNCTYPE(c_long, c_void_p, *argtypes)(vtable[index])

        out = []
        try:
            for i in range(16):
                adapter = c_void_p()
                if method(factory, 12, c_uint, POINTER(c_void_p))(factory, i, byref(adapter)) != 0:
                    break  # DXGI_ERROR_NOT_FOUND: no more adapters
                desc = AdapterDesc1()
                method(adapter, 10, POINTER(AdapterDesc1))(adapter, byref(desc))
                method(adapter, 2)(adapter)  # Release
                out.append({"index": i, "name": desc.Description, "vram_mb": desc.DedicatedVideoMemory // 2**20,
                            "software": bool(desc.Flags & 2)})
        finally:
            method(factory, 2)(factory)
        return out
    except Exception:  # noqa: BLE001 - informative only
        log.warning("could not list graphics adapters", exc_info=True)
        return []


def create_gpu_session(model: Path, *, gpu_mem_limit_mb: int = DEFAULT_GPU_MEM_LIMIT_MB, cpu_threads: int = 0,
                       allow_directml: bool = True, fixed_dims: dict[str, int] | None = None,
                       config: dict[str, str] | None = None, basic_optimizations: bool = False,
                       errors: list[str] | None = None) -> Session | None:
    """A session on the graphics card, or None (the reasons are appended to ``errors``).

    ``fixed_dims``: give the model's named free input dimensions fixed sizes (the session then only
    accepts that size). ``config``: ONNX Runtime session config entries, e.g.
    {"ep.dml.disable_graph_fusion": "1"}. ``basic_optimizations``: only the basic graph rewrites.
    These exist because DirectML failed on TOPIQ (owner's RTX 2080) in ways the CPU does not.
    """
    info = configure()
    errors = [] if errors is None else errors
    for label, providers in _gpu_attempts(info.available, gpu_mem_limit_mb):
        if label == "directml" and not allow_directml:
            errors.append("directml: không dùng cho mô hình này")
            continue
        assert all((p if isinstance(p, str) else p[0]) in ALLOWED_PROVIDERS for p in providers)
        opts = _options(label == "directml", cpu_threads, fixed_dims)
        for key, value in (config or {}).items():
            opts.add_session_config_entry(key, value)
        if basic_optimizations:
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        try:
            session = ort.InferenceSession(str(model), sess_options=opts, providers=providers)
        except Exception as exc:  # noqa: BLE001 - a broken GPU setup must not stop the app
            errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:400]}")
            continue
        used = session.get_providers()[0]
        if used in GPU_PROVIDERS:
            return Session(session, GPU_PROVIDERS[used], None, Path(model), cpu_threads)
        errors.append(f"{label}: không dùng được cho mô hình này")
    return None


def create_session(model: Path, *, prefer_gpu: bool = True, gpu_mem_limit_mb: int = DEFAULT_GPU_MEM_LIMIT_MB,
                   cpu_threads: int = 0, allow_directml: bool = True,
                   fixed_dims: dict[str, int] | None = None) -> Session:
    """GPU if possible (see create_gpu_session), else CPU. ``allow_directml=False``: CUDA or CPU only."""
    errors: list[str] = []
    if prefer_gpu:
        gpu = create_gpu_session(model, gpu_mem_limit_mb=gpu_mem_limit_mb, cpu_threads=cpu_threads,
                                 allow_directml=allow_directml, fixed_dims=fixed_dims, errors=errors)
        if gpu is not None:
            return gpu
    session = ort.InferenceSession(str(model), sess_options=_options(False, cpu_threads, fixed_dims),
                                   providers=["CPUExecutionProvider"])
    reason = None
    if prefer_gpu:
        short = "; ".join(e.split(":")[0] + (f": {e.split(':')[1].strip()}" if e.count(":") > 1 else "")
                          for e in errors)
        reason = (f"Không dùng được card đồ hoạ ({short}); dùng CPU" if errors
                  else "Bản ONNX Runtime đang cài không hỗ trợ card đồ hoạ; dùng CPU")
    return Session(session, "cpu", reason, Path(model), cpu_threads, last_error="; ".join(errors) or None)


GPU_MUST_BE_FASTER = 0.8  # the GPU is used only if it takes at most 80% of the CPU's time
_speed_cache: dict[str, tuple[bool, str]] = {}


def _time_session(session: Session, runs: int) -> float:
    """Milliseconds per run on a zero input (after one warm-up run: GPU providers compile then)."""
    import time

    import numpy as np

    inp = session.session.get_inputs()[0]
    dummy = np.zeros([d if isinstance(d, int) else 1 for d in inp.shape], np.float32)
    session.run(None, {inp.name: dummy})
    start = time.perf_counter()
    for _ in range(runs):
        session.run(None, {inp.name: dummy})
    return (time.perf_counter() - start) / runs * 1000


def gpu_speed_check(model: Path, runs: int = 3) -> tuple[bool, str]:
    """Is a graphics card really faster than the CPU here? Picks the fastest one for DirectML.

    A laptop has two GPUs and DirectML used to land on the integrated one (which also draws the
    screen): slower than the CPU and the whole PC stutters. Every hardware adapter is timed and the
    fastest is kept for this process (create_session then uses it). Cached per model.
    Returns (use the GPU, note for the user / log).
    """
    import time

    import numpy as np

    global _dml_device, gpu_name
    key = str(model)
    if key in _speed_cache:
        return _speed_cache[key]

    def timed(session: Session) -> float:
        return _time_session(session, runs)

    try:
        info = configure()
        cpu_ms = timed(create_session(model, prefer_gpu=False))
        candidates: list[tuple[float, str, int | None]] = []  # (ms, label, DirectML device id)
        if "CUDAExecutionProvider" in info.available:
            cuda = create_session(model, prefer_gpu=True, allow_directml=False)
            if cuda.device == "cuda":
                candidates.append((timed(cuda), "GPU NVIDIA (CUDA)", None))
        if not candidates and "DmlExecutionProvider" in info.available:
            gpus = [g for g in list_gpus() if not g["software"]] or [{"index": i, "name": f"card {i}"} for i in (0, 1)]
            for gpu in gpus:
                try:
                    sess = ort.InferenceSession(str(model), sess_options=_options(True),
                                                providers=[("DmlExecutionProvider", {"device_id": gpu["index"]}),
                                                           "CPUExecutionProvider"])
                except Exception:  # noqa: BLE001 - that adapter cannot run it
                    continue
                if sess.get_providers()[0] != "DmlExecutionProvider":
                    continue
                ms = timed(Session(sess, "directml", None, Path(model)))
                candidates.append((ms, f"GPU DirectML: {gpu['name'].strip()}", gpu["index"]))
        if not candidates and "OpenVINOExecutionProvider" in info.available:
            ov = create_session(model, prefer_gpu=True)
            if ov.device == "openvino":
                candidates.append((timed(ov), "OpenVINO (CPU Intel)", None))
        if not candidates:
            result = (False, "Không có card đồ hoạ dùng được; dùng CPU")
        else:
            measured = "; ".join(f"{label} {ms:.0f} ms" for ms, label, _ in sorted(candidates)) + f"; CPU {cpu_ms:.0f} ms"
            best_ms, best_label, best_index = min(candidates)
            if best_ms <= cpu_ms * GPU_MUST_BE_FASTER:
                _dml_device = best_index
                gpu_name = best_label.split(": ", 1)[-1]
                result = (True, f"Dùng {best_label} ({measured})")
            elif best_label.startswith("OpenVINO"):
                result = (False, f"OpenVINO không nhanh hơn CPU thường trên máy này ({measured}); dùng CPU")
            else:
                result = (False, f"Card đồ hoạ chậm hơn CPU trên máy này ({measured}); dùng CPU")
    except Exception as exc:  # noqa: BLE001 - the CPU always works
        result = (False, f"Kiểm tra card đồ hoạ lỗi ({type(exc).__name__}); dùng CPU")
    log.info("GPU speed check %s: %s", Path(model).name, result)
    _speed_cache[key] = result
    return result
