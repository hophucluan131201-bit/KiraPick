"""Bottom-bar counts and the size of what an export would copy (RAW+JPEG pairs counted as one photo)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.storage import decisions
from app.storage.project import Project
from app.storage.stats import Counts, counts

MB = 1_000_000


@pytest.fixture
def conn(tmp_path: Path):  # noqa: ANN201
    with Project.create(tmp_path / "s", "t") as project:
        project.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')")
        yield project.conn


def _add(conn: sqlite3.Connection, name: str, size: int, kind: str = "raster", pair: int | None = None,
         status: str = "ok") -> int:
    return int(conn.execute(
        "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, added_at, updated_at, pair_group_id) VALUES (1, ?, ?, ?, 'full', ?, 1, ?, ?, 't', 't', ?)",
        (name, name.rsplit(".", 1)[-1].lower(), kind, size, name, status, pair)).lastrowid)


def _pair(conn: sqlite3.Connection) -> int:
    return int(conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid)


def test_pair_counts_once_and_size_follows_option(conn: sqlite3.Connection) -> None:
    g = _pair(conn)
    raw = _add(conn, "DSC_1.NEF", 30 * MB, "raw", g)
    _add(conn, "DSC_1.JPG", 10 * MB, "raster", g)
    decisions.set_flag(conn, raw, "keep")
    assert counts(conn, include_pairs=True) == Counts(total=1, keep=1, reject=0, undecided=0, errors=0,
                                                      keep_bytes=40 * MB)
    assert counts(conn, include_pairs=False).keep_bytes == 30 * MB


def test_broken_pair_and_jpeg_only(conn: sqlite3.Connection) -> None:
    g = _pair(conn)
    orphan = _add(conn, "DSC_2.JPG", 8 * MB, "raster", g)  # its RAW was removed from the session
    plain = _add(conn, "DSC_3.JPG", 5 * MB)
    for a in (orphan, plain):
        decisions.set_flag(conn, a, "keep")
    c = counts(conn, include_pairs=True)
    assert (c.total, c.keep, c.keep_bytes) == (2, 2, 13 * MB)


def test_undecided_excludes_errors(conn: sqlite3.Connection) -> None:
    ok1, ok2, ok3 = (_add(conn, f"{i}.jpg", MB) for i in range(3))
    _add(conn, "bad.jpg", MB, status="error")
    _add(conn, "gone.jpg", MB, status="missing")  # not shown in the grid: not counted at all
    decisions.set_flag(conn, ok1, "keep")
    decisions.set_flag(conn, ok2, "reject")
    c = counts(conn, include_pairs=True)
    assert (c.total, c.keep, c.reject, c.undecided, c.errors) == (4, 1, 1, 1, 1)
    assert ok3


def test_pair_member_missing_on_disk_status_is_not_in_the_size(conn: sqlite3.Connection) -> None:
    g = _pair(conn)
    raw = _add(conn, "DSC_4.NEF", 30 * MB, "raw", g)
    _add(conn, "DSC_4.JPG", 10 * MB, "raster", g, status="missing")  # the export would skip it
    decisions.set_flag(conn, raw, "keep")
    assert counts(conn, include_pairs=True).keep_bytes == 30 * MB


def test_counts_match_what_the_grid_shows(conn: sqlite3.Connection) -> None:
    """Same rule as the grid query: a JPEG is hidden only when its group has a RAW."""
    from app.ui.asset_model import _QUERY, _FILTER_SQL, Filter

    g = _pair(conn)
    _add(conn, "A.NEF", 1, "raw", g)
    _add(conn, "A.JPG", 1, "raster", g)
    _add(conn, "B.JPG", 1, "raster", _pair(conn))
    _add(conn, "C.JPG", 1)
    shown = conn.execute(_QUERY + _FILTER_SQL[Filter.ALL], {"min_rating": 0, "target_id": None}).fetchall()
    assert counts(conn, include_pairs=True).total == len(shown) == 3


def test_empty_session(conn: sqlite3.Connection) -> None:
    assert counts(conn, include_pairs=True) == Counts(0, 0, 0, 0, 0, 0)


def test_jpeg_whose_raw_went_missing_is_shown_and_counted(conn: sqlite3.Connection) -> None:
    """Spec: a JPEG whose RAW is gone is an ordinary photo (before, the grid hid both files)."""
    from app.ui.asset_model import _QUERY, _FILTER_SQL, Filter

    g = _pair(conn)
    _add(conn, "E.NEF", 30 * MB, "raw", g, status="missing")
    jpg = _add(conn, "E.JPG", 10 * MB, "raster", g)
    decisions.set_flag(conn, jpg, "keep")
    shown = [r["id"] for r in conn.execute(_QUERY + _FILTER_SQL[Filter.ALL], {"min_rating": 0, "target_id": None})]
    assert shown == [jpg]
    c = counts(conn, include_pairs=True)
    assert (c.total, c.keep, c.keep_bytes) == (1, 1, 10 * MB)
