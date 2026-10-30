"""Part 3 Task 11 — every combination of ① source × ② format × ③ layout (2 × 3 × 2 = 12) on one session: RAW+JPEG
pairs, a pair whose JPEG is gone, RAW-only, JPEG-only, TIFF, PNG, two subjects (one photo in both), unknown photos,
and another folder holding RAWs (one only by capture time) plus a counter-restart duplicate. Plan + copy + manifest;
sources and the other folder byte-identical afterwards; the names list identical in every combination."""

from __future__ import annotations

import csv
import itertools
import shutil
from pathlib import Path

import pytest

from app.export.copy_export import Selection, plan_export, run_export, select_assets
from app.export.formats import ExportFormat
from app.export.layout import UNKNOWN_FOLDER, Layout
from app.export.names import keep_names
from app.export.sources import SourceSpec, scan_external
from tests.fixtures_export import make_export_session, tree_digest
from tests.unit.test_export_layout import _occ, _subject
from tests.unit.test_export_match import exif_file

# The files each kept photo gives, per source and format (names as copied).
FILES = {
    ("imported", ExportFormat.RAW_JPEG): {"pair": ["DSC_0001.NEF", "DSC_0001.JPG"], "pair_missing_jpeg": ["DSC_0002.NEF"],
                                          "raw_only": ["DSC_0003.NEF"], "jpeg_only": ["DSC_0004.JPG"],
                                          "tiff": ["DSC_0005.TIF"], "png": ["DSC_0006.PNG"]},
    ("imported", ExportFormat.RAW): {"pair": ["DSC_0001.NEF"], "pair_missing_jpeg": ["DSC_0002.NEF"],
                                     "raw_only": ["DSC_0003.NEF"]},
    ("imported", ExportFormat.JPEG): {"pair": ["DSC_0001.JPG"], "jpeg_only": ["DSC_0004.JPG"]},
    ("external", ExportFormat.RAW_JPEG): {"pair": ["DSC_0001.NEF", "DSC_0001.JPG"],
                                          "pair_missing_jpeg": ["DSC_0002.NEF"], "raw_only": ["DSC_0003.NEF"],
                                          "jpeg_only": ["DSC_0004.NEF"]},
    ("external", ExportFormat.RAW): {"pair": ["DSC_0001.NEF"], "pair_missing_jpeg": ["DSC_0002.NEF"],
                                     "raw_only": ["DSC_0003.NEF"], "jpeg_only": ["DSC_0004.NEF"]},
    ("external", ExportFormat.JPEG): {"pair": ["DSC_0001.JPG"]},
}
# Issues expected: (photo, kind, status)
ISSUES = {
    ("imported", ExportFormat.RAW_JPEG): {("pair_missing_jpeg", "jpeg", "missing")},
    ("imported", ExportFormat.RAW): {("jpeg_only", "raw", "missing_format"), ("tiff", "raw", "missing_format"),
                                     ("png", "raw", "missing_format")},
    ("imported", ExportFormat.JPEG): {("pair_missing_jpeg", "jpeg", "missing"), ("raw_only", "jpeg", "missing_format"),
                                      ("tiff", "jpeg", "missing_format"), ("png", "jpeg", "missing_format")},
    ("external", ExportFormat.RAW_JPEG): {("pair_missing_jpeg", "jpeg", "missing"), ("raw_only", "jpeg", "missing"),
                                          ("jpeg_only", "jpeg", "missing"), ("tiff", None, "missing_format"),
                                          ("png", None, "missing_format")},
    ("external", ExportFormat.RAW): {("tiff", "raw", "missing"), ("png", "raw", "missing")},
    ("external", ExportFormat.JPEG): {("pair_missing_jpeg", "jpeg", "missing"), ("raw_only", "jpeg", "missing"),
                                      ("jpeg_only", "jpeg", "missing"), ("tiff", "jpeg", "missing"),
                                      ("png", "jpeg", "missing")},
}
SUBJECT_FOLDERS = {"pair": ["Lan", "Mai"], "jpeg_only": ["Mai"]}  # the others: Chưa xác định
MATCH = {"imported": {"imported"}, "external": {"content", "time"}}


