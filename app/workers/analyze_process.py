"""Runs the AI analysis in a separate process, so the window never freezes.

Loading and running the models (above all on DirectML) can keep Python busy for many seconds;
in the window's own process that made Windows report "Not responding". The child process
opens its own database connection (SQLite WAL), reports progress through a queue and stops
when asked. If the graphics driver kills the child, the window stays alive and says so.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue as queue_mod
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

log = logging.getLogger(__name__)

POLL_S = 0.1


def _child(folder: str, mode: str, learning_dir: str | None, prefer_gpu: bool,
           out: mp.Queue, cancel: mp.Event) -> None:  # runs in the child process
    try:
        from logging.handlers import RotatingFileHandler

        from app.branding import data_dir

        log_dir = data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "kirapick-ai.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    except Exception:  # noqa: BLE001 - logging is optional
        pass
    try:
        from app.ai.models import ModelUnavailableError
        from app.storage.project import Project
        from app.workers.analyze_job import AnalyzeJob

        try:
            with Project.open(Path(folder)) as project:
                summary = AnalyzeJob(project, learning_dir=Path(learning_dir) if learning_dir else None,
                                     prefer_gpu=prefer_gpu).run(
                    progress=lambda p: out.put(("progress", p.phase, p.done, p.total)),
                    should_cancel=cancel.is_set, mode=mode)
            out.put(("done", asdict(summary)))
        except ModelUnavailableError as exc:
            out.put(("failed", f"{exc}\n\nCài lại ứng dụng, hoặc (bản mã nguồn) chạy một lần:\n"
                               ".\\.venv\\Scripts\\python .\\scripts\\fetch_models.py"))
    except Exception as exc:  # noqa: BLE001 - reported to the window
        logging.getLogger("app.ai").exception("analysis failed")
        out.put(("failed", f"{type(exc).__name__}: {exc}"))


def run_in_child(folder: Path, mode: str, learning_dir: Path | None, prefer_gpu: bool,
                 progress: Callable[[str, int, int], None], is_cancelled: Callable[[], bool]) -> dict:
    """Blocking (call from a worker thread). Returns the summary dict; raises RuntimeError on failure."""
    ctx = mp.get_context("spawn")
    out: mp.Queue = ctx.Queue()
    cancel = ctx.Event()
    child = ctx.Process(target=_child, name="kirapick-ai", daemon=True,
                        args=(str(folder), mode, str(learning_dir) if learning_dir else None, prefer_gpu, out, cancel))
    child.start()
    try:
        while True:
            if is_cancelled() and not cancel.is_set():
                cancel.set()
            try:
                msg = out.get(timeout=POLL_S)
            except queue_mod.Empty:
                if not child.is_alive():
                    try:  # the result may have arrived just before the child ended
                        msg = out.get(timeout=POLL_S * 5)
                    except queue_mod.Empty:
                        raise RuntimeError(
                            f"Tiến trình AI dừng đột ngột (mã {child.exitcode}). Có thể do driver card đồ hoạ: "
                            "thử tắt ⚡ Dùng card đồ hoạ rồi bấm lại; phần đã xong được giữ.") from None
                else:
                    continue
            if msg[0] == "progress":
                progress(msg[1], msg[2], msg[3])
            elif msg[0] == "done":
                return msg[1]
            else:
                raise RuntimeError(msg[1])
    finally:
        child.join(timeout=30)
        if child.is_alive():
            child.kill()
