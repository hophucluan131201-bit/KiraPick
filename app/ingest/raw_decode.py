"""Thin, read-only wrapper over rawpy/LibRaw.

Key facts established on real samples (docs/raw-support-matrix.md):
- Embedded previews are stored in sensor orientation; LibRaw's ``sizes.flip``
  must be applied to them. ``postprocess()`` already applies the flip itself.
- Embedded preview size varies by vendor: full-size on Nikon/Canon/Pentax/
  Samsung, 1616x1080 on most Sony bodies, 720x480 on some DNGs.
"""

from __future__ import annotations

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


def _source_for_libraw(path: Path) -> str | io.BufferedReader:
    # LibRaw takes a narrow char* path; on Windows a non-ASCII path may not be
    # representable in the ANSI code page, so hand rawpy a file object instead
    # (it then reads the file into memory). Elsewhere, paths are fine and let
    # LibRaw read only the parts it needs.
    if os.name == "nt" and not str(path).isascii():
        return open(path, "rb")  # noqa: SIM115 - closed by open_raw
    return str(path)


@contextmanager
def open_raw(path: Path) -> Iterator[rawpy.RawPy]:
    """Open a RAW file read-only, translating LibRaw errors to KiraPickErrors."""
    source = None
    try:
        source = _source_for_libraw(path)
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
    finally:
        if source is not None and not isinstance(source, str):
            source.close()


def _info_from(raw: rawpy.RawPy) -> RawInfo:
    sizes = raw.sizes
    orientation = flip_to_exif_orientation(sizes.flip)
    return RawInfo(
        full_size=oriented_size(sizes.width, sizes.height, orientation),
        raw_size=(sizes.raw_width, sizes.raw_height),
        orientation=orientation,
    )


def _embedded_from(raw: rawpy.RawPy, orientation: int, draft_size: tuple[int, int] | None) -> EmbeddedPreview | None:
    try:
        thumb = raw.extract_thumb()
    except _NO_THUMB_ERRORS:
        return None
    except rawpy.LibRawError as exc:
        log.debug("embedded preview unreadable: %s", type(exc).__name__)
        return None

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


def read_raw(path: Path, *, draft_size: tuple[int, int] | None = None) -> tuple[RawInfo, EmbeddedPreview | None]:
    """Read geometry and the embedded preview (if any) in one LibRaw open.

    ``draft_size`` lets the JPEG decoder skip detail beyond the requested size
    (Pillow may return up to 2x larger than requested; callers resize).
    """
    with open_raw(path) as raw:
        info = _info_from(raw)
        return info, _embedded_from(raw, info.orientation, draft_size)


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
