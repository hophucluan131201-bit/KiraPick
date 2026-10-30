"""Part 3 Task 5 — read-only index of another folder (card, drive) (spec §3.3 point 1)."""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.export.copy_export import ExportError
from app.export.sources import ExternalFile, ScanCancelled, scan_external
from tests.fixtures_export import tree_digest, write_file


def _card(tmp_path: Path) -> Path:
    card = tmp_path / "card"
    write_file(card / "DCIM" / "100NIKON" / "DSC_0001.NEF", 1, 2000)
    write_file(card / "DCIM" / "100NIKON" / "DSC_0001.JPG", 2, 1000)
    write_file(card / "DCIM" / "101NIKON" / "dsc_0001.nef", 3, 3000)  # counter restart, other case
    write_file(card / "DCIM" / "100NIKON" / "DSC_0002.JPEG", 4, 500)
    write_file(card / "DCIM" / "100NIKON" / "DSC_0003.TIF", 5, 500)  # other raster: not indexed externally
    return card


def _scan(card: Path, tmp_path: Path, **kw):  # noqa: ANN003, ANN202
    return scan_external(card, session_folder=tmp_path / "session", destination=tmp_path / "out", **kw)


def test_index_by_stem_casefold_and_kind(tmp_path: Path) -> None:
    card = _card(tmp_path)
    index = _scan(card, tmp_path)
    assert index.root == card.resolve()
    assert sorted(index.by_stem) == ["dsc_0001", "dsc_0002"]
    files = index.by_stem["dsc_0001"]
    assert sorted((f.kind, f.relative, f.size) for f in files) == [
        ("jpeg", "DCIM/100NIKON/DSC_0001.JPG", 1000),
        ("raw", "DCIM/100NIKON/DSC_0001.NEF", 2000),
        ("raw", "DCIM/101NIKON/dsc_0001.nef", 3000),
    ]
    assert all(isinstance(f, ExternalFile) and f.path.is_absolute() and f.mtime_ns > 0 for f in files)
    assert index.by_stem["dsc_0002"][0].kind == "jpeg"
    assert index.files == 4 and index.skipped == 1  # the TIFF
    assert [f.relative for f in index.candidates("DSC_0001", "jpeg")] == ["DCIM/100NIKON/DSC_0001.JPG"]


def test_unsupported_and_hidden_skipped(tmp_path: Path) -> None:
    card = tmp_path / "card"
    write_file(card / "notes.txt", 1, 10)
    write_file(card / ".hidden" / "DSC_0001.NEF", 2, 10)
    write_file(card / "_kirapick_danh_sach" / "DSC_0002.JPG", 3, 10)
    write_file(card / "._DSC_0003.JPG", 4, 10)  # macOS resource fork
    write_file(card / "$RECYCLE.BIN" / "DSC_0004.JPG", 5, 10)
    write_file(card / "System Volume Information" / "DSC_0005.JPG", 6, 10)
    write_file(card / "ok" / "DSC_0006.JPG", 7, 10)
    index = _scan(card, tmp_path)
    assert list(index.by_stem) == ["dsc_0006"]
    assert index.files == 1 and index.skipped >= 2


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need a privilege on Windows")
def test_symlink_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write_file(outside / "DSC_0009.NEF", 1, 10)
    card = tmp_path / "card"
    write_file(card / "DSC_0001.NEF", 2, 10)
    (card / "linkdir").symlink_to(outside, target_is_directory=True)
    (card / "DSC_0009.NEF").symlink_to(outside / "DSC_0009.NEF")
    (card / "loop").symlink_to(card, target_is_directory=True)
    index = _scan(card, tmp_path)
    assert list(index.by_stem) == ["dsc_0001"]
    assert index.skipped == 3


@pytest.mark.skipif(sys.platform != "win32", reason="junctions exist on Windows only")
def test_junction_and_reparse_point_skipped(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write_file(outside / "DSC_0009.NEF", 1, 10)
    card = tmp_path / "card"
    write_file(card / "DSC_0001.NEF", 2, 10)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(card / "junction"), str(outside)], check=True,
                   capture_output=True)
    index = _scan(card, tmp_path)
    assert list(index.by_stem) == ["dsc_0001"] and index.skipped == 1


def test_scan_reads_no_file_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = _card(tmp_path)

    def no_open(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("the scan opened a file")

    monkeypatch.setattr(builtins, "open", no_open)
    monkeypatch.setattr(Path, "open", no_open)
    monkeypatch.setattr(os, "open", no_open)
    assert _scan(card, tmp_path).files == 4


def _dir_state(root: Path) -> dict[str, tuple[int, int]]:
    out = {}
    for dirpath, dirs, _names in os.walk(root):
        for d in [dirpath, *[os.path.join(dirpath, x) for x in dirs]]:
            st = os.stat(d)
            out[d] = (st.st_mtime_ns, st.st_mode)
    return out


def test_scan_is_read_only(tmp_path: Path) -> None:
    card = _card(tmp_path)
    files, dirs = tree_digest(card), _dir_state(card)
    _scan(card, tmp_path)
    assert tree_digest(card) == files and _dir_state(card) == dirs
    assert not (tmp_path / "out").exists()  # the scan creates nothing, not even the destination


def test_cancel_raises_scan_cancelled(tmp_path: Path) -> None:
    card = _card(tmp_path)
    with pytest.raises(ScanCancelled):
        _scan(card, tmp_path, should_cancel=lambda: True)


def test_progress_reports_files_seen(tmp_path: Path) -> None:
    card = _card(tmp_path)
    seen: list[int] = []
    _scan(card, tmp_path, progress=seen.append)
    assert seen and seen[-1] == 5 and seen == sorted(seen)


@pytest.mark.parametrize("case", ["missing", "not_a_folder", "session_folder", "inside_session", "dest_inside_root",
                                  "dest_is_root", "root_inside_dest"])
def test_root_rules(tmp_path: Path, case: str) -> None:
    session = tmp_path / "session"
    (session / "sub").mkdir(parents=True)
    card = _card(tmp_path)
    dest = tmp_path / "out"
    root = {
        "missing": tmp_path / "nowhere",
        "not_a_folder": card / "DCIM" / "100NIKON" / "DSC_0001.NEF",
        "session_folder": session,
        "inside_session": session / "sub",
        "dest_inside_root": card,
        "dest_is_root": card,
        "root_inside_dest": dest / "card",
    }[case]
    if case == "dest_inside_root":
        dest = card / "Xuất"
    elif case == "dest_is_root":
        dest = card
    elif case == "root_inside_dest":
        write_file(root / "DSC_0001.NEF", 1, 10)
    with pytest.raises(ExportError) as err:
        scan_external(root, session_folder=session, destination=dest)
    assert err.value.args[0]  # a Vietnamese message for the dialog


def test_destination_none_is_allowed(tmp_path: Path) -> None:
    card = _card(tmp_path)
    assert scan_external(card, session_folder=tmp_path / "session", destination=None).files == 4
