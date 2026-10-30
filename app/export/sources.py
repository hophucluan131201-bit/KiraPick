"""Where the export's files come from: the imported folders or another folder (Part 3 spec §3.3).

The other folder (a memory card, a backup drive) is only read: the scan lists names, sizes and modification times
without opening any file; nothing is created, renamed or changed there."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from app.export.errors import ExportError
from app.export.formats import file_kind

MANIFEST_DIR = "_kirapick_danh_sach"
_SKIPPED_DIRS = {"$recycle.bin", "system volume information", MANIFEST_DIR}
_HIDDEN = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 4)
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_PROGRESS_EVERY = 256


class ScanCancelled(ExportError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalFile:
    path: Path
    kind: str  # raw | jpeg
    size: int
    mtime_ns: int
    relative: str  # POSIX path relative to the scanned root


@dataclass(slots=True)
class ExternalIndex:
    root: Path
    by_stem: dict[str, list[ExternalFile]] = field(default_factory=dict)  # stem.casefold() -> files, by path
    files: int = 0  # files indexed
    skipped: int = 0  # entries left out: unsupported, hidden, links, unreadable folders

    def candidates(self, stem: str, kind: str) -> list[ExternalFile]:
        """Files with exactly this base name (case-insensitive) and kind."""
        return [f for f in self.by_stem.get(stem.casefold(), ()) if f.kind == kind]


@dataclass(frozen=True, slots=True)
class SourceSpec:
    mode: Literal["imported", "external"] = "imported"
    root: Path | None = None
    index: ExternalIndex | None = None  # the scan of ``root`` (planning never rescans)


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def check_external_root(root: Path, *, session_folder: Path, destination: Path | None) -> Path:
    """The resolved root, or ExportError when it cannot be a source for this export."""
    if not root.exists():
        raise ExportError("không tìm thấy thư mục nguồn (thẻ nhớ đã rút, hoặc ổ đĩa chưa cắm?)")
    if not root.is_dir():
        raise ExportError("nguồn đã chọn không phải là thư mục")
    resolved = root.resolve()
    if _within(resolved, session_folder.resolve()):
        raise ExportError("không thể lấy ảnh từ thư mục dữ liệu phiên làm việc của KiraPick")
    if destination is not None:
        dest = destination.resolve()
        if _within(dest, resolved):
            raise ExportError("thư mục đích nằm trong thư mục nguồn — hãy chọn thư mục đích ở chỗ khác")
        if _within(resolved, dest):
            raise ExportError("thư mục nguồn nằm trong thư mục đích — hãy chọn thư mục đích ở chỗ khác")
    return resolved


def _is_link(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(entry.path):
        return True
    attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & _REPARSE)


def _is_hidden(entry: os.DirEntry[str]) -> bool:
    if entry.name.startswith("."):
        return True
    attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & _HIDDEN)


def scan_external(
    root: Path,
    *,
    session_folder: Path,
    destination: Path | None,
    progress: Callable[[int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ExternalIndex:
    """Index RAW and JPEG files under ``root`` by base name. Links, junctions and reparse points are never followed;
    hidden / system folders and KiraPick's own lists are skipped; no file is opened."""
    resolved = check_external_root(root, session_folder=session_folder, destination=destination)
    index = ExternalIndex(resolved)
    seen = 0
    pending = [resolved]
    while pending:
        if should_cancel is not None and should_cancel():
            raise ScanCancelled("đã huỷ quét thư mục nguồn")
        folder = pending.pop()
        try:
            with os.scandir(folder) as it:
                entries = list(it)
        except OSError:
            if folder == resolved:
                raise ExportError("không đọc được thư mục nguồn") from None
            index.skipped += 1
            continue
        for entry in entries:
            try:
                if _is_link(entry) or _is_hidden(entry):
                    index.skipped += 1
                    if not entry.is_dir(follow_symlinks=False):
                        seen += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.casefold() in _SKIPPED_DIRS:
                        index.skipped += 1
                    else:
                        pending.append(Path(entry.path))
                    continue
                seen += 1
                kind = file_kind(entry.name)
                if not entry.is_file(follow_symlinks=False) or kind not in ("raw", "jpeg"):
                    index.skipped += 1
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError:
                index.skipped += 1
                continue
            path = Path(entry.path)
            ext = ExternalFile(path, kind, st.st_size, st.st_mtime_ns, path.relative_to(resolved).as_posix())
            index.by_stem.setdefault(PurePosixPath(entry.name).stem.casefold(), []).append(ext)
            index.files += 1
            if progress is not None and seen % _PROGRESS_EVERY == 0:
                progress(seen)
    for files in index.by_stem.values():
        files.sort(key=lambda f: f.relative)  # the same index whatever order the file system lists entries in
    if progress is not None:
        progress(seen)
    return index
