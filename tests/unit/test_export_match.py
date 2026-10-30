"""Part 3 Task 6 — files of the session's photos found on another folder (spec §3.3 points 2–6, §12 RV-P3-B-03).

RAW stand-ins on the "card" are small TIFF files with a .NEF name and real EXIF (ExifRead reads them like a RAW
header); imported files come from tests/fixtures_export (capture time 2026-10-25 16:00:00, camera "NIKON Z 5")."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.export.copy_export import IssueStatus, plan_export, select_assets, Selection
from app.export.formats import ExportFormat
from app.export.hashing import HashCache, sha256_file
from app.export.photos import load_photos
from app.export.sources import ExternalIndex, SourceSpec, match_file, scan_external
from app.ingest import metadata as md
from app.ingest.metadata import read_metadata
from app.storage import decisions
from tests.fixtures_export import add_asset, make_export_session, write_file


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


def exif_file(path: Path, taken: str | None = "2026:10:25 16:00:00", *, subsec: str | None = None,
              make: str = "NIKON", model: str = "Z 5", seed: int = 0) -> Path:
    """A small image with EXIF; TIFF bytes under a RAW name, JPEG otherwise."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    if taken is not None:
        exif[md.MAKE], exif[md.MODEL] = make, model
        ifd = exif.get_ifd(md.EXIF_IFD_POINTER)
        ifd[md.DATETIME_ORIGINAL] = taken
        if subsec is not None:
            ifd[md.SUBSEC_ORIGINAL] = subsec
    fmt = "JPEG" if path.suffix.lower() in (".jpg", ".jpeg") else "TIFF"
    Image.new("RGB", (16, 16), (seed % 256, 7, 9)).save(path, fmt, exif=exif.tobytes())
    return path


def _index(fx, card: Path) -> ExternalIndex:  # noqa: ANN001
    return scan_external(card, session_folder=fx.project.folder, destination=fx.dest)


def _photo(fx, key: str):  # noqa: ANN001, ANN202
    return load_photos(fx.project.conn, [fx.ids[key]])[0]


def _copy(fx, key: str, card_rel: str, *, kind_index: int = 0) -> Path:  # noqa: ANN001
    src = fx.root / _photo(fx, key).files[kind_index].relative_path
    target = fx.root.parent / "card" / card_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    return target


def _flip_middle(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))


# --- same format: content proof ---------------------------------------------------------------------------------

def test_same_format_content_match(fx) -> None:  # noqa: ANN001
    card_file = _copy(fx, "raw_only", "DCIM/DSC_0003.NEF")
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card_file.parents[1]), hashes=HashCache())
    assert (m.status, m.method, m.file, m.duplicates) == ("matched", "content", card_file.resolve(), 0)
    assert m.reference_asset_id == fx.ids["raw_only"]
    assert m.identity is not None and m.identity.sha256 == sha256_file(card_file)
    assert m.identity.size == card_file.stat().st_size and m.identity.mtime_ns == card_file.stat().st_mtime_ns


def test_same_format_content_differs(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    write_file(card / "DSC_0003.NEF", 999, 123_456)
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "content_differs" and m.file is None and len(m.candidates) == 1


def test_middle_byte_differs_is_not_a_match(fx) -> None:  # noqa: ANN001
    card_file = _copy(fx, "raw_only", "DSC_0003.NEF")
    _flip_middle(card_file)  # same size, same head and tail: passes the quick filter
    cache = HashCache()
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card_file.parent), hashes=cache)
    assert m.status == "content_differs"
    assert cache.reads == 2  # the full proof was needed and ran on both files


def test_identical_duplicates_resolved(fx) -> None:  # noqa: ANN001
    a = _copy(fx, "raw_only", "A/DSC_0003.NEF")
    _copy(fx, "raw_only", "BACKUP/DSC_0003.NEF")
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, a.parents[1]), hashes=HashCache())
    assert (m.status, m.method, m.duplicates) == ("matched", "content", 1)
    assert m.file == a.resolve()  # shortest path first


