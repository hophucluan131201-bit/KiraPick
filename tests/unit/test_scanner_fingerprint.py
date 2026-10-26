from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.ingest.fingerprint import full_sha256, quick_fingerprint
from app.ingest.formats import FORMATS, MediaKind, SupportLevel, format_for, is_raw
from app.ingest.scanner import PairStatus, classify_pair, find_pair_candidates, scan_folder


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_format_registry() -> None:
    assert format_for(Path("A.NEF")) is FORMATS[".nef"]
    assert is_raw(Path("x.Cr3")) and not is_raw(Path("x.jpg")) and format_for(Path("x.txt")) is None
    verified = {e for e, f in FORMATS.items() if f.kind is MediaKind.RAW and f.level is SupportLevel.VERIFIED}
    assert {".nef", ".cr2", ".cr3", ".arw"} <= verified


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "Buổi chụp cosplay"
    _touch(root / "DSC_0001.NEF")
    _touch(root / "DSC_0001.JPG")
    _touch(root / "Ngày 2" / "DSC_0002.nef")
    _touch(root / "Ngày 2" / "ảnh đẹp.jpeg")
    _touch(root / "Ngày 2" / "notes.txt")
    _touch(root / ".hidden" / "DSC_9999.NEF")
    _touch(root / "$RECYCLE.BIN" / "DSC_8888.NEF")
    _touch(root / "amb" / "B.NEF")
    _touch(root / "amb" / "B.DNG")
    _touch(root / "amb" / "B.jpg")
    return root


def test_scan_finds_supported_files_recursively_with_unicode(tree: Path) -> None:
    report = scan_folder(tree)
    assert [e.relative_path for e in report.entries] == [
        "DSC_0001.JPG",
        "DSC_0001.NEF",
        "Ngày 2/DSC_0002.nef",
        "Ngày 2/ảnh đẹp.jpeg",
        "amb/B.DNG",
        "amb/B.NEF",
        "amb/B.jpg",
    ]
    assert report.unsupported_extensions == {".txt": 1}
    assert not report.cancelled


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_scan_never_follows_links(tree: Path, tmp_path: Path) -> None:
    outside = _touch(tmp_path / "outside" / "SECRET.NEF")
    os.symlink(outside, tree / "link.NEF")
    os.symlink(outside.parent, tree / "linkdir")
    os.symlink(tree, tree / "Ngày 2" / "loop")  # would recurse forever if followed
    report = scan_folder(tree)
    assert report.skipped_links == 3
    assert all("SECRET" not in e.relative_path and "loop" not in e.relative_path for e in report.entries)


def test_scan_cancel(tree: Path) -> None:
    assert scan_folder(tree, should_cancel=lambda: True).cancelled


def test_scan_rejects_file_root(tree: Path) -> None:
    with pytest.raises(NotADirectoryError):
        scan_folder(tree / "DSC_0001.NEF")


def test_pairing_by_folder_and_stem_skips_ambiguous(tree: Path) -> None:
    pairs = find_pair_candidates(scan_folder(tree).entries)
    assert [(p.raw.relative_path, p.jpeg.relative_path) for p in pairs] == [("DSC_0001.NEF", "DSC_0001.JPG")]


def test_pair_confirmation_uses_capture_time() -> None:
    t = datetime(2026, 10, 25, 16, 48, 19)
    assert classify_pair(t, t + timedelta(seconds=1)) is PairStatus.CONFIRMED
    assert classify_pair(t, t + timedelta(hours=2)) is PairStatus.TIME_MISMATCH
    assert classify_pair(t, None) is PairStatus.NAME_ONLY


def test_fingerprints(tmp_path: Path) -> None:
    payload = os.urandom(300_000)
    a = _touch(tmp_path / "a" / "X.NEF", payload)
    b = _touch(tmp_path / "b" / "Y.NEF", payload)
    assert quick_fingerprint(a).content_key() == quick_fingerprint(b).content_key()
    changed = bytearray(payload)
    changed[150_000] ^= 0xFF  # outside the hashed edges: quick hash cannot see it
    c = _touch(tmp_path / "c.NEF", bytes(changed))
    assert quick_fingerprint(c).quick_hash == quick_fingerprint(a).quick_hash
    assert full_sha256(c) != full_sha256(a)
    small = _touch(tmp_path / "tiny.jpg", b"abc")
    assert quick_fingerprint(small).size == 3
