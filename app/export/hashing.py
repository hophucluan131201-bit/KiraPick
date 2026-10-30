"""Full SHA-256 of a file, cancellable, and a per-dialog cache (Part 3 spec §3.9).

Only this proves that two files hold the same bytes; the quick fingerprint (size + head/tail) is a filter. Files are
opened read-only. Never called on the GUI thread (plan thread or copy thread)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

from app.export.errors import ExportError

CHUNK = 1 << 20


class HashCancelled(ExportError):
    pass


def sha256_file(path: Path, *, should_cancel: Callable[[], bool] | None = None) -> str:
    """SHA-256 of the file's bytes, read in 1 MiB chunks; ``should_cancel`` is asked between chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
            if should_cancel is not None and should_cancel():
                raise HashCancelled("đã huỷ kiểm tra nội dung")
    return digest.hexdigest()


class HashCache:
    """Hashes of one export dialog: a file is read at most once while its size and modification time stay the same."""

    def __init__(self) -> None:
        self._known: dict[tuple[str, int, int], str] = {}
        self.reads = 0  # files actually read
        self.hits = 0  # answers given without reading

    @staticmethod
    def _key(path: Path, size: int, mtime_ns: int) -> tuple[str, int, int]:
        return os.path.normcase(str(Path(path).resolve())), size, mtime_ns

    def seed(self, path: Path, size: int, mtime_ns: int, sha256: str) -> None:
        """A hash known from elsewhere (``assets.sha256`` of the import) for the file as it was then; used only while
        the file on disk still has that size and modification time."""
        self._known[self._key(path, size, mtime_ns)] = sha256

    def known(self, path: Path) -> str | None:
        try:
            st = os.stat(path)
        except OSError:
            return None
        return self._known.get(self._key(path, st.st_size, st.st_mtime_ns))

    def sha256(self, path: Path, *, should_cancel: Callable[[], bool] | None = None) -> str:
        st = os.stat(path)
        key = self._key(path, st.st_size, st.st_mtime_ns)
        if key in self._known:
            self.hits += 1
            return self._known[key]
        value = sha256_file(path, should_cancel=should_cancel)
        self.reads += 1
        after = os.stat(path)
        if (after.st_size, after.st_mtime_ns) == (st.st_size, st.st_mtime_ns):  # not changed while being read
            self._known[key] = value
        return value
