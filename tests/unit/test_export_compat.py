"""Part 3 Task 1 — compatibility baseline: what today's export plans for every kind of photo and scope.

The golden values below are the export of Parts 1–2 (``include_pairs=True``, the default). Task 3 runs the same
expectations against the new planner (Imported + RAW_JPEG + one folder): the equivalence claim covers
``include_pairs=True`` only (review CR-P3-D03). ``GOLDEN_INCLUDE_PAIRS_FALSE`` records the old "off" behaviour,
which the new options replace (documented difference, not an equivalence)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.export.copy_export import Selection, plan_export, run_export, select_assets
from tests.fixtures_export import make_export_session, snapshot, tree_digest, write_file

KEPT = {
    "copies": [
        ("DSC_0001.JPG", "DSC_0001.JPG"), ("DSC_0001.NEF", "DSC_0001.NEF"),
        ("DSC_0002.NEF", "DSC_0002.NEF"),
        ("DSC_0003.NEF", "DSC_0003.NEF"), ("DSC_0004.JPG", "DSC_0004.JPG"),
        ("DSC_0005.TIF", "DSC_0005.TIF"), ("DSC_0006.PNG", "DSC_0006.PNG"),
    ],
    "already_present": [],
    "missing": ["DSC_0002.JPG"],
}
GOLDEN = {
    Selection.KEEP: KEPT,
    Selection.FAVORITE: {"copies": [("DSC_0001.JPG", "DSC_0001.JPG"), ("DSC_0001.NEF", "DSC_0001.NEF"),
                                    ("DSC_0009.JPG", "DSC_0009.JPG")], "already_present": [], "missing": []},
    Selection.RATED: {"copies": [("DSC_0003.NEF", "DSC_0003.NEF"), ("DSC_0010.JPG", "DSC_0010.JPG")],
                      "already_present": [], "missing": []},
    Selection.IDS: {"copies": [("DSC_0001.JPG", "DSC_0001.JPG"), ("DSC_0001.NEF", "DSC_0001.NEF"),
                               ("DSC_0008.JPG", "DSC_0008.JPG")], "already_present": [], "missing": []},
    Selection.COLLECTION: {"copies": [("DSC_0004.JPG", "DSC_0004.JPG"), ("DSC_0011.JPG", "DSC_0011.JPG")],
                           "already_present": [], "missing": []},
}
GOLDEN_INCLUDE_PAIRS_FALSE = {
    "copies": [(src, dst) for src, dst in KEPT["copies"] if src != "DSC_0001.JPG"],
    "already_present": [],
    "missing": [],  # the missing JPEG is not looked at when pairs are off
}


def _scope_ids(fx, scope: Selection) -> list[int]:  # noqa: ANN001
    return select_assets(fx.project, scope, min_rating=3, ids=[fx.ids["pair"], fx.ids["undecided"]],
                         collection_id=fx.collection_id)


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


@pytest.mark.parametrize("scope", list(GOLDEN))
def test_today_plan_matches_golden(fx, scope: Selection) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, _scope_ids(fx, scope), fx.dest, include_pairs=True)
    assert snapshot(plan) == GOLDEN[scope]


def test_keep_never_lists_rejected_or_undecided(fx) -> None:  # noqa: ANN001
    ids = set(_scope_ids(fx, Selection.KEEP))
    assert fx.ids["rejected"] not in ids and fx.ids["undecided"] not in ids
    assert fx.files["pair"][1] not in ids  # the pair's JPEG comes with its RAW, it is not a photo of its own


def test_today_include_pairs_false_golden(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest, include_pairs=False)
    assert snapshot(plan) == GOLDEN_INCLUDE_PAIRS_FALSE


def test_today_collision_and_already_present(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    write_file(fx.dest / "DSC_0001.NEF", 999, 1000)  # a different file of the same name
    (fx.dest / "DSC_0003.NEF").write_bytes((fx.root / "DSC_0003.NEF").read_bytes())  # an identical copy
    plan = plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest, include_pairs=True)
    snap = snapshot(plan)
    assert ("DSC_0001.NEF", "DSC_0001 (1).NEF") in snap["copies"]
    assert ("DSC_0001.JPG", "DSC_0001 (1).JPG") in snap["copies"]  # the pair keeps one stem
    assert snap["already_present"] == ["DSC_0003.NEF"]
    assert ("DSC_0003.NEF", "DSC_0003.NEF") not in snap["copies"]


def _tables(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
            for t in ("decisions", "occurrences", "view_rotation", "assets", "subjects")}


def test_export_changes_nothing_but_destination(fx) -> None:  # noqa: ANN001
    before_db, before_files = _tables(fx.project.conn), tree_digest(fx.root)
    plan = plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest, include_pairs=True)
    result = run_export(plan)
    assert len(result.copied) == 7 and not result.failed
    assert _tables(fx.project.conn) == before_db
    assert tree_digest(fx.root) == before_files
