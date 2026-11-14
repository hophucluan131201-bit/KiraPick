"""Thin, read-only wrapper over rawpy/LibRaw.

Key facts established on real samples (docs/raw-support-matrix.md):
- Embedded previews are stored in sensor orientation; LibRaw's ``sizes.flip``
  must be applied to them. ``postprocess()`` already applies the flip itself.
- Embedded preview size varies by vendor: full-size on Nikon/Canon/Pentax/
  Samsung, 1616x1080 on most Sony bodies, 720x480 on some DNGs.
"""

from __future__ import annotations

import ctypes
import io
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image

from app.core.errors import CorruptImageError, ImageReadError, UnsupportedFormatError

log = logging.getLogger(__name__)

# LibRaw ``flip`` -> EXIF orientation. LibRaw only produces these four values.
_FLIP_TO_EXIF = {0: 1, 3: 3, 5: 8, 6: 6}

_CORRUPT_ERRORS: tuple[type[Exception], ...] = (
    rawpy.LibRawIOError,
    rawpy.LibRawDataError,
    rawpy.LibRawRequestForNonexistentImageError,
    rawpy.LibRawTooBigError,
)
_NO_THUMB_ERRORS: tuple[type[Exception], ...] = (
    rawpy.LibRawNoThumbnailError,
    rawpy.LibRawUnsupportedThumbnailError,
)


@dataclass(frozen=True, slots=True)
class EmbeddedPreview:
    image: Image.Image  # RGB, orientation already applied (may be draft-reduced)
    native_size: tuple[int, int]  # oriented (w, h) of the stored preview before any draft reduction
    is_jpeg: bool
    jpeg_bytes: bytes | None  # kept so metadata can fall back to the preview's EXIF


@dataclass(frozen=True, slots=True)
class RawInfo:
    full_size: tuple[int, int]  # oriented (width, height) of the demosaiced image
    raw_size: tuple[int, int]  # sensor (width, height) incl. masked borders
    orientation: int  # EXIF orientation 1..8 derived from LibRaw flip


def flip_to_exif_orientation(flip: int) -> int:
    return _FLIP_TO_EXIF.get(flip, 1)


_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def apply_orientation(image: Image.Image, orientation: int) -> Image.Image:
    """Apply an EXIF orientation value (1..8) to an un-rotated image."""
    method = _TRANSPOSE.get(orientation)
    return image.transpose(method) if method is not None else image


def oriented_size(width: int, height: int, orientation: int) -> tuple[int, int]:
    return (height, width) if orientation in (5, 6, 7, 8) else (width, height)


def needs_file_object(path: Path) -> bool:
    """LibRaw takes a narrow char* path; on Windows a non-ASCII path (a folder named "Ảnh buổi chụp") may not be
    representable in the ANSI code page, so rawpy must be handed the file's bytes instead of the path. Elsewhere
    paths are fine and let LibRaw read only the parts it needs."""
    return os.name == "nt" and not str(path).isascii()


def _source_for_libraw(path: Path) -> str | io.BufferedReader:
    if needs_file_object(path):
        return open(path, "rb")  # noqa: SIM115 - closed by open_raw; rawpy reads the whole file into memory
    return str(path)


@contextmanager
def open_raw(path: Path) -> Iterator[rawpy.RawPy]:
    """Open a RAW file read-only, translating LibRaw errors to KiraPickErrors."""
    source = None
    try:
        source = _source_for_libraw(path)
        with _libraw(path, source) as raw:
            yield raw
    finally:
        if source is not None and not isinstance(source, str):
            source.close()


@contextmanager
def _libraw(path: Path, source: object) -> Iterator[rawpy.RawPy]:
    try:
        with rawpy.imread(source) as raw:
            yield raw
    except rawpy.LibRawFileUnsupportedError as exc:
        raise UnsupportedFormatError(path, "not recognised by LibRaw: damaged file or unsupported camera") from exc
    except _CORRUPT_ERRORS as exc:
        raise CorruptImageError(path, type(exc).__name__) from exc
    except rawpy.LibRawError as exc:
        raise ImageReadError(path, type(exc).__name__) from exc
    except OSError as exc:
        raise ImageReadError(path, exc.strerror or type(exc).__name__) from exc


def _info_from(raw: rawpy.RawPy) -> RawInfo:
    sizes = raw.sizes
    orientation = flip_to_exif_orientation(sizes.flip)
    return RawInfo(
        full_size=oriented_size(sizes.width, sizes.height, orientation),
        raw_size=(sizes.raw_width, sizes.raw_height),
        orientation=orientation,
    )


