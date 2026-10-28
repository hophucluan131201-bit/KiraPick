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


SAMPLE_PHOTOS = 3  # real photos copied from the folder given on the command line


def _copy_samples(folder: Path, dest: Path) -> list[str]:
    """Copy (read only) the first few supported photos of ``folder``; the originals are never touched."""
    import shutil

    from app.ingest.formats import format_for

    names = []
    if not folder.is_dir():
        raise FileNotFoundError(f"không thấy thư mục ảnh “{folder}” — kiểm tra lại đường dẫn (thẻ nhớ đã cắm chưa?)")
    for f in sorted(folder.iterdir()):
        if f.is_file() and not f.is_symlink() and format_for(f) is not None:
            shutil.copy2(f, dest / f.name)
            names.append(f.name)
            if len(names) == SAMPLE_PHOTOS:
                break
    return names


def run(report_path: Path, photos: Path | None = None) -> int:
    """``photos``: optional folder of real photos; a few are copied and run through every stage."""
    report: dict = {"ok": False, "steps": [], "network_attempts": []}

    def step(text: str) -> None:
        """Record a finished step and save the report at once: a hard exit still shows how far it got."""
        report["steps"].append(text)
        print(text, flush=True)
        try:
            _write_report(report_path, report)
        except Exception:  # noqa: BLE001 - the final write reports any problem
            pass

    _block_network(report["network_attempts"])
    started = time.time()
    try:
        from app import __version__
        from app.ai.models import ModelRegistry, ModelState
        from app.ai.runtime import configure

        report["version"] = __version__
        from app.edition import EDITION

        report["edition"] = EDITION
        import os

        if os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
            raise RuntimeError("ONNX Runtime telemetry is not disabled")
        step("ONNX Runtime telemetry disabled (ORT_DISABLE_TELEMETRY=1)")
        registry = ModelRegistry()
        report["models_dir"] = str(registry.models_dir)
        report["models"] = {s.spec.id: s.state.value for s in registry.all_status()}
        missing = [i for i, st in report["models"].items()
                   if st != ModelState.READY.value
                   and registry.specs[i].purpose in ("identity", "identity_plus", "quality")]
        if missing:
            raise RuntimeError(f"models not ready: {missing}")
        step("models verified (SHA-256)")
        report["aesthetic_model"] = report["models"].get("aesthetic", "not in manifest")
        report["identity_plus"] = registry.ready("identity_plus")  # ArcFace + YoutuReID
        info = configure()
        report["onnxruntime"] = {"version": info.ort_version, "providers": list(info.available)}
        step("onnxruntime loaded")

        # Graphics card: informative only (a PC without a usable GPU is fine, it uses the CPU).
        from app.ai.runtime import create_session

        gpu_model = registry.status("person_detector_m")
        if gpu_model.state is ModelState.READY:
            probe = create_session(gpu_model.path, prefer_gpu=True)
            import numpy as np

            inp = probe.session.get_inputs()[0]
            dummy = np.zeros([d if isinstance(d, int) else 1 for d in inp.shape], np.float32)
            probe.session.run(None, {inp.name: dummy})  # warm-up
            t0 = time.perf_counter()
            for _ in range(3):
                probe.session.run(None, {inp.name: dummy})
            ms = round((time.perf_counter() - t0) / 3 * 1000)
            report["gpu"] = {"device": probe.device, "note": probe.fallback_reason, "yolox_m_ms": ms}
            from app.ai.runtime import gpu_speed_check

            use, note = gpu_speed_check(registry.require("person_detector_s"))
            report["gpu"]["faster_than_cpu"], report["gpu"]["speed_check"] = use, note
            from app.ai.runtime import list_gpus

            report["gpu"]["adapters"] = list_gpus()  # DXGI order = DirectML device_id
            step(f"graphics card: {probe.device}")

        from app.storage.project import Project
        from app.workers.analyze_job import AnalyzeJob
        from app.workers.import_job import ImportJob

        with tempfile.TemporaryDirectory(prefix="kirapick-selftest-") as tmp:
            shoot = Path(tmp) / "Ảnh thử"
            shoot.mkdir()
            expected = 2
            for i in range(2):
                _synthetic_photo(shoot / f"TEST_{i:04d}.jpg", i)
            if photos is not None:
                copied = _copy_samples(photos, shoot)
                report["sample_photos"] = copied
                expected += len(copied)
            with Project.create(Path(tmp) / "session", "selftest") as project:
                imported = ImportJob(project, shoot).run()
                step(f"import: {imported.ingested} photos")
                gpu = photos is not None  # with real photos, use the graphics card like the app does
                people = AnalyzeJob(project, registry, prefer_gpu=gpu).run(mode="people")
                step(f"people: {people.analysed} analysed, {people.failed} failed, device {people.device}")
                quality = AnalyzeJob(project, registry, prefer_gpu=gpu).run(mode="quality")
                step(f"quality: {quality.measured} measured, {quality.measure_failed} failed, "
                                       f"device {quality.device}")
                from app.workers import quality_job

                report["quality_timings_s"] = dict(quality_job.last_timings)
                report["aesthetic_gpu_check"] = dict(quality_job.last_aesthetic_check)
                report["quality_plus_models"] = dict(quality_job.last_extras)
                report["stage_errors"] = [dict(r) for r in project.conn.execute(
                    """SELECT a.relative_path AS file, s.stage, s.error FROM stage_status s
                       JOIN assets a ON a.id = s.asset_id WHERE s.state = 'failed'""")]
                if imported.ingested != expected or people.failed or quality.measure_failed:
                    raise RuntimeError("pipeline reported failures (see stage_errors)")
                from app.quality import select

                select.select_per_person(project.conn, 3)
                step("selection ran")
            # The window runs the AI in a child process of the exe: prove that starts and reports back.
            from app.workers.analyze_process import run_in_child

            child = run_in_child(Path(tmp) / "session", "people", None, False, lambda *_a: None, lambda: False)
            step(f"child process: ok ({child['analysed']} new photos)")
        if report["network_attempts"]:
            raise RuntimeError("the app tried to use the network")
        report["ok"] = True
    except Exception as exc:  # noqa: BLE001 - the report must always be written
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()[-4000:]
    report["seconds"] = round(time.time() - started, 1)
    _write_report(report_path, report)
    return 0 if report["ok"] else 1


def _fallback_report_dir() -> Path:
    from app.branding import data_dir

    return data_dir() / "logs"


def _write_report(path: Path, report: dict) -> Path:
    """Write the report; if that folder is missing or not writable (e.g. a Desktop moved to
    OneDrive), use the app's logs folder instead of losing the result. Returns where it went."""
    text = json.dumps(report, ensure_ascii=False, indent=1)
    try:
        path.write_text(text, encoding="utf-8")
        return path
    except OSError:
        fallback = _fallback_report_dir() / path.name
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(text, encoding="utf-8")
        return fallback


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1] if len(sys.argv) > 1 else "selftest.json")))