def test_head_tail_equal_duplicates_not_resolved(fx) -> None:  # noqa: ANN001
    good = _copy(fx, "raw_only", "BACKUP_LONGER/DSC_0003.NEF")
    edited = _copy(fx, "raw_only", "A/DSC_0003.NEF")
    _flip_middle(edited)
    card = good.parents[1]
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card), hashes=HashCache())
    assert (m.status, m.file, m.duplicates) == ("matched", good.resolve(), 0)  # the edited one never counts
    _flip_middle(good)
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "content_differs"


def test_each_file_hashed_once(fx) -> None:  # noqa: ANN001
    a = _copy(fx, "raw_only", "A/DSC_0003.NEF")
    _copy(fx, "raw_only", "B/DSC_0003.NEF")
    cache, index, photo = HashCache(), _index(fx, a.parents[1]), _photo(fx, "raw_only")
    for _ in range(3):
        match_file(photo, "raw", index, hashes=cache)
    assert cache.reads == 3  # the imported file and the two copies, once each


def test_imported_file_gone_cannot_prove_content(fx) -> None:  # noqa: ANN001
    card_file = _copy(fx, "raw_only", "DSC_0003.NEF")
    (fx.root / "DSC_0003.NEF").unlink()
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card_file.parent), hashes=HashCache())
    assert m.status == "ambiguous" and "không còn" in m.detail  # passes the filter, proof impossible: user decides
    m = match_file(_photo(fx, "raw_only"), "raw", _index(fx, card_file.parent), hashes=HashCache(),
                   recorded_sha={fx.ids["raw_only"]: sha256_file(card_file)})
    assert (m.status, m.method) == ("matched", "content")  # the hash the import recorded is a proof


# --- cross format: capture time ---------------------------------------------------------------------------------

def _set_photo(fx, key: str, *, time: str | None = "2026-10-25T16:00:00", subsec: str | None = None) -> None:  # noqa: ANN001
    for aid in fx.files[key]:
        fx.project.conn.execute("UPDATE assets SET capture_time = ?, subsec = ? WHERE id = ?", (time, subsec, aid))


def test_cross_format_within_tolerance(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    f = exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:02")
    m = match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache())
    assert (m.status, m.method, m.file) == ("matched", "time", f.resolve())
    assert m.reference_asset_id == fx.ids["jpeg_only"]  # the photo's own asset: its time and camera
    assert m.identity is not None and m.identity.sha256 is None  # not hashed at planning (documented limit)


def test_cross_format_just_outside(fx) -> None:  # noqa: ANN001
    _set_photo(fx, "jpeg_only", subsec="00")
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:02", subsec="01")
    m = match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "not_matched"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:02", subsec="00")
    assert match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache()).status == "matched"


def test_subseconds_used(fx) -> None:  # noqa: ANN001
    _set_photo(fx, "jpeg_only", time="2026-10-25T16:00:01", subsec="10")
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:03", subsec="50")  # whole seconds: 2 s; with subseconds 2.4 s
    assert match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache()).status == "not_matched"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:03")  # one side without subseconds: whole seconds
    assert match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache()).status == "matched"


def test_unknown_time_is_ambiguous(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004.NEF", None)
    m = match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "ambiguous" and m.candidates[0].capture_time is None
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:00")
    _set_photo(fx, "jpeg_only", time=None)
    assert match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache()).status == "ambiguous"