def _thumb(raw: rawpy.RawPy) -> rawpy.Thumbnail | None:
    try:
        return raw.extract_thumb()
    except _NO_THUMB_ERRORS:
        return None
    except rawpy.LibRawError as exc:
        log.debug("embedded preview unreadable: %s", type(exc).__name__)
        return None


def _embedded_from(raw: rawpy.RawPy, orientation: int, draft_size: tuple[int, int] | None) -> EmbeddedPreview | None:
    thumb = _thumb(raw)
    return None if thumb is None else _preview_from(thumb, orientation, draft_size)


def _preview_from(thumb: rawpy.Thumbnail, orientation: int, draft_size: tuple[int, int] | None) -> EmbeddedPreview | None:
    if thumb.format == rawpy.ThumbFormat.JPEG:
        try:
            image = Image.open(io.BytesIO(thumb.data))
            stored_size = image.size
            if draft_size is not None:
                image.draft("RGB", draft_size)  # fast DCT downscale while decoding
            image = image.convert("RGB")
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            log.debug("embedded JPEG undecodable: %s", type(exc).__name__)
            return None
        jpeg_bytes: bytes | None = bytes(thumb.data)
    else:
        array = np.asarray(thumb.data)
        if array.ndim != 3 or array.shape[2] != 3:
            return None
        image = Image.fromarray(array.astype(np.uint8, copy=False), "RGB")
        stored_size = image.size
        jpeg_bytes = None

    return EmbeddedPreview(
        apply_orientation(image, orientation),
        oriented_size(*stored_size, orientation),
        jpeg_bytes is not None,
        jpeg_bytes,
    )


def embedded_jpeg_bytes(path: Path) -> bytes | None:
    """Raw bytes of the embedded JPEG preview, without decoding it."""
    with open_raw(path) as raw:
        try:
            thumb = raw.extract_thumb()
        except rawpy.LibRawError:
            return None
        return bytes(thumb.data) if thumb.format == rawpy.ThumbFormat.JPEG else None


def read_raw(path: Path, *, draft_size: tuple[int, int] | None = None,
             from_start_min: int | None = None) -> tuple[RawInfo, EmbeddedPreview | None]:
    """Read geometry and the embedded preview (if any) in one LibRaw open.

    ``draft_size`` lets the JPEG decoder skip detail beyond the requested size
    (Pillow may return up to 2x larger than requested; callers resize).

    ``from_start_min`` (import thumbnails): where LibRaw cannot be given the path, read only the start of the file
    when it holds an embedded JPEG with a long side of at least this many pixels (it may then be a smaller preview
    than the one opening the path picks, as on Pentax; the geometry is the file's own).
    """
    if from_start_min is not None and needs_file_object(path):
        return _read_raw_from_start(path, draft_size, from_start_min)
    with open_raw(path) as raw:
        info = _info_from(raw)
        return info, _embedded_from(raw, info.orientation, draft_size)


# How much of the file is read first when LibRaw cannot be given the path (see needs_file_object). Measured on the
# RAW samples of tests/fixtures/raw_samples.json (9 makers): the header and the embedded JPEG lie within the first
# 4 MB for most bodies, within 8 MB for every NEF tested; Pentax K-1 keeps its large preview at the end (whole file).
PREFIX_STEPS = (4 << 20, 8 << 20, 16 << 20)


def _read_raw_from_start(path: Path, draft_size: tuple[int, int] | None,
                         min_long_side: int) -> tuple[RawInfo, EmbeddedPreview | None]:
    """Geometry and embedded preview from the start of the file only (import speed on external drives: a NEF is
    ~26 MB, its header and preview ~2-4 MB). LibRaw gets the bytes read so far followed by zeros up to the real file
    size, so it lays the file out as the real one. The result is accepted only when it does not depend on the part
    not read (_same_with_any_rest) and the preview is large enough; otherwise more is read, up to the whole file,
    which gives exactly what opening the path would."""
    try:
        size = path.stat().st_size
        fh = open(path, "rb")  # noqa: SIM115 - closed below
    except OSError as exc:
        raise ImageReadError(path, exc.strerror or type(exc).__name__) from exc
    data = bytearray()
    with fh:
        for step in (*PREFIX_STEPS, size):
            limit = min(step, size)
            if limit <= len(data) and limit < size:
                continue
            try:
                data += fh.read(limit - len(data))
            except OSError as exc:
                raise ImageReadError(path, exc.strerror or type(exc).__name__) from exc
            if len(data) >= size:
                with _libraw(path, io.BytesIO(bytes(data))) as raw:
                    info = _info_from(raw)
                    return info, _embedded_from(raw, info.orientation, draft_size)
            found = _same_with_any_rest(path, bytes(data), size)
            if found is not None:
                info, thumb = found
                preview = _preview_from(thumb, info.orientation, draft_size)
                if preview is not None and max(preview.native_size) >= min_long_side:
                    return info, preview
    raise ImageReadError(path, "file changed while reading")  # pragma: no cover - size shrank under us


