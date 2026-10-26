"""Camera metadata extraction, normalised across vendors.

Sources, in order:
1. ExifRead on the file itself (JPEG/TIFF and TIFF-based RAW: NEF, CR2, ARW,
   ORF, RW2, PEF, DNG, SRW, RWL).
2. CR3: the TIFF blobs in the ISO-BMFF ``CMT1``/``CMT2`` boxes (ExifRead does
   not parse CR3 containers).
3. EXIF of the embedded preview JPEG (fills gaps, e.g. Fujifilm RAF).

Privacy: GPS, serial numbers, owner/artist fields and maker notes are never
extracted. Nothing here is logged.
"""

from __future__ import annotations

import io
import logging
import struct
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

import exifread
from PIL import Image

from app.core.errors import ImageReadError
from app.ingest import raw_decode
from app.ingest.formats import is_raw

logging.getLogger("exifread").setLevel(logging.CRITICAL)  # it logs per-file noise

# EXIF tag ids used below.
MAKE, MODEL, ORIENTATION = 0x010F, 0x0110, 0x0112
EXPOSURE_TIME, F_NUMBER, ISO = 0x829A, 0x829D, 0x8827
DATETIME_ORIGINAL, SUBSEC_ORIGINAL = 0x9003, 0x9291
FOCAL_LENGTH, COLOR_SPACE, LENS_MODEL = 0x920A, 0xA001, 0xA434
EXIF_IFD_POINTER = 0x8769

# ExifRead key prefixes we accept (IFD0 is "Image", the Exif sub-IFD "EXIF").
_ACCEPTED_PREFIXES = ("Image", "EXIF")

_CR3_CANON_UUID = bytes.fromhex("85c0b687820f11e08111f4ce462b6a48")
_MAX_CMT_BOX = 4 * 1024 * 1024


@dataclass(slots=True)
class PhotoMetadata:
    make: str | None = None
    model: str | None = None
    lens: str | None = None
    datetime_original: str | None = None  # ISO 8601, camera local time, no tz
    subsec: str | None = None
    exposure_time_s: float | None = None
    f_number: float | None = None
    iso: int | None = None
    focal_length_mm: float | None = None
    orientation: int | None = None  # EXIF 1..8
    color_space: str | None = None  # "sRGB" | "uncalibrated" (often AdobeRGB) | None
    sources: tuple[str, ...] = ()

    def is_complete(self) -> bool:
        return self.make is not None and self.model is not None and self.datetime_original is not None

    def merge_missing(self, other: PhotoMetadata) -> None:
        """Fill fields that are still None from ``other``."""
        took = False
        for f in fields(self):
            if f.name == "sources":
                continue
            if getattr(self, f.name) is None and getattr(other, f.name) is not None:
                setattr(self, f.name, getattr(other, f.name))
                took = True
        if took:
            self.sources = self.sources + other.sources

    def capture_time(self) -> datetime | None:
        if self.datetime_original is None:
            return None
        return datetime.fromisoformat(self.datetime_original)

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = list(self.sources)
        return d


