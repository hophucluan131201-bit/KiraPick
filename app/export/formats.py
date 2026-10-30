"""The export's ② Định dạng option and the kind of each file it may copy (Part 3 spec §3.2)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path, PurePath
from typing import Literal

from app.ingest.formats import PAIRABLE_RASTER_EXTENSIONS, FORMATS, MediaKind

FileKind = Literal["raw", "jpeg", "other"]


class ExportFormat(str, Enum):
    RAW_JPEG = "raw_jpeg"  # every file of the photo (the export before Part 3)
    RAW = "raw"
    JPEG = "jpeg"


def file_kind(path: Path | str) -> FileKind | None:
    """raw / jpeg (.jpg, .jpeg) / other (TIFF, PNG); None for a file KiraPick does not import."""
    suffix = PurePath(path).suffix.lower()
    info = FORMATS.get(suffix)
    if info is None:
        return None
    if info.kind is MediaKind.RAW:
        return "raw"
    return "jpeg" if suffix in PAIRABLE_RASTER_EXTENSIONS else "other"


def wanted_kinds(fmt: ExportFormat, *, external: bool) -> frozenset[str]:
    """Kinds of file the format copies. Other rasters come only from the imported source (spec D10)."""
    if fmt is ExportFormat.RAW:
        return frozenset({"raw"})
    if fmt is ExportFormat.JPEG:
        return frozenset({"jpeg"})
    return frozenset({"raw", "jpeg"}) if external else frozenset({"raw", "jpeg", "other"})
