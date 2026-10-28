"""Histogram of the displayed preview and the burst of a photo (same person, taken within ±3 s)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.quality.burst import neighbours
from app.quality.histogram import BINS, Histogram, histogram
from app.storage.project import Project


def test_half_black_half_white() -> None:
    img = np.zeros((300, 400, 3), np.uint8)
    img[:, 200:] = 255
    h = histogram(img)
    assert isinstance(h, Histogram) and h.bins.shape == (BINS,) == (64,)
    assert h.shadows == pytest.approx(0.5, abs=0.01) and h.highlights == pytest.approx(0.5, abs=0.01)
    assert h.bins[0] == 1.0 and h.bins[63] == 1.0 and h.bins[1:63].sum() == 0


def test_grey_is_one_bin_and_uses_luminance_weights() -> None:
    h = histogram(np.full((50, 50, 3), 128, np.uint8))
    assert h.bins[32] == 1.0 and h.bins.sum() == 1.0 and h.shadows == 0 and h.highlights == 0
    green = np.zeros((10, 10, 3), np.uint8)
    green[..., 1] = 255  # Y = 0.7152 * 255 = 182.4 -> bin 45
    assert int(np.argmax(histogram(green).bins)) == 45


def test_clipping_thresholds_are_2_and_253() -> None:
    img = np.array([[[2, 2, 2], [3, 3, 3], [252, 252, 252], [253, 253, 253]]], np.uint8)
    h = histogram(img)
    assert h.shadows == pytest.approx(0.25) and h.highlights == pytest.approx(0.25)


def test_big_image_is_downscaled_and_grey_input_accepted() -> None:
    big = np.full((3000, 4000, 3), 128, np.uint8)
    big[:, :1000] = 0  # a quarter is black: survives the area-averaging downscale
    h = histogram(big)
    assert h.bins.max() == 1.0 and h.shadows == pytest.approx(0.25, abs=0.01)
    assert histogram(np.full((20, 20), 255, np.uint8)).highlights == 1.0


@pytest.mark.parametrize("bad", [np.zeros((0, 10, 3), np.uint8), np.zeros((10, 10, 3), np.float32),
                                 np.zeros((10, 10, 4, 1), np.uint8)])
def test_invalid_input_is_refused(bad: np.ndarray) -> None:
    with pytest.raises(ValueError):
        histogram(bad)


# ----------------------------------------------------------------------------------- burst
@pytest.fixture
def conn(tmp_path: Path):  # noqa: ANN201
    with Project.create(tmp_path / "s", "t") as project:
        project.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')")
        yield project.conn


def _photo(conn: sqlite3.Connection, seconds: float | None, subject: int | None = None, *, main: bool = True,
           kind: str = "raster", pair: int | None = None) -> int:
    when = sub = None
    if seconds is not None:
        whole = int(seconds)
        when = f"2026-10-25T16:00:{whole:02d}"
        sub = f"{round((seconds - whole) * 100):02d}"
    n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    aid = int(conn.execute(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at, capture_time, subsec, pair_group_id) "
        "VALUES (1, ?, 'jpg', ?, 'full', 1, 1, ?, 'ok', 't', 't', ?, ?, ?)",
        (f"{n}.jpg", kind, f"h{n}", when, sub, pair)).lastrowid)
    if subject is not None:
        if not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject,)).fetchone():
            conn.execute("INSERT INTO subjects (id, created_at) VALUES (?, 't')", (subject,))
        conn.execute("INSERT INTO occurrences (asset_id, prominence, is_main, analysis_version, created_at, subject_id)"
                     " VALUES (?, 1, ?, 1, 't', ?)", (aid, int(main), subject))
    return aid


def test_burst_of_the_same_person_within_three_seconds(conn: sqlite3.Connection) -> None:
    t0, t2, t3, t55 = (_photo(conn, t, subject=1) for t in (0, 2, 3, 5.5))
    other = _photo(conn, 1, subject=2)
    assert neighbours(conn, t2) == [t0, t3]
    assert t55 not in neighbours(conn, t2) and other not in neighbours(conn, t2)  # 3.5 s away / another person
    assert neighbours(conn, t55) == [t3]  # 2.5 s before


def test_sub_second_precision(conn: sqlite3.Connection) -> None:
    a = _photo(conn, 10.0, subject=1)
    b = _photo(conn, 13.0, subject=1)  # exactly 3 s: included
    c = _photo(conn, 13.5, subject=1)  # 3.5 s: excluded
    assert neighbours(conn, a) == [b] and c not in neighbours(conn, a)


def test_photo_without_time_or_without_people(conn: sqlite3.Connection) -> None:
    no_time = _photo(conn, None, subject=1)
    assert neighbours(conn, no_time) == []
    loose = _photo(conn, 20)  # not recognised yet: any photo of the burst
    with_person = _photo(conn, 21, subject=1)
    no_person = _photo(conn, 22)
    assert neighbours(conn, loose) == [with_person, no_person]


def test_hidden_jpeg_of_a_pair_is_not_a_neighbour(conn: sqlite3.Connection) -> None:
    g = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
    raw = _photo(conn, 30, subject=1, kind="raw", pair=g)
    _photo(conn, 30, kind="raster", pair=g)  # the JPEG of the same shot
    nxt = _photo(conn, 31, subject=1)
    assert neighbours(conn, nxt) == [raw]


def test_unknown_photo(conn: sqlite3.Connection) -> None:
    assert neighbours(conn, 999) == []


def test_burst_across_a_minute_and_midnight(conn: sqlite3.Connection) -> None:
    def at(when: str, sub: str) -> int:
        n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        return int(conn.execute(
            "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
            "quick_hash, status, added_at, updated_at, capture_time, subsec) "
            "VALUES (1, ?, 'jpg', 'raster', 'full', 1, 1, ?, 'ok', 't', 't', ?, ?)",
            (f"m{n}.jpg", f"m{n}", when, sub)).lastrowid)
    a, b = at("2026-10-25T16:00:59", "50"), at("2026-10-25T16:01:01", "00")
    c, d = at("2026-10-25T23:59:59", "00"), at("2026-10-26T00:00:01", "00")
    assert neighbours(conn, a) == [b] and neighbours(conn, c) == [d]


def test_capture_time_contract_from_the_importer() -> None:
    """Review RV5-01. The importer stores DateTimeOriginal as naive ISO local time 'YYYY-MM-DDTHH:MM:SS' (no time
    zone is read) and SubSecTimeOriginal as text: the owner's Z5 NEFs give two digits ('07', '20', '59')."""
    from datetime import datetime

    from app.ingest.metadata import _as_datetime
    from app.quality.burst import _moment

    assert _as_datetime("2026:07:12 15:53:18") == "2026-07-12T15:53:18"
    base = datetime(2026, 7, 12, 15, 53, 18)
    assert _moment("2026-07-12T15:53:18", "07") == base.replace(microsecond=70_000)  # hundredths (Nikon)
    assert _moment("2026-07-12T15:53:18", "123") == base.replace(microsecond=123_000)  # thousandths
    assert _moment("2026-07-12T15:53:18", "07 ") == base.replace(microsecond=70_000)  # space-padded EXIF text
    assert _moment("2026-07-12T15:53:18", "") == base and _moment("2026-07-12T15:53:18", None) == base
    assert _moment("2026-07-12T15:53:18", "ab") == base  # junk ignored, the second still counts
    assert _moment("not a date", "07") is None and _moment(None, None) is None