@pytest.fixture(scope="module")
def session(tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    tmp = tmp_path_factory.mktemp("combos")
    fx = make_export_session(tmp)
    conn = fx.project.conn
    mai, lan = _subject(conn, "Mai"), _subject(conn, "Lan")
    _occ(conn, fx.ids["pair"], mai)
    _occ(conn, fx.ids["pair"], lan)
    _occ(conn, fx.ids["jpeg_only"], mai)
    conn.commit()
    card = tmp / "Thẻ nhớ"
    for name in ("DSC_0001.NEF", "DSC_0001.JPG", "DSC_0002.NEF", "DSC_0003.NEF"):
        (card / "DCIM" / "100NIKON").mkdir(parents=True, exist_ok=True)
        shutil.copy2(fx.root / name, card / "DCIM" / "100NIKON" / name)
    exif_file(card / "DCIM" / "100NIKON" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=4)  # by capture time
    exif_file(card / "DCIM" / "101NIKON" / "DSC_0004.NEF", "2026:10:20 09:00:00", seed=5)  # counter restart
    fx.card = card
    yield fx
    fx.project.close()


@pytest.mark.parametrize(("source", "fmt", "layout"), list(itertools.product(("imported", "external"), ExportFormat,
                                                                                 Layout)))
def test_twelve_combinations(session, tmp_path: Path, source: str, fmt: ExportFormat, layout: Layout) -> None:  # noqa: ANN001
    fx = session
    ids = select_assets(fx.project, Selection.KEEP)
    before = tree_digest(fx.root, fx.card)
    spec = SourceSpec()
    if source == "external":
        spec = SourceSpec("external", fx.card, scan_external(fx.card, session_folder=fx.project.folder,
                                                             destination=tmp_path / "out"))
    plan = plan_export(fx.project, ids, tmp_path / "out", source=spec, fmt=fmt, layout=layout)
    key_of = {aid: key for key, aid in fx.ids.items()}

    expected = set()
    for photo, names in FILES[(source, fmt)].items():
        folders = SUBJECT_FOLDERS.get(photo, [UNKNOWN_FOLDER]) if layout is Layout.SUBJECTS else [""]
        expected |= {f"{folder}/{name}" if folder else name for folder in folders for name in names}
    assert {op.dest_relative for op in plan.operations} == expected
    assert {(key_of[i.photo_id], i.kind, i.status.value) for i in plan.issues} == ISSUES[(source, fmt)]
    assert {op.match for op in plan.operations} <= MATCH[source]
    if source == "external":
        assert all(fx.card.resolve() in op.source.parents for op in plan.operations)  # only from the card
        assert not any(op.source_relative.startswith("DCIM/101NIKON") for op in plan.operations)  # the restart dup

    result = run_export(plan, options={"scope": "keep"})
    assert set(result.statuses.values()) == {"copied"} and not result.failed
    out = tmp_path / "out"
    on_disk = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()
               and "_kirapick_danh_sach" not in p.parts}
    assert on_disk == expected
    for op in plan.operations:
        assert (out / op.dest_relative).read_bytes() == op.source.read_bytes()
    with open(result.manifest_csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(plan.operations) + len(plan.issues)
    assert tree_digest(fx.root, fx.card) == before  # sources and the card untouched
    names = keep_names(fx.project.conn, ids, with_extension=True)
    assert names.lines == ["DSC_0001.NEF", "DSC_0002.NEF", "DSC_0003.NEF", "DSC_0004.JPG", "DSC_0005.TIF",
                           "DSC_0006.PNG"]  # independent of the three choices


def test_network_free() -> None:
    """The network-import guard (tests/unit/test_app_update.py) walks every module of app/, app/export included."""
    import ast

    root = Path(__file__).resolve().parents[2] / "app" / "export"
    modules = sorted(p.name for p in root.glob("*.py"))
    assert {"copy_export.py", "sources.py", "hashing.py", "names.py", "layout.py"} <= set(modules)
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any(n.split(".")[0] in {"urllib", "http", "socket", "ssl", "requests", "httpx"} for n in names)
