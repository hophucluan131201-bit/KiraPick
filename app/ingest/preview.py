"""Unified image loading for grid thumbnails, analysis previews and 100% zoom.

Every result records where its pixels came from (``PreviewSource``) so later
stages — notably sharpness scoring — can refuse low-resolution sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.core.errors import CorruptImageError, ImageReadError, NoPreviewError, UnsupportedFormatError
from app.ingest import raw_decode
from app.ingest.formats import MediaKind, format_for
from app.ingest.metadata import PhotoMetadata, read_metadata
from app.ingest.validation import MIN_PREVIEW_CONSISTENCY, edge_similarity

# Largest sensors in production are ~100-150 MP; refuse beyond that instead of
# risking a decompression bomb from a crafted TIFF/PNG.
Image.MAX_IMAGE_PIXELS = 200_000_000

# An embedded preview counts as "full resolution" when it covers this fraction
# of the demosaiced size in both dimensions (Nikon 6016 vs 6040 px = 99.6%).
FULL_RES_COVERAGE = 0.95

# When the sensor data cannot be decoded, a smaller embedded preview is still
# shown (flagged by its source/native_size) unless it is too tiny to be useful.
MIN_FALLBACK_PREVIEW = 128


class PreviewSource(str, Enum):
    EMBEDDED_JPEG = "embedded_jpeg"
    EMBEDDED_BITMAP = "embedded_bitmap"
    DEMOSAIC_HALF = "demosaic_half"
    DEMOSAIC_FULL = "demosaic_full"
    RASTER = "raster"


@dataclass(frozen=True, slots=True)
class LoadedImage:
    image: Image.Image  # RGB, display orientation
    source: PreviewSource
    native_size: tuple[int, int]  # (w, h) of the decoded source before any resize
    full_size: tuple[int, int]  # (w, h) of the full-resolution photo
    metadata: PhotoMetadata | None = None

    @property
    def is_full_resolution(self) -> bool:
        return (
            self.native_size[0] >= self.full_size[0] * FULL_RES_COVERAGE
            and self.native_size[1] >= self.full_size[1] * FULL_RES_COVERAGE
        )


def _fit(image: Image.Image, max_long_side: int | None) -> Image.Image:
    if max_long_side is None or max(image.size) <= max_long_side:
        return image
    scale = max_long_side / max(image.size)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0)


def _draft_box(max_long_side: int | None) -> tuple[int, int] | None:
    # Orientation is unknown before decoding, so ask for a square box.
    return (max_long_side, max_long_side) if max_long_side else None


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("I;16", "I;16B", "I;16L", "I"):
        array = np.asarray(image, dtype=np.float32)
        peak = float(array.max()) or 1.0
        image = Image.fromarray((array * (255.0 / peak)).clip(0, 255).astype(np.uint8), "L")
    return image if image.mode == "RGB" else image.convert("RGB")


def _load_raster(path: Path, max_long_side: int | None, with_metadata: bool) -> LoadedImage:
    try:
        with Image.open(path) as image:
            full = image.size
            if image.format == "JPEG" and max_long_side:
                image.draft("RGB", _draft_box(max_long_side))
            native = image.size
            # exif_transpose reads the orientation of *this* file; for rasters it is authoritative.
            oriented = _to_rgb(ImageOps.exif_transpose(image))
    except Image.DecompressionBombError as exc:
        raise ImageReadError(path, "image too large") from exc
    except (Image.UnidentifiedImageError, SyntaxError) as exc:
        raise UnsupportedFormatError(path, "not a readable image") from exc
    except OSError as exc:
        raise CorruptImageError(path, exc.strerror or str(exc)[:80]) from exc

    if oriented.size != native:  # rotated by 90°/270°
        full, native = (full[1], full[0]), (native[1], native[0])
    metadata = read_metadata(path) if with_metadata else None
    return LoadedImage(_fit(oriented, max_long_side), PreviewSource.RASTER, native, full, metadata)


def _embedded_source(embedded: raw_decode.EmbeddedPreview) -> PreviewSource:
    return PreviewSource.EMBEDDED_JPEG if embedded.is_jpeg else PreviewSource.EMBEDDED_BITMAP


def _demosaic_checked(
    path: Path, half_size: bool, embedded: raw_decode.EmbeddedPreview | None
) -> tuple[raw_decode.RawInfo, Image.Image]:
    """Demosaic, then cross-check against the embedded preview when one exists.

    Guards against truncated files that LibRaw decodes without error into
    garbage (or into stale pixels from an earlier file).
    """
    info, image = raw_decode.demosaic(path, half_size=half_size)
    if embedded is not None and max(embedded.native_size) >= MIN_FALLBACK_PREVIEW:
        if edge_similarity(embedded.image, image) < MIN_PREVIEW_CONSISTENCY:
            raise CorruptImageError(path, "decoded sensor data does not match the embedded preview")
    return info, image


def _load_raw(path: Path, max_long_side: int | None, min_long_side: int, with_metadata: bool) -> LoadedImage:
    info, embedded = raw_decode.read_raw(path, draft_size=_draft_box(max_long_side))
    metadata = None
    if with_metadata:
        metadata = read_metadata(path, embedded_jpeg=embedded.jpeg_bytes if embedded else None)

    if embedded is not None and max(embedded.native_size) >= min_long_side:
        return LoadedImage(
            _fit(embedded.image, max_long_side), _embedded_source(embedded), embedded.native_size, info.full_size, metadata
        )

    # Embedded preview missing or too small: decode the sensor data.
    half = max(info.full_size) // 2 >= min_long_side
    try:
        _, image = _demosaic_checked(path, half, embedded)
    except CorruptImageError as exc:
        if embedded is not None and max(embedded.native_size) >= MIN_FALLBACK_PREVIEW:
            # A small preview beats nothing; source/native_size say what it is.
            return LoadedImage(
                _fit(embedded.image, max_long_side), _embedded_source(embedded), embedded.native_size, info.full_size, metadata
            )
        raise NoPreviewError(path, exc.detail) from exc
    source = PreviewSource.DEMOSAIC_HALF if half else PreviewSource.DEMOSAIC_FULL
    return LoadedImage(_fit(image, max_long_side), source, image.size, info.full_size, metadata)


def load_image(
    path: Path,
    *,
    max_long_side: int | None = None,
    min_long_side: int = 0,
    with_metadata: bool = False,
) -> LoadedImage:
    """Load a display-oriented RGB image, preferring the fastest adequate source.

    For RAW files the embedded preview is used when its long side is at least
    ``min_long_side``; otherwise the sensor data is demosaiced (half size when
    that is still large enough). The result is downscaled to ``max_long_side``.

    Typical calls: grid thumbnail ``(max=320, min=320)``; analysis preview
    ``(max=1600, min=1600)``.
    """
    info = format_for(path)
    if info is None:
        raise UnsupportedFormatError(path, f"extension {path.suffix or '(none)'} not supported")
    if info.kind is MediaKind.RASTER:
        return _load_raster(path, max_long_side, with_metadata)
    return _load_raw(path, max_long_side, min_long_side, with_metadata)


def load_full_resolution(path: Path, *, allow_embedded: bool = True) -> LoadedImage:
    """Full-resolution pixels for 100% zoom and focus measurement.

    A full-size embedded JPEG (camera-rendered, includes in-camera sharpening)
    is accepted when ``allow_embedded``; otherwise, or when the embedded preview
    is smaller than the sensor image, the RAW is fully demosaiced (~2 s for a
    24 MP NEF). ``LoadedImage.source`` records which path was taken.
    """
    info = format_for(path)
    if info is None:
        raise UnsupportedFormatError(path, f"extension {path.suffix or '(none)'} not supported")
    if info.kind is MediaKind.RASTER:
        return _load_raster(path, None, False)
    raw_info, embedded = raw_decode.read_raw(path, draft_size=None if allow_embedded else (512, 512))
    if allow_embedded and embedded is not None:
        candidate = LoadedImage(embedded.image, _embedded_source(embedded), embedded.native_size, raw_info.full_size)
        if candidate.is_full_resolution:
            return candidate
    raw_info, image = _demosaic_checked(path, False, embedded)
    return LoadedImage(image, PreviewSource.DEMOSAIC_FULL, image.size, raw_info.full_size)


def header_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of the full-resolution photo read from the file's header only (no pixel decode): the JPEG /
    TIFF / PNG header for rasters, LibRaw's size fields for RAW files. None when it cannot be read."""
    info = format_for(path)
    if info is None:
        return None
    try:
        if info.kind is MediaKind.RASTER:
            with Image.open(path) as im:  # lazy: only the header is parsed
                return im.size
        with raw_decode.open_raw(path) as raw:  # opens and identifies; the sensor data is not unpacked
            sizes = raw.sizes
            return (int(sizes.width), int(sizes.height)) if sizes.width and sizes.height else None
    except Exception:  # noqa: BLE001 - unreadable header: the size is checked when the frame arrives
        return None