def test_two_valid_is_ambiguous(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    exif_file(card / "A" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=1)
    exif_file(card / "B" / "DSC_0004.NEF", "2026:10:25 15:59:59", seed=2)
    m = match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "ambiguous" and m.file is None and len(m.candidates) == 2


def test_camera_mismatch_not_matched(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:00", model="Z 6")
    assert match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache()).status == "not_matched"


def test_stem_variants_not_candidates(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004 (1).NEF")
    exif_file(card / "DSC_0004-Edit.NEF")
    m = match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "missing" and m.candidates == ()


def test_counter_restart_three_times(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    exif_file(card / "100NIKON" / "DSC_0004.NEF", "2026:10:20 09:00:00", seed=1)
    right = exif_file(card / "101NIKON" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=2)
    exif_file(card / "102NIKON" / "DSC_0004.NEF", "2026:10:28 18:00:00", seed=3)
    index = _index(fx, card)
    m = match_file(_photo(fx, "jpeg_only"), "raw", index, hashes=HashCache())
    assert (m.status, m.file) == ("matched", right.resolve())
    right.unlink()
    m = match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache())
    assert m.status == "not_matched"  # "Không khớp", never "Không chắc"


def test_manual_confirmation(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    a = exif_file(card / "A" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=1)
    exif_file(card / "B" / "DSC_0004.NEF", "2026:10:25 15:59:59", seed=2)
    index, photo = _index(fx, card), _photo(fx, "jpeg_only")
    m = match_file(photo, "raw", index, hashes=HashCache(), confirmed=a.resolve())
    assert (m.status, m.method, m.file) == ("matched", "manual", a.resolve())
    assert m.identity is not None and (m.identity.size, m.identity.mtime_ns) == (a.stat().st_size, a.stat().st_mtime_ns)
    m = match_file(photo, "raw", index, hashes=HashCache(), confirmed=fx.root / "DSC_0004.JPG")
    assert m.status == "ambiguous"  # a path that is not a candidate is ignored


def test_metadata_read_only_for_candidates(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    for i, folder in enumerate(("100NIKON", "101NIKON", "102NIKON")):
        exif_file(card / folder / "DSC_0004.NEF", f"2026:10:2{i} 09:00:00", seed=i)
    for n in range(10, 30):
        exif_file(card / f"DSC_00{n}.NEF", seed=n)  # other photos on the card: never read
    calls: list[Path] = []

    def spy(path: Path, **kw):  # noqa: ANN003, ANN202
        calls.append(path)
        return read_metadata(path, **kw)

    match_file(_photo(fx, "jpeg_only"), "raw", _index(fx, card), hashes=HashCache(), read_meta=spy)
    assert len(calls) == 3
    _copy(fx, "raw_only", "DSC_0003.NEF")
    calls.clear()
    match_file(_photo(fx, "raw_only"), "raw", _index(fx, card), hashes=HashCache(), read_meta=spy)
    assert calls == []  # same format: content, no metadata


# --- planning in External mode ----------------------------------------------------------------------------------

def _plan(fx, card: Path, keys: list[str] | None = None, **kw):  # noqa: ANN001, ANN003, ANN202
    ids = [fx.ids[k] for k in keys] if keys else select_assets(fx.project, Selection.KEEP)
    return plan_export(fx.project, ids, fx.dest, source=SourceSpec("external", card, _index(fx, card)), **kw)


def test_external_root_is_the_imported_folder(fx) -> None:  # noqa: ANN001
    plan = _plan(fx, fx.root)
    rows = sorted((op.source_relative, op.kind, op.match) for op in plan.operations)
    assert rows == [("DSC_0001.JPG", "jpeg", "content"), ("DSC_0001.NEF", "raw", "content"),
                    ("DSC_0002.NEF", "raw", "content"), ("DSC_0003.NEF", "raw", "content"),
                    ("DSC_0004.JPG", "jpeg", "content")]  # each file once, proven by content
    issues = {(fx.project.conn.execute("SELECT relative_path FROM assets WHERE id = ?", (i.photo_id,)).fetchone()[0],
               i.kind, i.status) for i in plan.issues}
    assert ("DSC_0002.NEF", "jpeg", IssueStatus.MISSING) in issues  # the JPEG deleted from disk
    assert ("DSC_0005.TIF", None, IssueStatus.MISSING_FORMAT) in issues
    assert ("DSC_0006.PNG", None, IssueStatus.MISSING_FORMAT) in issues
    detail = {i.detail for i in plan.issues if i.status is IssueStatus.MISSING_FORMAT}
    assert detail == {"định dạng này chỉ lấy được từ thư mục đã nhập"}
    with pytest.raises(Exception, match="đích"):  # the destination may not be inside the chosen source
        plan_export(fx.project, [fx.ids["pair"]], fx.root / "Xuất",
                    source=SourceSpec("external", fx.root, _index(fx, fx.root)))


def test_external_mode_takes_files_only_from_the_card(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    _copy(fx, "pair", "DSC_0001.NEF")  # the card holds only the RAW; the JPEG was imported
    plan = _plan(fx, card, ["pair"])
    assert [(op.kind, op.match) for op in plan.operations] == [("raw", "content")]
    (note,) = plan.issues
    assert (note.kind, note.status, note.detail) == ("jpeg", IssueStatus.MISSING, "JPEG không có tại nguồn được chọn")
    _copy(fx, "pair", "DSC_0001.JPG", kind_index=1)  # RAW and JPEG on the card
    plan = _plan(fx, card, ["pair"])
    assert sorted((op.kind, op.match) for op in plan.operations) == [("jpeg", "content"), ("raw", "content")]
    assert plan.issues == []
    (card / "DSC_0001.NEF").unlink()  # only the JPEG
    plan = _plan(fx, card, ["pair"])
    assert [(op.kind, op.match) for op in plan.operations] == [("jpeg", "content")]
    assert [i.detail for i in plan.issues] == ["RAW không có tại nguồn được chọn"]


def test_no_operation_reads_from_the_imported_root_in_external_mode(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    for key, rel in (("pair", "DSC_0001.NEF"), ("raw_only", "DSC_0003.NEF"), ("jpeg_only", "DSC_0004.JPG")):
        _copy(fx, key, rel)
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:01")
    plan = _plan(fx, card)
    assert len(plan.operations) == 4
    for op in plan.operations:
        assert card.resolve() in op.source.parents
    assert {op.match for op in plan.operations} == {"content", "time"}


def test_external_needs_a_scan(fx) -> None:  # noqa: ANN001
    with pytest.raises(Exception, match="quét"):
        plan_export(fx.project, [fx.ids["pair"]], fx.dest, source=SourceSpec("external", fx.root))


def test_confirmations_reach_the_plan(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    a = exif_file(card / "A" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=1)
    exif_file(card / "B" / "DSC_0004.NEF", "2026:10:25 15:59:59", seed=2)
    plan = _plan(fx, card, ["jpeg_only"], fmt=ExportFormat.RAW)
    assert [i.status for i in plan.issues] == [IssueStatus.AMBIGUOUS] and len(plan.issues[0].candidates) == 2
    plan = _plan(fx, card, ["jpeg_only"], fmt=ExportFormat.RAW,
                 confirmations={(fx.ids["jpeg_only"], "raw"): a.resolve()})
    assert [(op.source, op.match, op.asset_id) for op in plan.operations] == [(a.resolve(), "manual",
                                                                               fx.ids["jpeg_only"])]


# --- RV-P3-B-03: photo identity, input order, counter restarts ---------------------------------------------------

def _ops(plan) -> list[tuple]:  # noqa: ANN001
    return sorted((op.kind, op.source_relative, op.asset_id, op.match, op.dest_relative) for op in plan.operations)


def test_input_order_raw_jpeg_same_match(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    _copy(fx, "pair", "DSC_0001.NEF")
    _copy(fx, "pair", "DSC_0001.JPG", kind_index=1)
    raw, jpg = fx.files["pair"]
    plans = [plan_export(fx.project, ids, fx.dest, source=SourceSpec("external", card, _index(fx, card)))
             for ids in ([raw, jpg], [jpg, raw], [jpg])]
    assert _ops(plans[0]) == _ops(plans[1]) == _ops(plans[2])
    refs = {op.kind: op.asset_id for op in plans[0].operations}
    assert refs == {"raw": raw, "jpeg": jpg}  # each file proven against the imported file of its own kind
    assert [op.photo_id for op in plans[1].operations] == [jpg, jpg]  # legacy identity: the first id given


def test_scan_order_does_not_matter(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    exif_file(card / "A" / "DSC_0004.NEF", "2026:10:20 16:00:01", seed=1)
    exif_file(card / "B" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=2)
    _copy(fx, "raw_only", "Z/DSC_0003.NEF")
    _copy(fx, "raw_only", "Y/DSC_0003.NEF")
    index = _index(fx, card)
    flipped = ExternalIndex(index.root, {k: list(reversed(v)) for k, v in reversed(list(index.by_stem.items()))},
                            index.files, index.skipped)
    ids = [fx.ids["jpeg_only"], fx.ids["raw_only"]]
    a = plan_export(fx.project, ids, fx.dest, source=SourceSpec("external", card, index), fmt=ExportFormat.RAW)
    b = plan_export(fx.project, ids, fx.dest, source=SourceSpec("external", card, flipped), fmt=ExportFormat.RAW)
    assert _ops(a) == _ops(b) and len(a.operations) == 2


def _second_shoot(fx, rel: str, time: str) -> int:  # noqa: ANN001
    source_id = fx.project.conn.execute("SELECT id FROM sources").fetchone()[0]
    aid = add_asset(fx.project, source_id, fx.root, rel, seed=401, kind="raster", capture_time=time)
    decisions.set_flag(fx.project.conn, aid, "keep")
    return aid


def test_counter_restart_two_photos_same_stem(fx) -> None:  # noqa: ANN001
    other = _second_shoot(fx, "Buổi 2/DSC_0004.JPG", "2026-10-26T10:00:00")
    card = fx.root.parent / "card"
    first = exif_file(card / "100NIKON" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=1)
    second = exif_file(card / "101NIKON" / "DSC_0004.NEF", "2026:10:26 10:00:00", seed=2)
    plan = plan_export(fx.project, [fx.ids["jpeg_only"], other], fx.dest, fmt=ExportFormat.RAW,
                       source=SourceSpec("external", card, _index(fx, card)))
    got = {op.photo_id: op.source for op in plan.operations}
    assert got == {fx.ids["jpeg_only"]: first.resolve(), other: second.resolve()}  # never combined by name
    assert len({op.dest_relative for op in plan.operations}) == 2


def test_one_card_file_valid_for_two_photos_is_ambiguous(fx) -> None:  # noqa: ANN001
    other = _second_shoot(fx, "Buổi 2/DSC_0004.JPG", "2026-10-25T16:00:01")
    card = fx.root.parent / "card"
    exif_file(card / "DSC_0004.NEF", "2026:10:25 16:00:01")
    plan = plan_export(fx.project, [fx.ids["jpeg_only"], other], fx.dest, fmt=ExportFormat.RAW,
                       source=SourceSpec("external", card, _index(fx, card)))
    assert plan.operations == []
    assert [(i.status, i.detail) for i in plan.issues] == [(IssueStatus.AMBIGUOUS, "file này khớp với nhiều ảnh")] * 2


def test_decisions_come_from_the_session_not_the_card(fx) -> None:  # noqa: ANN001
    card = fx.root.parent / "card"
    _copy(fx, "rejected", "DSC_0007.JPG")  # a rejected photo's file on the card is never picked up
    _copy(fx, "raw_only", "DSC_0003.NEF")
    plan = _plan(fx, card)
    assert {op.source_relative for op in plan.operations} == {"DSC_0003.NEF"}
    assert plan.photos[fx.ids["raw_only"]].flag == "keep" and plan.photos[fx.ids["raw_only"]].rating == 4
