"""RV-P3-C03 — cross-format matching on real camera RAW files (tests/fixtures/raw_samples.json; absent samples skip).

For every sample KiraPick imports: its capture time and camera are read the way the export reads a card candidate;
a JPEG photo taken ≤ 2 s from it with the same camera matches it by time; 3 s away or another camera does not; a RAW
whose capture time cannot be read is "ambiguous" (the user decides), never matched. One file per format family is
then copied with run_export, which reads the capture time again from the copy. The samples are hard-linked into
the test's folder (read only; no copy of the sample is written)."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.export.copy_export import ExportOp, ExportPlan, run_export
from app.export.formats import file_kind
from app.export.hashing import HashCache, sha256_file
from app.export.photos import Photo
from app.export.sources import SourceIdentity, match_file, scan_external
from app.ingest.metadata import read_metadata
from tests.conftest import sample_path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = json.loads((ROOT / "tests" / "fixtures" / "raw_samples.json").read_text(encoding="utf-8"))["samples"]
RAW_SAMPLES = [s for s in SAMPLES if file_kind(s["file"]) == "raw"]
COPY_ONE_PER = {".nef": "public/iss030e122639.NEF", ".cr3": "mei/Canon EOS R3.cr3",
                ".arw": "mei/Sony ILCE-7M3 (A7M3).arw"}


def _card(tmp_path: Path, sample: Path) -> Path:
    card = tmp_path / "card"
    card.mkdir()
    target = card / sample.name
    try:
        os.link(sample, target)  # same bytes, no extra disk
    except OSError:
        shutil.copy2(sample, target)
    return card


def _photo(stem: str, when: datetime | None, subsec: str | None, camera: str | None) -> Photo:
    return Photo(1, stem, (), when, subsec, camera, "keep", 0, False)


def _camera(meta) -> str | None:  # noqa: ANN001
    return " ".join(filter(None, [meta.make, meta.model])) or None


@pytest.mark.parametrize("sample", RAW_SAMPLES, ids=[s["file"] for s in RAW_SAMPLES])
def test_real_raw_matches_by_capture_time(tmp_path: Path, sample: dict) -> None:
    path = sample_path(sample)
    card = _card(tmp_path, path)
    index = scan_external(card, session_folder=tmp_path / "session", destination=tmp_path / "out")
    assert index.files == 1, "the sample's extension is indexed as RAW"
    meta = read_metadata(card / path.name)
    stem = path.stem
    taken = datetime.fromisoformat(meta.datetime_original) if meta.datetime_original else None
    if taken is None:
        m = match_file(_photo(stem, datetime(2026, 1, 1), None, None), "raw", index, hashes=HashCache())
        assert m.status == "ambiguous" and m.candidates[0].capture_time is None  # never matched blind
        pytest.skip(f"capture time not readable from {path.suffix} sample: reported as 'Không chắc' (tested)")
    camera = _camera(meta)
    near = match_file(_photo(stem, taken + timedelta(seconds=2), None, camera), "raw", index, hashes=HashCache())
    assert (near.status, near.method) == ("matched", "time")
    assert near.candidates[0].capture_time == taken and near.candidates[0].camera == camera
    far = match_file(_photo(stem, taken + timedelta(seconds=3), None, camera), "raw", index, hashes=HashCache())
    assert far.status == "not_matched"
    if camera:
        other = match_file(_photo(stem, taken, None, "Other Maker X1"), "raw", index, hashes=HashCache())
        assert other.status == "not_matched"
    if meta.subsec:
        sub = match_file(_photo(stem, taken, meta.subsec, camera), "raw", index, hashes=HashCache())
        assert sub.status == "matched"


@pytest.mark.parametrize("suffix", sorted(COPY_ONE_PER))
def test_real_raw_copied_and_reverified(tmp_path: Path, suffix: str) -> None:
    sample = next(s for s in SAMPLES if s["file"] == COPY_ONE_PER[suffix])
    path = sample_path(sample)
    card = _card(tmp_path, path)
    meta = read_metadata(card / path.name)
    if not meta.datetime_original:
        pytest.skip(f"{suffix}: capture time not readable")
    taken = datetime.fromisoformat(meta.datetime_original)
    photo = _photo(path.stem, taken, None, _camera(meta))
    index = scan_external(card, session_folder=tmp_path / "session", destination=tmp_path / "out")
    m = match_file(photo, "raw", index, hashes=HashCache())
    assert m.status == "matched" and m.identity is not None
    op = ExportOp(1, 1, "raw", m.source.path, m.source.relative, "", path.name, m.identity.size, "time", m.identity)
    plan = ExportPlan(tmp_path / "out", [op], photos={1: photo})
    result = run_export(plan)
    assert result.statuses == {path.name: "copied"}  # the capture time was read again from the copy and still matched
    assert result.hashes[path.name] == sha256_file(path) == sample["sha256"]
    shutil.rmtree(tmp_path / "out")  # do not keep a copy of the sample


def test_samples_cover_nef_cr3_arw() -> None:
    """The manifest lists real NEF, CR3 and ARW files; other formats are listed in the review as tested or not."""
    suffixes = {Path(s["file"]).suffix.lower() for s in RAW_SAMPLES}
    assert {".nef", ".cr3", ".arw"} <= suffixes
