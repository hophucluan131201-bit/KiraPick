"""The bottom bar's size must equal what the export plan would copy (same files, same bytes)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.export.copy_export import Selection, plan_export, run_export, select_assets
from app.storage import decisions
from app.storage.project import Project
from app.storage.stats import SHOWN_PHOTO_SQL, counts
from app.workers.import_job import ImportJob
from tests.integration.test_import_job import _photo


@pytest.fixture
def shoot(tmp_path: Path):  # noqa: ANN201
    root = tmp_path / "shoot"
    for i, name in enumerate(["A.jpg", "A_x.jpg", "A_y.jpg", "B.jpg", "C.jpg", "D.jpg", "E.jpg"]):
        _photo(root / name, i)
    with Project.create(tmp_path / "proj", "p") as project:
        ImportJob(project, root).run()
        conn = project.conn
        ids = {r[1]: r[0] for r in conn.execute("SELECT id, relative_path FROM assets")}
        g3 = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
        conn.execute("UPDATE assets SET pair_group_id = ?, media_kind = CASE relative_path WHEN 'A.jpg' THEN 'raw'"
                     " ELSE 'raster' END WHERE relative_path IN ('A.jpg', 'A_x.jpg', 'A_y.jpg')", (g3,))
        g2 = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
        conn.execute("UPDATE assets SET pair_group_id = ? WHERE relative_path IN ('B.jpg', 'C.jpg')", (g2,))
        conn.execute("UPDATE assets SET media_kind = 'raw', status = 'missing' WHERE relative_path = 'B.jpg'")
        yield project, root, ids


@pytest.mark.parametrize("include_pairs", [True, False])
def test_size_equals_the_export_plan(shoot, tmp_path: Path, include_pairs: bool) -> None:  # noqa: ANN001
    project, _root, ids = shoot
    conn = project.conn
    for name in ("A.jpg", "A_x.jpg", "C.jpg", "D.jpg"):  # A_x: a kept hidden member; C: JPEG whose RAW is missing
        decisions.set_flag(conn, ids[name], "keep")
    decisions.set_flag(conn, ids["E.jpg"], "keep")
    conn.execute("UPDATE assets SET status = 'error' WHERE id = ?", (ids["E.jpg"],))  # kept, now unreadable
    plan = plan_export(project, select_assets(project, Selection.KEEP), tmp_path / f"out{include_pairs}",
                       include_pairs=include_pairs)
    assert counts(conn, include_pairs).keep_bytes == plan.total_bytes > 0


def test_jpeg_fallback_grid_keep_export(shoot, tmp_path: Path) -> None:  # noqa: ANN001
    """A JPEG whose RAW went missing: shown in the grid, can be kept, and is exported alone."""
    project, root, ids = shoot
    conn = project.conn
    shown = {r[0] for r in conn.execute(f"SELECT a.id FROM assets a WHERE {SHOWN_PHOTO_SQL}")}
    assert ids["C.jpg"] in shown and ids["B.jpg"] not in shown
    decisions.set_flag(conn, ids["C.jpg"], "keep")
    plan = plan_export(project, select_assets(project, Selection.KEEP), tmp_path / "out")
    result = run_export(plan)
    assert result.copied == ["C.jpg"] and (tmp_path / "out" / "C.jpg").read_bytes() == (root / "C.jpg").read_bytes()
