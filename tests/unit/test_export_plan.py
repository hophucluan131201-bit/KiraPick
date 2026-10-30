"""Part 3 Task 3 — the planner: operations, issues and formats on the imported source.

The default plan (Imported + RAW_JPEG + one folder) must equal today's export with "Kèm JPEG" on: the golden
snapshots of Task 1 (CR-P3-02; the equivalence covers include_pairs=True only, CR-P3-D03)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.export.copy_export import ExportError, IssueStatus, Selection, estimated_bytes, plan_export, select_ids
from app.export.formats import ExportFormat
from app.export.layout import Layout
from app.export.sources import SourceSpec
from app.storage.stats import counts
from tests.fixtures_export import make_export_session, snapshot, write_file
from tests.unit.test_export_compat import GOLDEN, GOLDEN_INCLUDE_PAIRS_FALSE, _scope_ids


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


@pytest.mark.parametrize("scope", list(GOLDEN))
def test_default_plan_equals_todays_export(fx, scope: Selection) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, _scope_ids(fx, scope), fx.dest)
    assert snapshot(plan) == GOLDEN[scope]
    explicit = plan_export(fx.project, _scope_ids(fx, scope), fx.dest, source=SourceSpec("imported"),
                           fmt=ExportFormat.RAW_JPEG, layout=Layout.SINGLE)
    assert snapshot(explicit) == GOLDEN[scope]


def test_default_plan_keeps_collisions_and_already_present(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    write_file(fx.dest / "DSC_0001.NEF", 999, 1000)
    (fx.dest / "DSC_0003.NEF").write_bytes((fx.root / "DSC_0003.NEF").read_bytes())
    snap = snapshot(plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest))
    assert ("DSC_0001.NEF", "DSC_0001 (1).NEF") in snap["copies"] and ("DSC_0001.JPG", "DSC_0001 (1).JPG") in snap["copies"]
    assert snap["already_present"] == ["DSC_0003.NEF"]


def test_include_pairs_false_differs_and_is_documented(fx) -> None:  # noqa: ANN001
    """The old "Kèm JPEG" off has no equivalent: RAW_JPEG adds exactly the pairs' JPEGs (and reports the missing one)."""
    new = snapshot(plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest))
    extra = sorted(set(new["copies"]) - set(GOLDEN_INCLUDE_PAIRS_FALSE["copies"]))
    assert extra == [("DSC_0001.JPG", "DSC_0001.JPG")]
    assert not set(GOLDEN_INCLUDE_PAIRS_FALSE["copies"]) - set(new["copies"])
    assert new["missing"] == ["DSC_0002.JPG"]


def _names(plan) -> list[str]:  # noqa: ANN001
    return sorted(op.dest_relative for op in plan.operations)


def _issues(plan) -> dict[str, IssueStatus]:  # noqa: ANN001
    return {i.stem + (f".{i.kind}" if i.kind else ""): i.status for i in plan.issues}


def test_format_raw(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest, fmt=ExportFormat.RAW)
    assert _names(plan) == ["DSC_0001.NEF", "DSC_0002.NEF", "DSC_0003.NEF"]
    issues = _issues(plan)
    assert issues == {"DSC_0004.raw": IssueStatus.MISSING_FORMAT, "DSC_0005.raw": IssueStatus.MISSING_FORMAT,
                      "DSC_0006.raw": IssueStatus.MISSING_FORMAT}
    assert next(i for i in plan.issues if i.stem == "DSC_0004").detail == "Thiếu RAW"


def test_format_jpeg(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest, fmt=ExportFormat.JPEG)
    assert _names(plan) == ["DSC_0001.JPG", "DSC_0004.JPG"]
    assert _issues(plan) == {
        "DSC_0002.jpeg": IssueStatus.MISSING,  # it has a JPEG, gone from disk
        "DSC_0003.jpeg": IssueStatus.MISSING_FORMAT, "DSC_0005.jpeg": IssueStatus.MISSING_FORMAT,
        "DSC_0006.jpeg": IssueStatus.MISSING_FORMAT,
    }
    assert next(i for i in plan.issues if i.stem == "DSC_0003").detail == "Thiếu JPEG"


