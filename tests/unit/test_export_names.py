"""Part 3 Task 8 — the names of the kept photos, one line per photo (spec §3.8, CR-P3-04)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.export.copy_export import Selection, select_assets
from app.export.names import keep_names
from app.storage import decisions
from tests.fixtures_export import add_asset, make_export_session
from tests.unit.test_export_layout import _occ, _subject

KEPT = ["DSC_0001", "DSC_0002", "DSC_0003", "DSC_0004", "DSC_0005", "DSC_0006"]


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


def _keep(fx) -> list[int]:  # noqa: ANN001
    return select_assets(fx.project, Selection.KEEP)


def test_one_line_per_photo_with_pairs(fx) -> None:  # noqa: ANN001
    names = keep_names(fx.project.conn, _keep(fx), with_extension=False)
    assert names.lines == KEPT and names.photos == 6 and names.shared_stems == {}
    names = keep_names(fx.project.conn, _keep(fx), with_extension=True)
    assert names.lines == ["DSC_0001.NEF", "DSC_0002.NEF", "DSC_0003.NEF", "DSC_0004.JPG", "DSC_0005.TIF",
                           "DSC_0006.PNG"]  # the RAW for a pair, as the grid shows


def test_pair_named_by_its_raw_whichever_file_is_asked(fx) -> None:  # noqa: ANN001
    raw, jpg = fx.files["pair"]
    for ids in ([raw, jpg], [jpg, raw]):
        decisions.set_flag(fx.project.conn, ids[0], "keep")
        assert keep_names(fx.project.conn, ids, with_extension=True).lines == ["DSC_0001.NEF"]


def test_scope_intersect_keep(fx) -> None:  # noqa: ANN001
    favourites = select_assets(fx.project, Selection.FAVORITE)
    assert fx.ids["fav"] in favourites  # a favourite that is not kept
    assert keep_names(fx.project.conn, favourites, with_extension=False).lines == ["DSC_0001"]
    rated = select_assets(fx.project, Selection.RATED, min_rating=3)
    assert keep_names(fx.project.conn, rated, with_extension=False).lines == ["DSC_0003"]


def test_order_capture_time_then_name(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    conn.execute("UPDATE assets SET capture_time = '2026-10-25T15:00:00' WHERE relative_path = 'DSC_0006.PNG'")
    conn.execute("UPDATE assets SET capture_time = NULL WHERE relative_path = 'DSC_0002.NEF'")
    conn.execute("UPDATE assets SET capture_time = NULL WHERE relative_path = 'DSC_0002.JPG'")
    lines = keep_names(conn, _keep(fx), with_extension=False).lines
    assert lines == ["DSC_0006", "DSC_0001", "DSC_0003", "DSC_0004", "DSC_0005", "DSC_0002"]  # unknown time last


def test_shared_stem_listed_once_with_note(fx) -> None:  # noqa: ANN001
    source_id = fx.project.conn.execute("SELECT id FROM sources").fetchone()[0]
    other = add_asset(fx.project, source_id, fx.root, "Buổi 2/DSC_0001.JPG", seed=900, kind="raster")
    decisions.set_flag(fx.project.conn, other, "keep")
    names = keep_names(fx.project.conn, _keep(fx), with_extension=False)
    assert names.lines == KEPT and names.photos == 7
    assert names.shared_stems == {"DSC_0001": 2}
    with_ext = keep_names(fx.project.conn, _keep(fx), with_extension=True)
    assert with_ext.lines.count("DSC_0001.NEF") == 1 and "DSC_0001.JPG" in with_ext.lines
    assert with_ext.shared_stems == {"DSC_0001": 2}


def test_independent_of_subjects(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    a, b = _subject(conn, "Mai"), _subject(conn, "Lan")
    _occ(conn, fx.ids["pair"], a)
    _occ(conn, fx.ids["pair"], b)
    assert keep_names(conn, _keep(fx), with_extension=False).lines == KEPT


def test_works_without_disk(fx) -> None:  # noqa: ANN001
    before = keep_names(fx.project.conn, _keep(fx), with_extension=True)
    fx.root.rename(fx.root.with_name("moved away"))  # card / drive disconnected
    assert keep_names(fx.project.conn, _keep(fx), with_extension=True) == before


def test_empty_scope(fx) -> None:  # noqa: ANN001
    names = keep_names(fx.project.conn, [], with_extension=False)
    assert names.lines == [] and names.photos == 0 and names.shared_stems == {}
