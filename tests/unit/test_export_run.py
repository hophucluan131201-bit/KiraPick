"""Part 3 Task 7 — verified copies, source revalidation, pairs at an occupied destination, disk space, manifest v2,
cancel and retry (spec §3.6, §3.7, §3.9, §12 RV-P3-B-01/02)."""

from __future__ import annotations

import csv
import errno
import json
import os
import shutil
from pathlib import Path

import pytest

from app.export import copy_export
from app.export.copy_export import (
    FAIL_FAST_AFTER,
    IssueStatus,
    Selection,
    plan_export,
    run_export,
    select_assets,
)
from app.export.formats import ExportFormat
from app.export.hashing import sha256_file
from app.export.sources import SourceSpec, scan_external
from app.storage import exports
from tests.fixtures_export import make_export_session, tree_digest, write_file
from tests.unit.test_export_match import exif_file


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


def _external(fx, card: Path, ids: list[int], **kw):  # noqa: ANN001, ANN003, ANN202
    index = scan_external(card, session_folder=fx.project.folder, destination=fx.dest)
    return plan_export(fx.project, ids, fx.dest, source=SourceSpec("external", card, index), **kw)


def _copy_to_card(fx, name: str) -> Path:  # noqa: ANN001
    target = fx.root.parent / "card" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fx.root / name, target)
    return target


