"""End-to-end checks against real camera files listed in tests/fixtures/raw_samples.json.

Samples live in test_photos/ (git-ignored); missing ones are skipped, so these
tests prove support only for the files that were actually present in a run.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.core.errors import ImageReadError, NoPreviewError
from app.ingest import cli, raw_decode
from app.ingest.fingerprint import full_sha256
from app.ingest.metadata import read_metadata
from app.ingest.preview import PreviewSource, load_full_resolution, load_image
from app.ingest.validation import check_embedded_orientation
from tests.conftest import PHOTOS, load_samples, sample_path

pytestmark = pytest.mark.samples

SAMPLES = load_samples()
GOOD = [s for s in SAMPLES if s["expect"] == "ok"]
BAD = [s for s in SAMPLES if s["expect"] != "ok"]


def _id(sample: dict) -> str:
    return sample["file"]


@pytest.mark.parametrize("sample", GOOD, ids=_id)
def test_good_raw_decodes_with_correct_geometry_and_metadata(sample: dict) -> None:
    path = sample_path(sample)
    assert full_sha256(path) == sample["sha256"], "sample differs from manifest"

    grid = load_image(path, max_long_side=320, min_long_side=320, with_metadata=True)
    assert max(grid.image.size) == 320
    info, _ = raw_decode.read_raw(path)
    portrait = info.orientation in (5, 6, 7, 8)
    assert (grid.image.height > grid.image.width) == portrait
    assert (grid.full_size[1] > grid.full_size[0]) == portrait

    analysis = load_image(path, max_long_side=1600, min_long_side=1600)
    assert max(analysis.image.size) == 1600
    assert max(analysis.native_size) >= 1600, "analysis preview must not be upscaled"

    meta = grid.metadata
    assert meta is not None and meta.make == sample.get("make") and meta.model == sample.get("model")
    assert full_sha256(path) == sample["sha256"], "source file was modified"


@pytest.mark.slow
@pytest.mark.parametrize("sample", GOOD, ids=_id)
def test_embedded_preview_orientation_agrees_with_libraw(sample: dict) -> None:
    check = check_embedded_orientation(sample_path(sample))
    assert check is not None and check.passed, check


@pytest.mark.slow
@pytest.mark.parametrize("sample", GOOD, ids=_id)
def test_full_resolution_is_really_full_resolution(sample: dict) -> None:
    loaded = load_full_resolution(sample_path(sample))
    assert loaded.is_full_resolution
    assert loaded.image.size == loaded.native_size


@pytest.mark.parametrize("sample", BAD, ids=_id)
def test_damaged_or_stripped_files_fail_cleanly(sample: dict) -> None:
    path = sample_path(sample)
    expect = sample["expect"]
    if expect.startswith("preview_only:"):
        # Embedded preview is usable, sensor data is not: shown, never analysed at 100%.
        load_image(path, max_long_side=320)
        with pytest.raises(ImageReadError) as info:
            load_full_resolution(path)
        assert type(info.value).__name__ == expect.split(":", 1)[1]
    else:
        with pytest.raises(ImageReadError) as info:
            load_image(path, max_long_side=320, min_long_side=320)
        assert type(info.value).__name__ == expect


def test_stripped_file_rejected_even_after_decoding_real_files() -> None:
    """Regression: LibRaw reused a stale buffer, so a stripped DNG 'decoded'
    as a valid (black) image when it followed real files in the same process."""
    stripped = sample_path({"file": "stripped/DNG.dng"})
    for real in ("mei/Leica T (Typ 701).dng", "public/iss030e122639.NEF"):
        raw_decode.demosaic(sample_path({"file": real}), half_size=True)
        with pytest.raises(NoPreviewError):
            load_image(stripped, max_long_side=320, min_long_side=320)


def test_metadata_sources_for_cr3_and_raf() -> None:
    cr3 = read_metadata(sample_path({"file": "mei/Canon EOS R3.cr3"}))
    assert cr3.model == "Canon EOS R3" and cr3.datetime_original == "2023-02-09T10:10:27"
    assert "cr3_cmt" in cr3.sources
    raf = read_metadata(sample_path({"file": "mei/Fujifilm X-E1.raf"}))
    assert raf.model == "X-E1" and "embedded_jpeg" in raf.sources


def test_small_sony_preview_falls_back_to_demosaic_for_full_res() -> None:
    path = sample_path({"file": "mei/Sony NEX-7.arw"})
    assert load_image(path, max_long_side=320, min_long_side=320).source is PreviewSource.EMBEDDED_JPEG
    full = load_full_resolution(path)
    assert full.source is PreviewSource.DEMOSAIC_FULL and full.image.size == (6024, 4024)


def test_unicode_and_space_paths(tmp_path: Path, public_nef: Path) -> None:
    target = tmp_path / "Lễ hội Cosplay 2026" / "ảnh đẹp nhất (1).NEF"
    target.parent.mkdir()
    shutil.copyfile(public_nef, target)
    loaded = load_image(target, max_long_side=320, min_long_side=320, with_metadata=True)
    assert loaded.metadata is not None and loaded.metadata.model == "NIKON D3S"


@pytest.mark.parametrize("fraction", [0.002, 0.02, 0.3, 0.6, 0.95])
def test_truncated_nef_never_yields_unflagged_garbage(tmp_path: Path, public_nef: Path, fraction: float) -> None:
    data = public_nef.read_bytes()
    path = tmp_path / f"cut_{fraction}.NEF"
    path.write_bytes(data[: int(len(data) * fraction)])
    try:
        loaded = load_full_resolution(path, allow_embedded=False)
    except ImageReadError:
        return  # clean, typed failure
    # If LibRaw decoded it, the result must still match the real photo.
    reference = load_full_resolution(public_nef, allow_embedded=False)
    from app.ingest.validation import edge_similarity

    assert edge_similarity(loaded.image, reference.image) > 0.5


def test_probe_cli_reports_and_proves_sources_untouched(tmp_path: Path, public_nef: Path) -> None:
    folder = tmp_path / "shoot"
    folder.mkdir()
    shutil.copyfile(public_nef, folder / "good.NEF")
    (folder / "broken.nef").write_bytes(b"garbage" * 1000)
    (folder / "readme.txt").write_text("x")
    report = tmp_path / "report.json"
    code = cli.main([str(folder), "--verify", "--verify-untouched", "--json", str(report)])
    data = json.loads(report.read_text(encoding="utf-8"))
    assert code == 1  # one broken file
    assert data["sources_unchanged"] is True
    assert data["unsupported_extensions"] == {".txt": 1}
    by_name = {f["path"]: f for f in data["files"]}
    assert by_name["good.NEF"]["orientation_check"] == "pass" and by_name["good.NEF"]["error"] is None
    assert by_name["broken.nef"]["error"].startswith("unsupported_format")
    assert sorted(p.name for p in folder.iterdir()) == ["broken.nef", "good.NEF", "readme.txt"]


def test_manifest_covers_requested_formats() -> None:
    present = {Path(s["file"]).suffix.lower() for s in GOOD}
    assert {".nef", ".cr2", ".cr3", ".arw"} <= present
    assert PHOTOS.name == "test_photos"
