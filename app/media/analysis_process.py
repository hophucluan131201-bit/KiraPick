"""Runs 'Phân tích sự kiện' in a separate process, like the Chụp cá nhân analysis (app.workers.analyze_process): the
window never freezes while the models load or run, and a crashed graphics driver ends only the child. The child
opens its own connection to the event database (SQLite WAL) and reports progress through a queue."""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue as queue_mod
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

POLL_S = 0.1


def _child(folder: str, prefer_gpu: bool, out: mp.Queue, cancel: mp.Event) -> None:  # runs in the child process
    try:
        from logging.handlers import RotatingFileHandler

        from app.branding import data_dir

        import os

        # the self-test sends this to a temporary folder: it must leave the user's data folder byte-identical
        log_dir = Path(os.environ["KIRAPICK_LOG_DIR"]) if os.environ.get("KIRAPICK_LOG_DIR") else data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "kirapick-media.log", maxBytes=2_000_000, backupCount=2,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    except Exception:  # noqa: BLE001 - logging is optional
        pass
    try:
        from app.media.analysis import analyse_event
        from app.storage.project import Project

        with Project.open(Path(folder)) as event:
            summary = analyse_event(event, prefer_gpu=prefer_gpu,
                                    progress=lambda done, total: out.put(("progress", done, total)),
                                    should_cancel=cancel.is_set)
        out.put(("done", asdict(summary)))
    except Exception as exc:  # noqa: BLE001 - reported to the window
        logging.getLogger("app.media").exception("media analysis failed")
        out.put(("failed", f"{type(exc).__name__}: {exc}"))


def run_in_child(folder: Path, prefer_gpu: bool, progress: Callable[[int, int], None],
                 is_cancelled: Callable[[], bool]) -> dict:
    """Blocking (call from a worker thread). Returns the AnalysisSummary as a dict; raises RuntimeError on failure."""
    ctx = mp.get_context("spawn")
    out: mp.Queue = ctx.Queue()
    cancel = ctx.Event()
    child = ctx.Process(target=_child, name="kirapick-media", daemon=True, args=(str(folder), prefer_gpu, out, cancel))
    child.start()
    try:
        while True:
            if is_cancelled() and not cancel.is_set():
                cancel.set()
            try:
                msg = out.get(timeout=POLL_S)
            except queue_mod.Empty:
                if not child.is_alive():
                    try:
                        msg = out.get(timeout=POLL_S * 5)
                    except queue_mod.Empty:
                        raise RuntimeError(
                            f"Tiến trình phân tích dừng đột ngột (mã {child.exitcode}). Phần đã xong được giữ; "
                            "bấm 🧠 Phân tích sự kiện để chạy tiếp.") from None
                else:
                    continue
            if msg[0] == "progress":
                progress(msg[1], msg[2])
            elif msg[0] == "done":
                return msg[1]
            else:
                raise RuntimeError(msg[1])
    finally:
        child.join(timeout=30)
        if child.is_alive():
            child.kill()
