"""Offline self-test of an installed/packaged app: ``KiraPick.exe --self-test report.json``.

Proves on the target machine, with every outgoing Python network connection blocked
(native libraries are covered by switching their telemetry off: see app/__init__.py),
that the bundled models are present and verified, ONNX Runtime and OpenCV load,
and the full pipeline (import -> people -> quality -> grouping -> selection)
runs on two synthetic photos. Never touches the user's photos or sessions:
everything happens in a temporary folder that is deleted afterwards.
"""

from __future__ import annotations

import json
import socket
import sys
import tempfile
import time
import traceback
from pathlib import Path


class _NetworkBlocked(OSError):
    pass


def _block_network(attempts: list[str]) -> None:
    def refuse(*args, **_kw):  # noqa: ANN002, ANN003, ANN202
        attempts.append(repr(args[1:] if len(args) > 1 else args)[:200])
        raise _NetworkBlocked("network access is not allowed in KiraPick")

    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.socket.connect_ex = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.getaddrinfo = refuse  # type: ignore[assignment]


def _synthetic_photo(path: Path, seed: int) -> None:
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    img = (rng.random((900, 600, 3)) * 255).astype("uint8")
    img[200:800, 200:400] = (200, 120, 90)  # a block the detectors may or may not see
    Image.fromarray(img).save(path, "JPEG", quality=90)


def run(report_path: Path) -> int:
    report: dict = {"ok": False, "steps": [], "network_attempts": []}
    _block_network(report["network_attempts"])
    started = time.time()
    try:
        from app import __version__
        from app.ai.models import ModelRegistry, ModelState
        from app.ai.runtime import configure

        report["version"] = __version__
        import os

        if os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
            raise RuntimeError("ONNX Runtime telemetry is not disabled")
        report["steps"].append("ONNX Runtime telemetry disabled (ORT_DISABLE_TELEMETRY=1)")
        registry = ModelRegistry()
        report["models_dir"] = str(registry.models_dir)
        report["models"] = {s.spec.id: s.state.value for s in registry.all_status()}
        missing = [i for i, st in report["models"].items()
                   if st != ModelState.READY.value and registry.specs[i].purpose in ("identity", "quality")]
        if missing:
            raise RuntimeError(f"models not ready: {missing}")
        report["steps"].append("models verified (SHA-256)")
        info = configure()
        report["onnxruntime"] = {"version": info.ort_version, "providers": list(info.available)}
        report["steps"].append("onnxruntime loaded")

        # Graphics card: informative only (a PC without a usable GPU is fine, it uses the CPU).
        from app.ai.runtime import create_session

        gpu_model = registry.status("person_detector_m")
        if gpu_model.state is ModelState.READY:
            probe = create_session(gpu_model.path, prefer_gpu=True)
            import numpy as np

            inp = probe.session.get_inputs()[0]
            dummy = np.zeros([d if isinstance(d, int) else 1 for d in inp.shape], np.float32)
            probe.session.run(None, {inp.name: dummy})  # warm-up
            started = time.perf_counter()
            for _ in range(3):
                probe.session.run(None, {inp.name: dummy})
            ms = round((time.perf_counter() - started) / 3 * 1000)
            report["gpu"] = {"device": probe.device, "note": probe.fallback_reason, "yolox_m_ms": ms}
            report["steps"].append(f"graphics card: {probe.device}")

        from app.storage.project import Project
        from app.workers.analyze_job import AnalyzeJob
        from app.workers.import_job import ImportJob

        with tempfile.TemporaryDirectory(prefix="kirapick-selftest-") as tmp:
            shoot = Path(tmp) / "Ảnh thử"
            shoot.mkdir()
            for i in range(2):
                _synthetic_photo(shoot / f"TEST_{i:04d}.jpg", i)
            with Project.create(Path(tmp) / "session", "selftest") as project:
                imported = ImportJob(project, shoot).run()
                report["steps"].append(f"import: {imported.ingested} photos")
                people = AnalyzeJob(project, registry, prefer_gpu=False).run(mode="people")
                report["steps"].append(f"people: {people.analysed} analysed, {people.failed} failed, device {people.device}")
                quality = AnalyzeJob(project, registry, prefer_gpu=False).run(mode="quality")
                report["steps"].append(f"quality: {quality.measured} measured, {quality.measure_failed} failed")
                if imported.ingested != 2 or people.failed or quality.measure_failed:
                    raise RuntimeError("pipeline reported failures")
                from app.quality import select

                select.select_per_person(project.conn, 3)
                report["steps"].append("selection ran")
        if report["network_attempts"]:
            raise RuntimeError("the app tried to use the network")
        report["ok"] = True
    except Exception as exc:  # noqa: BLE001 - the report must always be written
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()[-4000:]
    report["seconds"] = round(time.time() - started, 1)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1] if len(sys.argv) > 1 else "selftest.json")))