def test_raw_jpeg_keeps_other_rasters(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, _scope_ids(fx, Selection.KEEP), fx.dest, fmt=ExportFormat.RAW_JPEG)
    assert {"DSC_0005.TIF", "DSC_0006.PNG"} <= set(_names(plan))
    assert _issues(plan) == {"DSC_0002.jpeg": IssueStatus.MISSING}


def test_missing_on_disk_is_an_issue(fx) -> None:  # noqa: ANN001
    (fx.root / "DSC_0003.NEF").unlink()
    plan = plan_export(fx.project, [fx.ids["raw_only"], fx.ids["jpeg_only"]], fx.dest)
    assert _names(plan) == ["DSC_0004.JPG"]
    assert _issues(plan) == {"DSC_0003.raw": IssueStatus.MISSING}
    assert plan.missing == ["DSC_0003.NEF"] and plan.photos_planned == 1


def test_identity_recorded(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, [fx.ids["pair"]], fx.dest)
    for op in plan.operations:
        st = op.source.stat()
        assert (op.identity.size, op.identity.mtime_ns, op.identity.sha256) == (st.st_size, st.st_mtime_ns, None)
        assert op.match == "imported" and op.folder == "" and op.photo_id == fx.ids["pair"]
    assert {op.asset_id for op in plan.operations} == set(fx.files["pair"])


def test_a_pairs_jpeg_selected_too_is_copied_once(fx) -> None:  # noqa: ANN001
    raw, jpg = fx.files["pair"]
    plan = plan_export(fx.project, [raw, jpg], fx.dest)
    assert _names(plan) == ["DSC_0001.JPG", "DSC_0001.NEF"]


def test_external_source_not_yet_supported(fx) -> None:  # noqa: ANN001
    with pytest.raises(ExportError):
        plan_export(fx.project, [fx.ids["pair"]], fx.dest, source=SourceSpec("external", fx.root))


@pytest.mark.parametrize("fmt", list(ExportFormat))
def test_estimated_bytes_per_format(fx, fmt: ExportFormat) -> None:  # noqa: ANN001
    ids = _scope_ids(fx, Selection.KEEP)
    (fx.root / "DSC_0002.JPG").write_bytes(b"")  # every recorded file present: the estimate has no disk access
    plan = plan_export(fx.project, ids, fx.dest, fmt=fmt)
    (fx.root / "DSC_0002.JPG").unlink()
    recorded = {op.dest_relative: op.size for op in plan.operations}
    if "DSC_0002.JPG" in recorded:
        recorded["DSC_0002.JPG"] = 300_000  # the size the import recorded (the stand-in file is empty)
    assert estimated_bytes(fx.project.conn, ids, fmt=fmt) == sum(recorded.values())


def test_bottom_bar_follows_format(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    kept = select_ids(conn, Selection.KEEP)
    for fmt in ExportFormat:
        assert counts(conn, fmt).keep_bytes == estimated_bytes(conn, kept, fmt=fmt)
    assert counts(conn, ExportFormat.RAW).keep_bytes == 3 * 500_000 - 500_000 + 300_000  # 2 pair RAWs + DSC_0003


def test_marked_unreadable_photo_is_still_copied(fx) -> None:  # noqa: ANN001
    """Before Part 3 a marked photo (scope IDS) the import could not decode (status 'error') was still copied: the
    file exists, only its preview failed. The new planner keeps that (self-review of batch A)."""
    conn = fx.project.conn
    conn.execute("UPDATE assets SET status = 'error' WHERE id = ?", (fx.ids["jpeg_only"],))
    plan = plan_export(fx.project, [fx.ids["jpeg_only"]], fx.dest)
    assert _names(plan) == ["DSC_0004.JPG"] and plan.issues == []
