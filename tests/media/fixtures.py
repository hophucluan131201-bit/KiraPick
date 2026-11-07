"""Synthetic event photos for the Media tests: small JPEGs with EXIF capture time, camera make and model."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image


def photo(path: Path, seed: int, *, taken: str | None = None, make: str | None = None, model: str | None = None,
          size: tuple[int, int] = (320, 240)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    if make:
        exif[0x010F] = make
    if model:
        exif[0x0110] = model
    if taken:
        exif.get_ifd(0x8769)[0x9003] = taken
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)).save(
        path, "JPEG", quality=80, exif=exif.tobytes())
    return path


def hashes(folder: Path) -> dict[str, str]:
    """SHA-256 of every file under ``folder`` (the original photos must never change)."""
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}
