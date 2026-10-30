"""Part 3 Task 5 — full SHA-256 of files, cancellable, cached per dialog (spec §3.9)."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

from app.export import hashing
from app.export.hashing import CHUNK, HashCache, HashCancelled, sha256_file
from tests.fixtures_export import write_file


def test_sha256_matches_hashlib(tmp_path: Path) -> None:
    for size in (0, 1, CHUNK - 1, CHUNK, CHUNK + 1, 3 * CHUNK + 17):
        p = write_file(tmp_path / f"f{size}.bin", size % 97, size)
        assert sha256_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_cache_reads_each_file_once(tmp_path: Path) -> None:
    p = write_file(tmp_path / "a.NEF", 1)
    cache = HashCache()
    first = cache.sha256(p)
    assert cache.sha256(p) == first and cache.sha256(tmp_path / "." / "a.NEF") == first
    assert cache.reads == 1 and cache.hits == 2
    assert cache.known(p) == first


def test_cache_invalidated_by_mtime_or_size(tmp_path: Path) -> None:
    p = write_file(tmp_path / "a.NEF", 1)
    cache = HashCache()
    old = cache.sha256(p)
    st = p.stat()
    write_file(p, 2)  # same size, other bytes
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert cache.known(p) is None
    assert cache.sha256(p) != old and cache.reads == 2
    write_file(p, 2, 1000)  # other size
    assert cache.known(p) is None


def test_seed_used_only_when_size_and_mtime_match(tmp_path: Path) -> None:
    p = write_file(tmp_path / "a.JPG", 3)
    st = p.stat()
    cache = HashCache()
    cache.seed(p, st.st_size + 1, st.st_mtime_ns, "f" * 64)  # stale database row: ignored
    assert cache.known(p) is None
    cache.seed(p, st.st_size, st.st_mtime_ns, "e" * 64)
    assert cache.known(p) == "e" * 64 and cache.sha256(p) == "e" * 64 and cache.reads == 0


def test_cancel_between_chunks(tmp_path: Path) -> None:
    p = write_file(tmp_path / "big.NEF", 4, 3 * CHUNK)
    calls = []

    def cancel() -> bool:
        calls.append(1)
        return len(calls) > 1  # after the first chunk

    with pytest.raises(HashCancelled):
        sha256_file(p, should_cancel=cancel)
    assert len(calls) == 2
    cache = HashCache()
    with pytest.raises(HashCancelled):
        cache.sha256(p, should_cancel=lambda: True)
    assert cache.known(p) is None  # a cancelled hash is never cached


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_hash_opens_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = write_file(tmp_path / "ro.NEF", 5)
    p.chmod(0o444)
    modes = []
    real_open = open

    def spy(file, mode="r", *args, **kwargs):  # noqa: ANN001, ANN202
        modes.append(mode)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(hashing, "open", spy, raising=False)
    assert sha256_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()
    assert modes == ["rb"]


def test_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        HashCache().sha256(tmp_path / "gone.NEF")
