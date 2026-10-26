"""Source-file fingerprints for dedupe and change detection (read-only)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

_EDGE_BYTES = 64 * 1024
_CHUNK = 1024 * 1024


@dataclass(frozen=True, slots=True)
class Fingerprint:
    size: int
    mtime_ns: int
    quick_hash: str  # sha256(size || first 64 KiB || last 64 KiB)

    def content_key(self) -> tuple[int, str]:
        """Identity of the bytes, independent of path and mtime (for dedupe)."""
        return self.size, self.quick_hash


def quick_fingerprint(path: Path) -> Fingerprint:
    """Cheap fingerprint: reads at most 128 KiB regardless of file size.

    RAW headers and trailers carry capture time, maker notes and the start/end
    of sensor data, so two different photos colliding here is not a practical
    concern; ``full_sha256`` is available where certainty is required.
    """
    st = os.stat(path)
    digest = hashlib.sha256(st.st_size.to_bytes(8, "little"))
    with open(path, "rb") as fh:
        digest.update(fh.read(_EDGE_BYTES))
        if st.st_size > _EDGE_BYTES:
            fh.seek(max(_EDGE_BYTES, st.st_size - _EDGE_BYTES))
            digest.update(fh.read(_EDGE_BYTES))
    return Fingerprint(st.st_size, st.st_mtime_ns, digest.hexdigest())


def full_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
