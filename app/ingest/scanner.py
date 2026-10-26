"""Recursive, read-only folder scan and RAW+JPEG pairing.

Safety rules: symlinks and Windows junctions are never followed (no loops, no
escaping the chosen root), hidden and system folders are skipped, and an
unreadable folder is reported without aborting the scan.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from app.ingest.formats import PAIRABLE_RASTER_EXTENSIONS, FormatInfo, MediaKind, format_for

_SKIPPED_DIR_NAMES = frozenset({"$recycle.bin", "system volume information", "__macosx"})


@dataclass(frozen=True, slots=True)
class ScanEntry:
    path: Path  # absolute
    relative_path: str  # POSIX-style, relative to the scan root
    format: FormatInfo


@dataclass(slots=True)
class ScanReport:
    root: Path
    entries: list[ScanEntry] = field(default_factory=list)
    skipped_links: int = 0
    unsupported_extensions: Counter[str] = field(default_factory=Counter)
    unreadable: list[str] = field(default_factory=list)  # relative paths of folders/files we could not list
    cancelled: bool = False


def _is_link(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    is_junction = getattr(entry, "is_junction", None)  # Python >= 3.12
    return bool(is_junction and is_junction())


def scan_folder(
    root: Path,
    *,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> ScanReport:
    """List importable files under ``root`` (sorted, deterministic)."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    report = ScanReport(root)
    stack = [root]
    while stack:
        if should_cancel is not None and should_cancel():
            report.cancelled = True
            break
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                children = sorted(it, key=lambda e: e.name)
        except OSError:
            report.unreadable.append(folder.relative_to(root).as_posix() or ".")
            continue
        subdirs: list[Path] = []
        for entry in children:
            if entry.name.startswith("."):
                continue
            try:
                if _is_link(entry):
                    report.skipped_links += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() not in _SKIPPED_DIR_NAMES:
                        subdirs.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                report.unreadable.append(Path(entry.path).relative_to(root).as_posix())
                continue
            path = Path(entry.path)
            info = format_for(path)
            if info is None:
                report.unsupported_extensions[path.suffix.lower() or "(none)"] += 1
                continue
            report.entries.append(ScanEntry(path, path.relative_to(root).as_posix(), info))
        stack.extend(reversed(subdirs))  # depth-first, alphabetical
        if on_progress is not None:
            on_progress(len(report.entries))
    report.entries.sort(key=lambda e: e.relative_path)
    return report


# -------------------------------------------------------------------- pairing


class PairStatus(str, Enum):
    CONFIRMED = "confirmed"  # same folder + stem, capture times agree
    NAME_ONLY = "name_only"  # same folder + stem, a capture time is missing
    TIME_MISMATCH = "time_mismatch"  # same name but different shots: do not pair


@dataclass(frozen=True, slots=True)
class PairCandidate:
    raw: ScanEntry
    jpeg: ScanEntry


def find_pair_candidates(entries: list[ScanEntry]) -> list[PairCandidate]:
    """Match RAW and JPEG files sharing folder and case-insensitive stem.

    Groups with more than one RAW or more than one JPEG (e.g. ``A.NEF`` +
    ``A.DNG``) are ambiguous and left unpaired.
    """
    groups: dict[tuple[str, str], list[ScanEntry]] = defaultdict(list)
    for entry in entries:
        groups[(str(entry.path.parent).casefold(), entry.path.stem.casefold())].append(entry)
    pairs = []
    for members in groups.values():
        raws = [e for e in members if e.format.kind is MediaKind.RAW]
        jpegs = [e for e in members if e.format.extension in PAIRABLE_RASTER_EXTENSIONS]
        if len(raws) == 1 and len(jpegs) == 1:
            pairs.append(PairCandidate(raws[0], jpegs[0]))
    return sorted(pairs, key=lambda p: p.raw.relative_path)


def classify_pair(raw_time: datetime | None, jpeg_time: datetime | None, tolerance_s: float = 2.0) -> PairStatus:
    """Confirm a name-based pair with capture times (cameras reuse file numbers)."""
    if raw_time is None or jpeg_time is None:
        return PairStatus.NAME_ONLY
    if abs((raw_time - jpeg_time).total_seconds()) <= tolerance_s:
        return PairStatus.CONFIRMED
    return PairStatus.TIME_MISMATCH
