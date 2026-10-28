"""Download → verify → activate atomically; the previous file is kept for "Quay lại bản trước"."""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

from app.branding import data_dir
from app.updates.catalog import TIMEOUT_S, Entry

Progress = Callable[[int, int], None]
Fetch = Callable[[str, Path, Progress], None]


class UpdateError(RuntimeError):
    pass


def updates_root() -> Path:
    return data_dir() / "models"


def fetch_url(url: str, dest: Path, progress: Progress) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "KiraPick-model-update"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp, open(dest, "wb") as out:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            progress(done, total)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def install(entry: Entry, fetch: Fetch, progress: Progress, root: Path | None = None) -> Path:
    root = root or updates_root()
    staged_dir = root / "staged" / f"{entry.id}-{entry.version}"
    active, previous = root / "active", root / "previous"
    for d in (staged_dir, active, previous):
        d.mkdir(parents=True, exist_ok=True)
    staged = staged_dir / entry.file
    try:
        fetch(entry.url, staged, progress)
        if staged.stat().st_size != entry.size or _sha256(staged) != entry.sha256:
            raise UpdateError(f"{entry.file}: tải về không khớp mã kiểm tra (SHA-256) — đã bỏ")
    except UpdateError:
        shutil.rmtree(staged_dir, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001 - any download problem: nothing becomes active
        shutil.rmtree(staged_dir, ignore_errors=True)
        raise UpdateError(f"{entry.file}: tải về thất bại ({type(exc).__name__})") from exc
    target = active / entry.file
    sidecar = active / (entry.file + ".sha256")
    if target.exists():
        os.replace(target, previous / entry.file)
        if sidecar.exists():
            os.replace(sidecar, previous / (entry.file + ".sha256"))
    os.replace(staged, target)  # same volume: atomic
    sidecar.write_text(f"{entry.sha256} {entry.size} catalog:{entry.version}\n", encoding="ascii")
    shutil.rmtree(staged_dir, ignore_errors=True)
    return target


def rollback(model_id: str, file: str, root: Path | None = None) -> None:
    """Back to the previous update, or to the model bundled with the app."""
    root = root or updates_root()
    active, previous = root / "active", root / "previous"
    for name in (file, file + ".sha256"):
        (active / name).unlink(missing_ok=True)
        if (previous / name).exists():
            os.replace(previous / name, active / name)
