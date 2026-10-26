from __future__ import annotations

import io
import struct
from fractions import Fraction
from pathlib import Path

from PIL import Image

from app.ingest import metadata as md
from app.ingest.metadata import PhotoMetadata, normalise, read_metadata


def test_normalise_cleans_values() -> None:
    meta = normalise(
        {
            md.MAKE: "OLYMPUS IMAGING CORP.  ",
            md.MODEL: ["E-M10\x00"],
            md.DATETIME_ORIGINAL: "2015:07:23 14:16:32",
            md.EXPOSURE_TIME: [Fraction(1, 250)],
            md.F_NUMBER: Fraction(71, 10),
            md.ISO: [200],
            md.ORIENTATION: [8],
            md.COLOR_SPACE: 0xFFFF,
        },
        "exif",
    )
    assert meta.make == "OLYMPUS IMAGING CORP." and meta.model == "E-M10"
    assert meta.datetime_original == "2015-07-23T14:16:32"
    assert meta.exposure_time_s == 0.004 and meta.f_number == 7.1 and meta.iso == 200
    assert meta.orientation == 8 and meta.color_space == "uncalibrated"
    assert meta.sources == ("exif",)


def test_unset_camera_clock_is_missing_not_invented() -> None:
    meta = normalise({md.DATETIME_ORIGINAL: "0000:00:00 00:00:00", md.ORIENTATION: 0}, "exif")
    assert meta.datetime_original is None and meta.orientation is None
    assert normalise({}, "exif").sources == ()


def test_bad_numbers_are_dropped() -> None:
    meta = normalise({md.F_NUMBER: Fraction(1, 1) * float("nan"), md.ISO: "abc", md.FOCAL_LENGTH: -5}, "x")
    assert meta.f_number is None and meta.iso is None and meta.focal_length_mm is None


def test_merge_missing_keeps_primary_values() -> None:
    primary = PhotoMetadata(make="Canon", sources=("exif",))
    primary.merge_missing(PhotoMetadata(make="Other", model="EOS R3", sources=("cr3_cmt",)))
    assert primary.make == "Canon" and primary.model == "EOS R3"
    assert primary.sources == ("exif", "cr3_cmt")


def _jpeg_with_exif(path: Path, with_gps: bool) -> None:
    exif = Image.Exif()
    exif[md.MAKE] = "NIKON CORPORATION"
    exif[md.MODEL] = "NIKON Z 5"
    exif.get_ifd(md.EXIF_IFD_POINTER)[md.DATETIME_ORIGINAL] = "2026:10:25 16:48:19"
    if with_gps:
        exif.get_ifd(0x8825)[2] = (10.0, 46.0, 30.0)  # GPSLatitude
    Image.new("RGB", (32, 32)).save(path, "JPEG", exif=exif.tobytes())


def test_read_metadata_from_jpeg_never_exposes_gps(tmp_path: Path) -> None:
    path = tmp_path / "ảnh Đà Nẵng.jpg"  # Unicode path
    _jpeg_with_exif(path, with_gps=True)
    meta = read_metadata(path)
    assert meta.is_complete() and meta.model == "NIKON Z 5"
    assert not any("gps" in key.lower() for key in meta.to_json_dict())


def test_read_metadata_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_metadata(tmp_path / "gone.jpg") == PhotoMetadata()


def _box(box_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), box_type) + payload


def test_cr3_parser_reads_cmt_boxes_and_survives_malformed_input() -> None:
    tiff = io.BytesIO()
    exif = Image.Exif()
    exif[md.MAKE] = "Canon"
    exif[md.MODEL] = "Canon EOS R8"
    blob = exif.tobytes()
    assert blob.startswith(b"Exif\x00\x00")
    tiff.write(blob[6:])  # bare TIFF ("II*..."), exactly like a real CMT1 box
    canon = _md_uuid(_box(b"CMT1", tiff.getvalue()))
    data = _box(b"ftyp", b"crx ") + _box(b"moov", canon)
    tags = md._cr3_tags(io.BytesIO(data), len(data))
    assert md.normalise(tags, "cr3_cmt").model == "Canon EOS R8"

    # Truncated / lying box sizes must not raise or loop.
    for broken in (data[:20], data[:-3], struct.pack(">I4s", 0xFFFFFFF0, b"moov") + b"x" * 8, b"\x00" * 7):
        assert isinstance(md._cr3_tags(io.BytesIO(broken), len(broken)), dict)


def _md_uuid(payload: bytes) -> bytes:
    body = md._CR3_CANON_UUID + payload
    return struct.pack(">I4s", 8 + len(body), b"uuid") + body
