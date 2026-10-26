"""Registry of importable file formats and their verification status.

``SupportLevel.VERIFIED`` means the format was decoded end-to-end (embedded
preview, demosaic, metadata, orientation) against real camera files in the
test suite. ``UNVERIFIED`` formats are passed to LibRaw anyway, but the UI must
show them as untested; a failure there is reported, never hidden.
See docs/raw-support-matrix.md for the evidence behind each entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MediaKind(str, Enum):
    RAW = "raw"
    RASTER = "raster"


class SupportLevel(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class FormatInfo:
    extension: str  # lower case, with leading dot
    kind: MediaKind
    vendor: str
    level: SupportLevel


def _raw(ext: str, vendor: str, verified: bool) -> FormatInfo:
    level = SupportLevel.VERIFIED if verified else SupportLevel.UNVERIFIED
    return FormatInfo(ext, MediaKind.RAW, vendor, level)


_RAW_FORMATS = [
    # Verified against real files (see docs/raw-support-matrix.md).
    _raw(".nef", "Nikon", True),
    _raw(".cr2", "Canon", True),
    _raw(".cr3", "Canon", True),
    _raw(".arw", "Sony", True),
    _raw(".raf", "Fujifilm", True),
    _raw(".orf", "Olympus / OM System", True),
    _raw(".rw2", "Panasonic", True),
    _raw(".pef", "Pentax / Ricoh", True),
    _raw(".dng", "Adobe DNG (Leica, Pentax, phones...)", True),
    _raw(".srw", "Samsung", True),
    _raw(".rwl", "Leica", True),
    # Known to LibRaw but not yet verified with a real full-size sample.
    _raw(".nrw", "Nikon (Coolpix)", False),
    _raw(".crw", "Canon (legacy)", False),
    _raw(".sr2", "Sony (legacy)", False),
    _raw(".srf", "Sony (legacy)", False),
    _raw(".3fr", "Hasselblad", False),
    _raw(".fff", "Hasselblad / Imacon", False),
    _raw(".iiq", "Phase One", False),
    _raw(".kdc", "Kodak", False),
    _raw(".dcr", "Kodak", False),
    _raw(".mef", "Mamiya", False),
    _raw(".mos", "Leaf", False),
    _raw(".mrw", "Minolta", False),
    _raw(".erf", "Epson", False),
    _raw(".x3f", "Sigma", False),
    _raw(".raw", "Panasonic / Leica (legacy)", False),
    _raw(".gpr", "GoPro", False),
]

_RASTER_FORMATS = [
    FormatInfo(ext, MediaKind.RASTER, "", SupportLevel.VERIFIED)
    for ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff")
]

FORMATS: dict[str, FormatInfo] = {f.extension: f for f in _RAW_FORMATS + _RASTER_FORMATS}

# JPEG-family extensions that can form a RAW+JPEG pair.
PAIRABLE_RASTER_EXTENSIONS = frozenset({".jpg", ".jpeg"})


def format_for(path: Path) -> FormatInfo | None:
    """Return the format registered for ``path``'s extension, or None."""
    return FORMATS.get(path.suffix.lower())


def is_raw(path: Path) -> bool:
    info = format_for(path)
    return info is not None and info.kind is MediaKind.RAW