# ---------------------------------------------------------------- normalising


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _as_float(value: Any) -> float | None:
    value = _first(value)
    if value is None:
        return None
    try:
        result = float(value)  # Fraction, IFDRational, exifread Ratio, int
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return result if result == result and result >= 0 else None  # drop NaN/neg


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _as_text(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    if isinstance(value, (list, tuple)):
        value = "".join(str(v) for v in value) if all(isinstance(v, str) for v in value) else _first(value)
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    return text or None


def _as_datetime(value: Any) -> str | None:
    text = _as_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None  # e.g. "0000:00:00 00:00:00" on cameras with an unset clock


def normalise(tags: dict[int, Any], source: str) -> PhotoMetadata:
    """Build PhotoMetadata from a ``{exif_tag_id: raw value}`` mapping."""
    orientation = _as_int(tags.get(ORIENTATION))
    color = _as_int(tags.get(COLOR_SPACE))
    return PhotoMetadata(
        make=_as_text(tags.get(MAKE)),
        model=_as_text(tags.get(MODEL)),
        lens=_as_text(tags.get(LENS_MODEL)),
        datetime_original=_as_datetime(tags.get(DATETIME_ORIGINAL)),
        subsec=_as_text(tags.get(SUBSEC_ORIGINAL)),
        exposure_time_s=_as_float(tags.get(EXPOSURE_TIME)),
        f_number=_as_float(tags.get(F_NUMBER)),
        iso=_as_int(tags.get(ISO)),
        focal_length_mm=_as_float(tags.get(FOCAL_LENGTH)),
        orientation=orientation if orientation in range(1, 9) else None,
        color_space={1: "sRGB", 0xFFFF: "uncalibrated"}.get(color) if color is not None else None,
        sources=(source,) if tags else (),
    )


# ------------------------------------------------------------------- readers

_WANTED = {MAKE, MODEL, ORIENTATION, EXPOSURE_TIME, F_NUMBER, ISO, DATETIME_ORIGINAL,
           SUBSEC_ORIGINAL, FOCAL_LENGTH, COLOR_SPACE, LENS_MODEL}


def _exifread_tags(fh: BinaryIO) -> dict[int, Any]:
    try:
        raw_tags = exifread.process_file(fh, details=False)
    except Exception:  # noqa: BLE001 - ExifRead raises arbitrary errors on odd files
        return {}
    tags: dict[int, Any] = {}
    for key, tag in raw_tags.items():
        prefix = key.split(" ", 1)[0]
        tag_id = getattr(tag, "tag", None)
        if prefix not in _ACCEPTED_PREFIXES or tag_id not in _WANTED:
            continue
        # IFD0 ("Image") wins over duplicates seen later.
        tags.setdefault(tag_id, tag.values)
    return tags


def _iter_boxes(fh: BinaryIO, start: int, end: int) -> Any:
    """Yield (type, payload_offset, payload_end, uuid_or_None) for ISO-BMFF boxes."""
    pos = start
    while pos + 8 <= end:
        fh.seek(pos)
        header = fh.read(8)
        if len(header) < 8:
            return
        size, box_type = struct.unpack(">I4s", header)
        header_len = 8
        if size == 1:
            ext = fh.read(8)
            if len(ext) < 8:
                return
            size = struct.unpack(">Q", ext)[0]
            header_len = 16
        elif size == 0:
            size = end - pos
        if size < header_len or pos + size > end:
            return  # malformed: stop rather than read garbage
        uuid = None
        if box_type == b"uuid":
            uuid = fh.read(16)
            header_len += 16
        yield box_type, pos + header_len, pos + size, uuid
        pos += size


def _cr3_tags(fh: BinaryIO, file_size: int) -> dict[int, Any]:
    tags: dict[int, Any] = {}
    for box_type, begin, end, _ in _iter_boxes(fh, 0, file_size):
        if box_type != b"moov":
            continue
        for inner_type, ibegin, iend, uuid in _iter_boxes(fh, begin, end):
            if inner_type != b"uuid" or uuid != _CR3_CANON_UUID:
                continue
            for cmt_type, cbegin, cend, _ in _iter_boxes(fh, ibegin, iend):
                # CMT1 = IFD0, CMT2 = Exif IFD; each is a standalone TIFF.
                if cmt_type in (b"CMT1", b"CMT2") and cend - cbegin <= _MAX_CMT_BOX:
                    fh.seek(cbegin)
                    blob = fh.read(cend - cbegin)
                    for tag_id, value in _exifread_tags(io.BytesIO(blob)).items():
                        tags.setdefault(tag_id, value)
        break
    return tags


def _pillow_jpeg_tags(jpeg: bytes) -> dict[int, Any]:
    try:
        with Image.open(io.BytesIO(jpeg)) as image:
            exif = image.getexif()
            tags: dict[int, Any] = {k: v for k, v in exif.items() if k in _WANTED}
            for k, v in exif.get_ifd(EXIF_IFD_POINTER).items():
                if k in _WANTED:
                    tags.setdefault(k, v)
            return tags
    except (OSError, ValueError, SyntaxError):
        return {}


def read_metadata(path: Path, *, embedded_jpeg: bytes | None = None) -> PhotoMetadata:
    """Read normalised metadata. Never raises for unreadable metadata.

    Pass ``embedded_jpeg`` when the caller already extracted the RAW preview;
    otherwise it is extracted here only if the primary sources are incomplete.
    """
    meta = PhotoMetadata()
    try:
        with open(path, "rb") as fh:
            meta = normalise(_exifread_tags(fh), "exif")
            if path.suffix.lower() == ".cr3" and not meta.is_complete():
                fh.seek(0, io.SEEK_END)
                meta.merge_missing(normalise(_cr3_tags(fh, fh.tell()), "cr3_cmt"))
    except OSError:
        return meta
    if embedded_jpeg is None and not meta.is_complete() and is_raw(path):
        try:
            embedded_jpeg = raw_decode.embedded_jpeg_bytes(path)
        except ImageReadError:
            embedded_jpeg = None
    if embedded_jpeg is not None and not meta.is_complete():
        meta.merge_missing(normalise(_pillow_jpeg_tags(embedded_jpeg), "embedded_jpeg"))
    return meta
