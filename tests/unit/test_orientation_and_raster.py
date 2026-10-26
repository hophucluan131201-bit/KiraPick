from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageOps

from app.core.errors import ImageReadError, UnsupportedFormatError
from app.ingest.preview import PreviewSource, load_full_resolution, load_image
from app.ingest.raw_decode import apply_orientation, flip_to_exif_orientation, oriented_size


def _asymmetric(width: int = 60, height: int = 40) -> Image.Image:
    """Image whose every flip/rotation is distinguishable."""
    array = np.zeros((height, width, 3), np.uint8)
    array[:10, :20] = (255, 0, 0)  # top-left red block
    array[-5:, -30:] = (0, 0, 255)  # bottom-right blue bar
    return Image.fromarray(array, "RGB")


def _with_orientation(image: Image.Image, orientation: int) -> Image.Image:
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = orientation
    image.save(buf, "PNG", exif=exif.tobytes())
    return Image.open(io.BytesIO(buf.getvalue()))


@pytest.mark.parametrize("orientation", range(1, 9))
def test_apply_orientation_matches_pillow_exif_transpose(orientation: int) -> None:
    base = _asymmetric()
    expected = ImageOps.exif_transpose(_with_orientation(base, orientation))
    actual = apply_orientation(base, orientation)
    assert actual.size == expected.size
    assert np.array_equal(np.asarray(actual), np.asarray(expected.convert("RGB")))


def test_libraw_flip_mapping() -> None:
    assert [flip_to_exif_orientation(f) for f in (0, 3, 5, 6, 99)] == [1, 3, 8, 6, 1]
    assert oriented_size(6000, 4000, 8) == (4000, 6000)
    assert oriented_size(6000, 4000, 3) == (6000, 4000)


def _write_jpeg(path: Path, size: tuple[int, int], orientation: int | None = None) -> None:
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    _asymmetric(*size).save(path, "JPEG", quality=90, exif=exif.tobytes())


def test_raster_jpeg_respects_exif_orientation_and_downscales(tmp_path: Path) -> None:
    path = tmp_path / "portrait.jpg"
    _write_jpeg(path, (1200, 800), orientation=6)  # stored landscape, displayed portrait
    loaded = load_image(path, max_long_side=300, with_metadata=True)
    assert loaded.source is PreviewSource.RASTER
    assert loaded.full_size == (800, 1200)
    assert loaded.image.size == (200, 300)
    assert loaded.metadata is not None and loaded.metadata.orientation == 6


def test_raster_full_resolution(tmp_path: Path) -> None:
    path = tmp_path / "a.jpeg"
    _write_jpeg(path, (640, 480))
    loaded = load_full_resolution(path)
    assert loaded.image.size == (640, 480) and loaded.is_full_resolution


def test_16bit_png_is_converted(tmp_path: Path) -> None:
    path = tmp_path / "deep.png"
    Image.fromarray(np.arange(64 * 64, dtype=np.uint16).reshape(64, 64) * 16).save(path)
    loaded = load_image(path)
    assert loaded.image.mode == "RGB" and np.asarray(loaded.image).max() == 255


def test_unknown_extension_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("x")
    with pytest.raises(UnsupportedFormatError):
        load_image(path)


@pytest.mark.parametrize("name", ["fake.jpg", "fake.png", "fake.nef", "fake.cr3", "empty.arw"])
def test_garbage_files_raise_typed_errors(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"" if name.startswith("empty") else b"not an image at all" * 100)
    with pytest.raises(ImageReadError):
        load_image(path, max_long_side=320, min_long_side=320)