def _rows(result) -> list[dict[str, str]]:  # noqa: ANN001
    with open(result.manifest_csv, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _rewrite_keep_mtime(path: Path, seed: int) -> None:
    st = path.stat()
    write_file(path, seed, st.st_size)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


# --- verification ------------------------------------------------------------------------------------------------

def test_verify_failure_removes_only_our_file(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    (fx.dest / "keep_me.txt").write_text("user file")
    real = copy_export.sha256_file

    def bad_target(path: Path, **kw) -> str:  # noqa: ANN003
        return "0" * 64 if fx.dest in path.parents else real(path, **kw)

    monkeypatch.setattr(copy_export, "sha256_file", bad_target)
    result = run_export(plan_export(fx.project, [fx.ids["raw_only"]], fx.dest))
    assert result.statuses == {"DSC_0003.NEF": "failed"} and "kiểm tra" in result.failed["DSC_0003.NEF"]
    assert not (fx.dest / "DSC_0003.NEF").exists() and (fx.dest / "keep_me.txt").read_text() == "user file"


def test_copy_hash_streamed_once(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    opened: list[str] = []
    real_open = open

    def spy(file, mode="r", *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        if str(file).startswith(str(fx.root)):
            opened.append(mode)
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr("builtins.open", spy)
    result = run_export(plan_export(fx.project, [fx.ids["raw_only"]], fx.dest))
    assert opened == ["rb"]  # the source is read once: copied and hashed from the same stream
    assert result.hashes["DSC_0003.NEF"] == sha256_file(fx.root / "DSC_0003.NEF")


def test_already_present_requires_full_hash(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    data = bytearray((fx.root / "DSC_0003.NEF").read_bytes())
    data[len(data) // 2] ^= 1
    (fx.dest / "DSC_0003.NEF").write_bytes(bytes(data))
    shutil.copyfile(fx.root / "DSC_0004.JPG", fx.dest / "DSC_0004.JPG")
    result = run_export(plan_export(fx.project, [fx.ids["raw_only"], fx.ids["jpeg_only"]], fx.dest))
    assert result.statuses == {"DSC_0003.NEF": "copied", "DSC_0004.JPG": "already_present"}
    assert result.renamed == {"DSC_0003.NEF": "DSC_0003 (1).NEF"}
    assert (fx.dest / "DSC_0003.NEF").read_bytes() == bytes(data)  # never overwritten
    rows = {r["exported_as"]: r for r in _rows(result)}
    assert rows["DSC_0004.JPG"]["status"] == "already_present"
    assert rows["DSC_0004.JPG"]["sha256"] == sha256_file(fx.root / "DSC_0004.JPG")


def test_already_present_reverified(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    shutil.copyfile(fx.root / "DSC_0003.NEF", fx.dest / "DSC_0003.NEF")
    plan = plan_export(fx.project, [fx.ids["raw_only"]], fx.dest)
    assert plan.already_present == ["DSC_0003.NEF"]
    _rewrite_keep_mtime(fx.dest / "DSC_0003.NEF", 77)  # changed after the preview
    before = (fx.dest / "DSC_0003.NEF").read_bytes()
    result = run_export(plan)
    assert result.copied == ["DSC_0003 (1).NEF"] and (fx.dest / "DSC_0003.NEF").read_bytes() == before


def test_never_overwrites_different_file(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    write_file(fx.dest / "DSC_0004.JPG", 999)
    before = tree_digest(fx.dest)
    plan = plan_export(fx.project, [fx.ids["jpeg_only"]], fx.dest)
    write_file(fx.dest / "DSC_0004 (1).JPG", 998)  # the planned free name is taken after the preview
    result = run_export(plan)
    assert result.renamed == {"DSC_0004 (1).JPG": "DSC_0004 (2).JPG"}
    after = tree_digest(fx.dest)
    for path, digest in before.items():
        assert after[path] == digest


# --- source revalidation -----------------------------------------------------------------------------------------

def _time_plan(fx):  # noqa: ANN001, ANN202
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:01")
    return card, _external(fx, card, [fx.ids["jpeg_only"]], fmt=ExportFormat.RAW)


def _manual_plan(fx):  # noqa: ANN001, ANN202
    card = fx.root.parent / "card"
    a = exif_file(card / "A" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=1)
    exif_file(card / "B" / "DSC_0004.NEF", "2026:10:25 16:00:00", seed=2)
    return a, _external(fx, card, [fx.ids["jpeg_only"]], fmt=ExportFormat.RAW,
                        confirmations={(fx.ids["jpeg_only"], "raw"): a.resolve()})


@pytest.mark.parametrize("how", ["size", "mtime"])
@pytest.mark.parametrize("match", ["imported", "content", "time", "manual"])
def test_source_changed_before_copy(fx, match: str, how: str, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    if match == "imported":
        plan = plan_export(fx.project, [fx.ids["raw_only"]], fx.dest)
    elif match == "content":
        _copy_to_card(fx, "DSC_0003.NEF")
        plan = _external(fx, fx.root.parent / "card", [fx.ids["raw_only"]])
    elif match == "time":
        _, plan = _time_plan(fx)
    else:
        _, plan = _manual_plan(fx)
    (op,) = plan.operations
    assert op.match == match
    if how == "size":
        with open(op.source, "ab") as fh:
            fh.write(b"x")
    else:
        st = op.source.stat()
        os.utime(op.source, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    monkeypatch.setattr(copy_export, "_copy_exclusive", lambda *a, **k: pytest.fail("copied a changed source"))
    result = run_export(plan)
    assert result.statuses == {op.dest_relative: "source_changed"}
    assert not (fx.dest / op.dest_relative).exists() and result.copied == []
    assert _rows(result)[0]["error"] == "File nguồn đã thay đổi sau khi xem trước"


def test_source_replaced_same_size_and_mtime(fx) -> None:  # noqa: ANN001
    card_file = _copy_to_card(fx, "DSC_0003.NEF")
    plan = _external(fx, card_file.parent, [fx.ids["raw_only"]])
    assert plan.operations[0].identity.sha256 is not None
    _rewrite_keep_mtime(card_file, 55)
    result = run_export(plan)
    assert result.statuses == {"DSC_0003.NEF": "source_changed"}
    assert not (fx.dest / "DSC_0003.NEF").exists()  # our new target removed


def test_time_match_revalidated_on_copy(fx) -> None:  # noqa: ANN001
    card, plan = _time_plan(fx)
    raw = card / "DSC_0004.NEF"
    st = raw.stat()
    exif_file(raw, "2026:10:25 16:00:31")  # another shot under the same name, 30 s later
    assert raw.stat().st_size == st.st_size  # same size; the modification time is restored below
    os.utime(raw, ns=(st.st_atime_ns, st.st_mtime_ns))
    result = run_export(plan)
    assert result.statuses == {"DSC_0004.NEF": "source_changed"} and not (fx.dest / "DSC_0004.NEF").exists()


def test_revalidation_limit_is_documented(fx) -> None:  # noqa: ANN001
    """Spec §3.9 known limit: a time-matched file rewritten in place with the same size, a restored mtime and the same
    capture metadata is copied. Pinned so a change to this limit is deliberate."""
    card, plan = _time_plan(fx)
    raw = card / "DSC_0004.NEF"
    data = bytearray(raw.read_bytes())
    data[-1] ^= 0xFF  # the last pixel byte: metadata unchanged
    st = raw.stat()
    raw.write_bytes(bytes(data))
    os.utime(raw, ns=(st.st_atime_ns, st.st_mtime_ns))
    result = run_export(plan)
    assert result.statuses == {"DSC_0004.NEF": "copied"}
    assert result.hashes["DSC_0004.NEF"] == sha256_file(fx.dest / "DSC_0004.NEF")  # what was really copied


# --- RV-P3-B-01: a RAW+JPEG pair at an occupied destination ------------------------------------------------------

def _pair_plan(fx):  # noqa: ANN001, ANN202
    return plan_export(fx.project, [fx.ids["pair"]], fx.dest)


def _differ(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 1  # same size, same head/tail: the plan cannot tell
    path.write_bytes(bytes(data))


def _seed_dest(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir(exist_ok=True)
    for name in ("DSC_0001.NEF", "DSC_0001.JPG"):
        shutil.copyfile(fx.root / name, fx.dest / name)


def test_pair_both_present_identical(fx) -> None:  # noqa: ANN001
    _seed_dest(fx)
    plan = _pair_plan(fx)
    assert sorted(plan.already_present) == ["DSC_0001.JPG", "DSC_0001.NEF"] and plan.to_copy == []
    result = run_export(plan)
    assert result.statuses == {"DSC_0001.NEF": "already_present", "DSC_0001.JPG": "already_present"}
    assert result.copied == [] and result.notes == {}


def test_pair_one_identical_one_different(fx) -> None:  # noqa: ANN001
    _seed_dest(fx)
    _differ(fx.dest / "DSC_0001.JPG")
    before = tree_digest(fx.dest)
    plan = _pair_plan(fx)
    assert sorted(plan.already_present) == ["DSC_0001.JPG", "DSC_0001.NEF"]  # the quick filter cannot tell
    result = run_export(plan)
    assert sorted(result.copied) == ["DSC_0001 (1).JPG", "DSC_0001 (1).NEF"]  # the whole pair, one new stem
    assert result.statuses == {"DSC_0001.NEF": "copied", "DSC_0001.JPG": "copied"}
    assert set(result.notes.values()) == {copy_export.NOTE_RELOCATED}
    after = tree_digest(fx.dest)
    assert all(after[p] == d for p, d in before.items())  # existing files untouched
    for name in ("DSC_0001.NEF", "DSC_0001.JPG"):
        stem, ext = name.split(".")
        assert sha256_file(fx.dest / f"{stem} (1).{ext}") == sha256_file(fx.root / name)


def test_pair_both_different(fx) -> None:  # noqa: ANN001
    _seed_dest(fx)
    _differ(fx.dest / "DSC_0001.JPG")
    _differ(fx.dest / "DSC_0001.NEF")
    result = run_export(_pair_plan(fx))
    assert sorted(result.copied) == ["DSC_0001 (1).JPG", "DSC_0001 (1).NEF"]
    assert result.renamed == {"DSC_0001.NEF": "DSC_0001 (1).NEF", "DSC_0001.JPG": "DSC_0001 (1).JPG"}


def test_pair_one_missing_at_destination(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    shutil.copyfile(fx.root / "DSC_0001.NEF", fx.dest / "DSC_0001.NEF")
    plan = _pair_plan(fx)
    assert plan.already_present == ["DSC_0001.NEF"] and [op.dest_relative for op in plan.to_copy] == ["DSC_0001.JPG"]
    result = run_export(plan)
    assert result.statuses == {"DSC_0001.NEF": "already_present", "DSC_0001.JPG": "copied"}
    assert result.copied == ["DSC_0001.JPG"] and result.notes == {}  # one stem: the pair is complete


def test_pair_one_identical_one_missing_then_name_taken(fx) -> None:  # noqa: ANN001
    fx.dest.mkdir()
    shutil.copyfile(fx.root / "DSC_0001.NEF", fx.dest / "DSC_0001.NEF")
    plan = _pair_plan(fx)
    write_file(fx.dest / "DSC_0001.JPG", 5)  # another program takes the JPEG's name after the preview
    result = run_export(plan)
    assert sorted(result.copied) == ["DSC_0001 (1).JPG", "DSC_0001 (1).NEF"]  # never NEF at one stem, JPEG at another
    assert result.notes["DSC_0001.NEF"] == copy_export.NOTE_RELOCATED


def test_pair_race_removes_only_our_files(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    plan = _pair_plan(fx)
    real = copy_export._copy_exclusive
    fired = []

    def racing(src: Path, root: Path, rel: str, **kw):  # noqa: ANN003, ANN202
        if rel == "DSC_0001.JPG" and not fired:
            fired.append(1)
            write_file(root / rel, 6)  # appears between our two creates
        return real(src, root, rel, **kw)

    monkeypatch.setattr(copy_export, "_copy_exclusive", racing)
    result = run_export(plan)
    assert sorted(result.copied) == ["DSC_0001 (1).JPG", "DSC_0001 (1).NEF"]
    names = sorted(p.name for p in fx.dest.iterdir() if p.is_file())
    assert names == ["DSC_0001 (1).JPG", "DSC_0001 (1).NEF", "DSC_0001.JPG"]  # our first NEF was rolled back
    assert (fx.dest / "DSC_0001.JPG").read_bytes() == write_file(fx.root.parent / "x", 6).read_bytes()


def test_pair_member_source_changed_is_reported_incomplete(fx) -> None:  # noqa: ANN001
    plan = _pair_plan(fx)
    with open(fx.root / "DSC_0001.JPG", "ab") as fh:
        fh.write(b"x")
    result = run_export(plan)
    assert result.statuses == {"DSC_0001.NEF": "copied", "DSC_0001.JPG": "source_changed"}
    assert result.notes["DSC_0001.NEF"] == copy_export.NOTE_INCOMPLETE


def test_group_with_two_files_of_one_extension_keeps_distinct_names(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    from tests.fixtures_export import add_asset

    conn = fx.project.conn
    source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
    group = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
    first = add_asset(fx.project, source_id, fx.root, "DSC_0099.JPG", seed=501, kind="raster", pair_group=group)
    add_asset(fx.project, source_id, fx.root, "DSC_0099_alt.JPG", seed=502, kind="raster", pair_group=group)
    fx.dest.mkdir()
    write_file(fx.dest / "DSC_0099.JPG", 503)
    plan = plan_export(fx.project, [first], fx.dest)
    assert [op.dest_relative for op in plan.operations] == ["DSC_0099 (1).JPG", "DSC_0099_alt.JPG"]
    write_file(fx.dest / "DSC_0099 (1).JPG", 504)  # taken after the preview: the group moves
    result = run_export(plan)
    assert sorted(result.copied) == ["DSC_0099 (2).JPG", "DSC_0099_alt (2).JPG"]
    assert set(result.statuses.values()) == {"copied"}


# --- RV-P3-B-02: disk space --------------------------------------------------------------------------------------

def test_estimated_and_worst_case_bytes(fx) -> None:  # noqa: ANN001
    _seed_dest(fx)
    plan = plan_export(fx.project, [fx.ids["pair"], fx.ids["jpeg_only"]], fx.dest)
    assert plan.estimated_bytes == plan.total_bytes == 300_000  # only DSC_0004.JPG seems missing
    assert plan.worst_case_bytes == 500_000 + 300_000 + 300_000  # every seemingly present target may differ


def test_free_space_rechecked_before_extra_copy(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    _seed_dest(fx)
    _differ(fx.dest / "DSC_0001.JPG")
    plan = _pair_plan(fx)
    assert plan.estimated_bytes == 0
    before = tree_digest(fx.dest)
    monkeypatch.setattr(copy_export, "free_space", lambda _p: 700_000)  # less than the pair (800 000)
    result = run_export(plan)
    assert result.statuses == {"DSC_0001.NEF": "already_present", "DSC_0001.JPG": "failed"}  # spec §12 step 5
    assert result.failed == {"DSC_0001.JPG": copy_export.NO_SPACE}
    assert result.notes == {"DSC_0001.NEF": copy_export.NOTE_INCOMPLETE, "DSC_0001.JPG": copy_export.NOTE_INCOMPLETE}
    photos = {p: d for p, d in tree_digest(fx.dest).items() if copy_export.MANIFEST_DIR not in p}
    assert photos == before  # nothing written, nothing overwritten or removed (only the export list was added)


# --- cancel, failures, retry ---------------------------------------------------------------------------------------

def test_cancel_writes_not_started(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, select_assets(fx.project, Selection.KEEP), fx.dest)
    stop: list[int] = []  # Dừng pressed once the first photo is done
    result = run_export(plan, should_cancel=lambda: bool(stop), progress=lambda done, _total: stop.append(done))
    assert result.cancelled
    statuses = list(result.statuses.values())
    assert statuses.count("copied") >= 1 and "not_started" in statuses and len(statuses) == len(plan.operations)
    assert {r["status"] for r in _rows(result)} >= {"copied", "not_started", "missing"}


def test_partial_failure_continues_and_retry_copies_only_missing(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    ids = select_assets(fx.project, Selection.KEEP)
    bad = str(fx.root / "DSC_0004.JPG")
    real_open = open

    def denied(file, mode="r", *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        if str(file) == bad and "r" in mode:
            raise PermissionError(errno.EACCES, "Permission denied")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr("builtins.open", denied)
    first = run_export(plan_export(fx.project, ids, fx.dest))
    assert first.statuses["DSC_0004.JPG"] == "failed" and list(first.failed) == ["DSC_0004.JPG"]
    assert sum(s == "copied" for s in first.statuses.values()) == len(first.statuses) - 1
    monkeypatch.setattr("builtins.open", real_open)
    second = run_export(plan_export(fx.project, ids, fx.dest))
    assert second.copied == ["DSC_0004.JPG"]
    assert sum(s == "already_present" for s in second.statuses.values()) == len(second.statuses) - 1


def test_source_vanishes_after_preview(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    for name in ("DSC_0001.NEF", "DSC_0001.JPG", "DSC_0003.NEF", "DSC_0004.JPG", "DSC_0002.NEF"):
        _copy_to_card(fx, name)
    plan = _external(fx, card, select_assets(fx.project, Selection.KEEP))
    assert len(plan.operations) == 5
    shutil.rmtree(card)  # the card is ejected
    result = run_export(plan)
    assert result.source_unavailable
    assert set(result.statuses.values()) == {"failed"} and result.copied == []
    assert list(result.failed.values()).count(copy_export.SOURCE_GONE) == len(plan.operations)
    assert FAIL_FAST_AFTER == 3 and result.manifest_csv is not None


def test_copied_files_stay_when_source_vanishes_midway(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    for name in ("DSC_0003.NEF", "DSC_0004.JPG", "DSC_0001.NEF", "DSC_0001.JPG"):
        _copy_to_card(fx, name)
    plan = _external(fx, card, [fx.ids["raw_only"], fx.ids["jpeg_only"], fx.ids["pair"]])
    real = copy_export._copy_exclusive

    def eject_after_first(src: Path, root: Path, rel: str, **kw):  # noqa: ANN003, ANN202
        out = real(src, root, rel, **kw)
        shutil.rmtree(card, ignore_errors=True)
        return out

    monkeypatch.setattr(copy_export, "_copy_exclusive", eject_after_first)
    result = run_export(plan)
    assert result.copied == [plan.operations[0].dest_relative] and (fx.dest / result.copied[0]).is_file()
    assert result.source_unavailable


# --- manifest v2 -----------------------------------------------------------------------------------------------------

MANIFEST_COLUMNS = ["status", "exported_as", "folder", "photo", "kind", "source", "match", "size_bytes", "sha256",
                    "flag", "rating", "favorite", "capture_time", "camera", "error", "note"]


def test_manifest_rows_cover_ops_and_issues(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "Thẻ nhớ A"
    for name in ("DSC_0001.NEF", "DSC_0003.NEF"):
        _copy_to_card(fx, name)
    (fx.root.parent / "card").rename(card)
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:01")
    plan = _external(fx, card, select_assets(fx.project, Selection.KEEP))
    result = run_export(plan, options={"scope": "keep"})
    rows = _rows(result)
    assert list(rows[0]) == MANIFEST_COLUMNS
    assert len(rows) == len(plan.operations) + len(plan.issues)
    assert sorted(r["status"] for r in rows if r["exported_as"]) == ["copied"] * len(plan.operations)
    issue_statuses = sorted(r["status"] for r in rows if not r["exported_as"])
    assert issue_statuses == sorted(i.status.value for i in plan.issues)
    assert all(r["source"].startswith("Thẻ nhớ A/") for r in rows if r["exported_as"])
    data = json.loads(result.manifest_json.read_text(encoding="utf-8"))
    assert set(data) == {"app_version", "exported_at", "options", "counts", "rows"}
    assert data["options"] == {"scope": "keep", "source": "external", "source_folder": "Thẻ nhớ A",
                               "format": "raw_jpeg", "layout": "single"}
    assert str(card) not in result.manifest_json.read_text(encoding="utf-8")  # the folder name only
    assert data["counts"]["copied"] == len(plan.operations)
    assert data["rows"] == rows or len(data["rows"]) == len(rows)


def test_manifest_match_words(fx) -> None:  # noqa: ANN001
    imported = run_export(plan_export(fx.project, [fx.ids["raw_only"]], fx.dest / "a"))
    assert [r["match"] for r in _rows(imported)] == ["imported"]
    card = fx.root.parent / "card"
    _copy_to_card(fx, "DSC_0003.NEF")
    content = run_export(_external(fx, card, [fx.ids["raw_only"]]))
    assert [r["match"] for r in _rows(content) if r["exported_as"]] == ["content"]
    shutil.rmtree(card)
    for words, (plan_fn) in (("time", _time_plan), ("manual", _manual_plan)):
        shutil.rmtree(card, ignore_errors=True)
        _, plan = plan_fn(fx)
        plan.destination = fx.dest / words
        result = run_export(plan)
        assert [r["match"] for r in _rows(result) if r["exported_as"]] == [words]


def test_manifest_written_when_nothing_copied(fx) -> None:  # noqa: ANN001
    result = run_export(plan_export(fx.project, [fx.ids["raw_only"]], fx.dest), should_cancel=lambda: True)
    assert result.cancelled and result.copied == []
    assert [r["status"] for r in _rows(result)] == ["not_started"]


def test_export_runs_counts_subject_duplicates(fx) -> None:  # noqa: ANN001
    from app.export.layout import Layout
    from tests.unit.test_export_layout import _occ, _subject

    conn = fx.project.conn
    a, b = _subject(conn, "Mai"), _subject(conn, "Lan")
    _occ(conn, fx.ids["pair"], a)
    _occ(conn, fx.ids["pair"], b)
    plan = plan_export(fx.project, [fx.ids["pair"]], fx.dest, layout=Layout.SUBJECTS)
    result = run_export(plan)
    assert len(result.copied) == 4  # files: the pair in two folders
    assert exports.photo_count(conn, result.copied_ids) == 1  # photos: distinct


def test_issue_rows_keep_their_status(fx) -> None:  # noqa: ANN001
    result = run_export(plan_export(fx.project, [fx.ids["tiff"]], fx.dest, fmt=ExportFormat.JPEG))
    (row,) = _rows(result)
    assert (row["status"], row["kind"], row["error"]) == (IssueStatus.MISSING_FORMAT.value, "jpeg", "Thiếu JPEG")


# --- RV-P3-C01 / C04: cancel inside a large file; second member of a pair fails ------------------------------------

BIG = 3 * 1024 * 1024 + 123


def _big_pair(fx) -> int:  # noqa: ANN001
    from tests.fixtures_export import add_asset

    conn = fx.project.conn
    source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
    group = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
    raw = add_asset(fx.project, source_id, fx.root, "DSC_0098.NEF", seed=601, kind="raw", pair_group=group, size=BIG)
    add_asset(fx.project, source_id, fx.root, "DSC_0098.JPG", seed=602, kind="raster", pair_group=group, size=BIG)
    conn.commit()
    return raw


def _photo_files(dest: Path) -> list[str]:
    return sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")
                  if p.is_file() and copy_export.MANIFEST_DIR not in p.parts)


def _cancel_after_chunks(n: int):  # noqa: ANN202
    calls = [0]

    def should_cancel() -> bool:
        calls[0] += 1
        return calls[0] > n

    return should_cancel


def test_cancel_inside_a_large_file_removes_the_partial_file(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, [_big_pair(fx)], fx.dest)
    result = run_export(plan, should_cancel=_cancel_after_chunks(2))  # group check + 1st chunk, then stop
    assert result.cancelled and result.copied == []
    assert _photo_files(fx.dest) == []  # the half-written NEF is gone
    assert result.statuses == {"DSC_0098.NEF": "not_started", "DSC_0098.JPG": "not_started"}
    assert [r["status"] for r in _rows(result)] == ["not_started", "not_started"]


def test_cancel_inside_the_second_file_rolls_back_the_pair(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, [_big_pair(fx)], fx.dest)
    real, finished = copy_export._copy_exclusive, []

    def spy(src: Path, root: Path, rel: str, **kw):  # noqa: ANN003, ANN202
        out = real(src, root, rel, **kw)
        finished.append(rel)
        return out

    monkeypatch.setattr(copy_export, "_copy_exclusive", spy)
    result = run_export(plan, should_cancel=_cancel_after_chunks(1 + 4 + 1))  # NEF done (4 chunks), stop in the JPEG
    assert finished == ["DSC_0098.NEF"]  # the NEF was complete on disk before the stop
    assert result.cancelled and result.copied == [] and _photo_files(fx.dest) == []  # never half a pair
    assert set(result.statuses.values()) == {"not_started"}


def test_second_member_fails_after_the_first_was_written(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    plan = _pair_plan(fx)
    real = copy_export._copy_exclusive

    def full_disk(src: Path, root: Path, rel: str, **kw):  # noqa: ANN003, ANN202
        if rel.endswith(".JPG"):
            (root / rel).write_bytes(b"partial")  # what a failing write leaves …
            (root / rel).unlink()  # … and removes (as _copy_exclusive does)
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(src, root, rel, **kw)

    monkeypatch.setattr(copy_export, "_copy_exclusive", full_disk)
    result = run_export(plan)
    assert result.statuses == {"DSC_0001.NEF": "copied", "DSC_0001.JPG": "failed"}
    assert result.failed == {"DSC_0001.JPG": "No space left on device"}
    assert _photo_files(fx.dest) == ["DSC_0001.NEF"]
    rows = {r["kind"]: r for r in _rows(result)}
    assert rows["raw"]["note"] == rows["jpeg"]["note"] == copy_export.NOTE_INCOMPLETE
    assert rows["jpeg"]["exported_as"] == "" and rows["jpeg"]["sha256"] == ""
    assert rows["raw"]["sha256"] == sha256_file(fx.dest / "DSC_0001.NEF")


def test_second_member_name_race_then_cancel(fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, [_big_pair(fx)], fx.dest)
    real = copy_export._copy_exclusive
    stop = []

    def race_then_stop(src: Path, root: Path, rel: str, **kw):  # noqa: ANN003, ANN202
        if rel == "DSC_0098.JPG" and not stop:
            write_file(root / rel, 7)  # another program takes the JPEG's name …
            stop.append(1)  # … and the user presses Dừng while the pair is moved to "(1)"
        return real(src, root, rel, **kw)

    monkeypatch.setattr(copy_export, "_copy_exclusive", race_then_stop)
    result = run_export(plan, should_cancel=lambda: len(stop) > 0 and stop.append(1) is None and len(stop) > 3)
    assert result.cancelled and result.copied == []
    assert _photo_files(fx.dest) == ["DSC_0098.JPG"]  # only the other program's file; ours rolled back
    assert set(result.statuses.values()) == {"not_started"}
    rows = _rows(result)
    assert [r["status"] for r in rows] == ["not_started", "not_started"] and all(not r["exported_as"] for r in rows)