class _Reader:
    """What rawpy.imread needs of a file object: ``read()`` giving the whole buffer (here without a copy)."""

    def __init__(self, buffer: bytearray) -> None:
        self._buffer = buffer

    def read(self) -> bytearray:
        return self._buffer


def _same_with_any_rest(path: Path, start: bytes, size: int) -> tuple[RawInfo, rawpy.Thumbnail] | None:
    """Open ``start`` followed by 0x00 bytes, then by 0xFF bytes, up to the real size. Geometry and JPEG preview bytes
    that come out identical both times do not depend on the part not read: they are the file's own (a byte taken
    from that part would differ). None otherwise (read more)."""
    results = []
    buffer = bytearray(size)  # zeros
    buffer[: len(start)] = start
    for fill in (0x00, 0xFF):
        if fill:
            rest = (ctypes.c_char * size).from_buffer(buffer)
            ctypes.memset(ctypes.addressof(rest) + len(start), fill, size - len(start))
            del rest
        try:
            with _libraw(path, _Reader(buffer)) as raw:  # LibRaw reads the buffer in place: no copy
                info, thumb = _info_from(raw), _thumb(raw)
                if thumb is None or thumb.format != rawpy.ThumbFormat.JPEG:
                    return None
                results.append((info, thumb, bytes(thumb.data)))
        except ImageReadError:
            return None
    (info_a, thumb_a, bytes_a), (info_b, _thumb_b, bytes_b) = results
    return (info_a, thumb_a) if info_a == info_b and bytes_a == bytes_b else None


# Smallest file size per sensor pixel for a file that can hold sensor data.
# Measured: real files 0.47 (Canon C-RAW) to 2.7 B/px; files with stripped
# sensor data <= 0.006 B/px. See docs/raw-support-matrix.md.
MIN_BYTES_PER_SENSOR_PIXEL = 0.05


def _sensor_data_problem(path: Path, raw: rawpy.RawPy) -> str | None:
    """Return why the sensor data cannot be trusted, or None.

    LibRaw does not always fail on files whose sensor data is missing: it may
    "decode" an uninitialised buffer whose contents depend on previously
    opened files. Checks are deterministic first (file size), then content.
    """
    pixels = raw.sizes.raw_width * raw.sizes.raw_height
    if pixels <= 0:
        return "no sensor area"
    if path.stat().st_size / pixels < MIN_BYTES_PER_SENSOR_PIXEL:
        return "sensor data missing (file too small)"
    # Real exposures, even lens-cap frames, are non-zero almost everywhere
    # because of the black level and read noise.
    sample = raw.raw_image_visible[::8, ::8]
    if sample.size == 0 or np.count_nonzero(sample) / sample.size < 0.5 or len(np.unique(sample[::4, ::4])) < 8:
        return "sensor data missing (blank)"
    return None


def demosaic(path: Path, *, half_size: bool) -> tuple[RawInfo, Image.Image]:
    """Decode the sensor data to an oriented 8-bit sRGB image.

    Uses the camera white balance; LibRaw applies the orientation flip.
    ``half_size`` skips interpolation (≈5x faster) and halves each dimension.
    """
    with open_raw(path) as raw:
        info = _info_from(raw)
        try:
            problem = _sensor_data_problem(path, raw)
            if problem is not None:
                raise CorruptImageError(path, problem)
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=half_size,
                output_bps=8,
                output_color=rawpy.ColorSpace.sRGB,
            )
        except rawpy.LibRawError as exc:
            # The header parsed but the sensor data did not decode.
            raise CorruptImageError(path, type(exc).__name__) from exc
    return info, Image.fromarray(rgb, "RGB")
