"""Part 3 Task 4 — one folder per subject (spec §3.4, CR-P3-03, CR-P3-D04, RV-P3-D2-04)."""

from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

import pytest

from app.export.copy_export import IssueStatus, plan_export, run_export
from app.export.layout import (
    MAX_FOLDER_CHARS,
    UNKNOWN_FOLDER,
    Layout,
    photo_subjects,
    resolve_subject,
    safe_folder_name,
    subject_folders,
)
from app.export.photos import load_photos
from app.identity import actions
from app.storage.project import utc_now
from tests.fixtures_export import make_export_session


def _subject(conn: sqlite3.Connection, name: str | None, merged_into: int | None = None) -> int:
    return int(conn.execute("INSERT INTO subjects (display_name, merged_into, created_at) VALUES (?, ?, ?)",
                            (name, merged_into, utc_now())).lastrowid)


def _occ(conn: sqlite3.Connection, asset_id: int, subject_id: int | None, assignment: str = "manual") -> None:
    conn.execute("""INSERT INTO occurrences (asset_id, prominence, is_main, subject_id, assignment, analysis_version,
                                             created_at) VALUES (?, 1.0, 1, ?, ?, 1, ?)""",
                 (asset_id, subject_id, assignment, utc_now()))


@pytest.fixture
def fx(tmp_path: Path):  # noqa: ANN201
    f = make_export_session(tmp_path)
    yield f
    f.project.close()


def _folders(plan) -> dict[str, list[str]]:  # noqa: ANN001
    out: dict[str, list[str]] = {}
    for op in plan.operations:
        out.setdefault(op.folder, []).append(op.dest_relative)
    return {k: sorted(v) for k, v in out.items()}


def test_membership_auto_manual_only(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    mai, lan, ren = _subject(conn, "Mai"), _subject(conn, "Lan"), _subject(conn, "Ren")
    _occ(conn, fx.ids["raw_only"], mai, "auto")
    _occ(conn, fx.ids["jpeg_only"], lan, "manual")
    _occ(conn, fx.ids["tiff"], ren, "suggested")
    _occ(conn, fx.ids["png"], None, "none")
    photos = load_photos(conn, [fx.ids[k] for k in ("raw_only", "jpeg_only", "tiff", "png")])
    assert photo_subjects(conn, photos) == {fx.ids["raw_only"]: (mai,), fx.ids["jpeg_only"]: (lan,),
                                            fx.ids["tiff"]: (), fx.ids["png"]: ()}


def test_membership_from_any_file_of_the_pair(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    mai = _subject(conn, "Mai")
    _occ(conn, fx.files["pair"][1], mai)  # the analysis ran on the JPEG half
    assert photo_subjects(conn, load_photos(conn, [fx.ids["pair"]])) == {fx.ids["pair"]: (mai,)}


def test_merged_subject_resolves_to_survivor(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    final = _subject(conn, "Mai")
    middle = _subject(conn, "Mai cũ", merged_into=final)
    old = _subject(conn, None, merged_into=middle)
    assert resolve_subject(conn, old) == final and resolve_subject(conn, final) == final
    _occ(conn, fx.ids["raw_only"], old)
    _occ(conn, fx.ids["raw_only"], final)  # the same person twice in one photo → one folder
    a, b = _subject(conn, "A"), _subject(conn, "B")
    conn.execute("UPDATE subjects SET merged_into = ? WHERE id = ?", (b, a))
    conn.execute("UPDATE subjects SET merged_into = ? WHERE id = ?", (a, b))  # a cycle
    _occ(conn, fx.ids["jpeg_only"], a)
    assert resolve_subject(conn, a) is None and resolve_subject(conn, 99_999) is None
    photos = load_photos(conn, [fx.ids["raw_only"], fx.ids["jpeg_only"]])
    assert photo_subjects(conn, photos) == {fx.ids["raw_only"]: (final,), fx.ids["jpeg_only"]: ()}
    plan = plan_export(fx.project, [fx.ids["raw_only"], fx.ids["jpeg_only"]], fx.dest, layout=Layout.SUBJECTS)
    assert _folders(plan) == {"Mai": ["Mai/DSC_0003.NEF"], UNKNOWN_FOLDER: [f"{UNKNOWN_FOLDER}/DSC_0004.JPG"]}


def test_merged_subject_never_gets_a_folder(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    keep = _subject(conn, "Mai")
    dropped = _subject(conn, "Lan", merged_into=keep)
    assert dropped not in subject_folders(conn) and subject_folders(conn)[keep] == "Mai"


def test_merge_subjects_leaves_no_stale_reference(fx) -> None:  # noqa: ANN001
    """Why resolution is only defensive: the app's merge moves every occurrence and deletes the dropped row."""
    conn = fx.project.conn
    keep, drop = _subject(conn, "Mai"), _subject(conn, "Mai 2")
    _occ(conn, fx.ids["raw_only"], drop)
    actions.merge_subjects(conn, keep, drop)
    assert conn.execute("SELECT COUNT(*) FROM occurrences WHERE subject_id = ?", (drop,)).fetchone()[0] == 0
    assert photo_subjects(conn, load_photos(conn, [fx.ids["raw_only"]])) == {fx.ids["raw_only"]: (keep,)}


def test_multi_subject_photo_in_each_folder(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    mai, lan = _subject(conn, "Mai"), _subject(conn, "Lan")
    _occ(conn, fx.ids["pair"], mai)
    _occ(conn, fx.ids["pair"], lan)
    plan = plan_export(fx.project, [fx.ids["pair"]], fx.dest, layout=Layout.SUBJECTS)
    assert _folders(plan) == {"Lan": ["Lan/DSC_0001.JPG", "Lan/DSC_0001.NEF"],
                              "Mai": ["Mai/DSC_0001.JPG", "Mai/DSC_0001.NEF"]}
    assert plan.total_bytes == 2 * (500_000 + 300_000) and plan.photos_planned == 1
    assert plan.layout_stats.multi_subject == 1 and plan.layout_stats.per_folder == {"Lan": 1, "Mai": 1}
    result = run_export(plan)
    assert sorted(result.copied) == sorted(op.dest_relative for op in plan.operations) and not result.failed
    assert (fx.dest / "Mai" / "DSC_0001.NEF").read_bytes() == (fx.root / "DSC_0001.NEF").read_bytes()


def test_unknown_and_suggested_go_to_unknown_folder(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    mai = _subject(conn, "Mai")
    _occ(conn, fx.ids["raw_only"], mai, "suggested")  # AI not sure
    _occ(conn, fx.ids["jpeg_only"], None, "none")  # a person, nobody known
    ids = [fx.ids[k] for k in ("raw_only", "jpeg_only", "tiff")]  # tiff: no person at all
    plan = plan_export(fx.project, ids, fx.dest, layout=Layout.SUBJECTS)
    assert set(_folders(plan)) == {UNKNOWN_FOLDER}
    stats = plan.layout_stats
    assert (stats.unknown_suggested, stats.unknown_other, stats.analysed) == (1, 2, True)


def test_never_analysed_flag(fx) -> None:  # noqa: ANN001
    plan = plan_export(fx.project, [fx.ids["raw_only"]], fx.dest, layout=Layout.SUBJECTS)
    assert plan.layout_stats.analysed is False and set(_folders(plan)) == {UNKNOWN_FOLDER}


@pytest.mark.parametrize(("name", "expected"), [
    ("Mai/Lan?", "Mai_Lan_"), ("CON", "CON_"), ("aux.txt", "aux.txt_"), ("com1", "com1_"), ("LPT9", "LPT9_"),
    ("  Ren. ", "Ren"), ("???", "Chủ thể 7"), ("...", "Chủ thể 7"), ("   ", "Chủ thể 7"), ("<>|", "Chủ thể 7"),
    ("#1", "#1"), ("a\tb", "a_b"), ("", "Chủ thể 7"),
])
def test_safe_folder_name(name: str, expected: str) -> None:
    assert safe_folder_name(name, "Chủ thể 7") == expected


def test_safe_folder_name_length_and_nfc() -> None:
    assert len(safe_folder_name("Á" * 70, "x")) == MAX_FOLDER_CHARS == 60
    decomposed = unicodedata.normalize("NFD", "Nguyễn Thị Hằng")
    assert safe_folder_name(decomposed, "x") == unicodedata.normalize("NFC", "Nguyễn Thị Hằng")


def test_duplicate_names_get_ids(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    a, b, c, d, e = (_subject(conn, n) for n in ("Mai", "mai", "Lan", UNKNOWN_FOLDER, None))
    f = _subject(conn, "Mai?")  # "Mai_" after sanitising: not equal to "Mai"
    folders = subject_folders(conn)
    assert folders[a] == f"Mai (#{a})" and folders[b] == f"mai (#{b})" and folders[c] == "Lan"
    assert folders[d] == f"{UNKNOWN_FOLDER} (#{d})" and folders[e] == f"Chủ thể {e}" and folders[f] == "Mai_"


def test_path_too_long_is_an_issue(fx, tmp_path: Path) -> None:  # noqa: ANN001
    conn = fx.project.conn
    long_dest = tmp_path / ("d" * 200) / ("e" * 40)
    mai = _subject(conn, "M" * 55)
    _occ(conn, fx.ids["raw_only"], mai)
    _occ(conn, fx.ids["jpeg_only"], mai)
    conn.execute("UPDATE subjects SET display_name = ? WHERE id = ?", ("M" * 55, mai))
    plan = plan_export(fx.project, [fx.ids["raw_only"]], long_dest, layout=Layout.SUBJECTS)
    if len(str(long_dest / ("M" * 55) / "DSC_0003.NEF")) <= 259:
        pytest.skip("temporary folder too short to exceed 259 characters")
    assert plan.operations == []
    (issue,) = plan.issues
    assert issue.status is IssueStatus.PATH_TOO_LONG and "DSC_0003.NEF" in issue.detail


def test_rename_between_exports_uses_new_folder(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    mai = _subject(conn, "Mai")
    _occ(conn, fx.ids["raw_only"], mai)
    run_export(plan_export(fx.project, [fx.ids["raw_only"]], fx.dest, layout=Layout.SUBJECTS))
    actions.rename_subject(conn, mai, "Mai Anh")
    plan = plan_export(fx.project, [fx.ids["raw_only"]], fx.dest, layout=Layout.SUBJECTS)
    assert _folders(plan) == {"Mai Anh": ["Mai Anh/DSC_0003.NEF"]}
    run_export(plan)
    assert (fx.dest / "Mai" / "DSC_0003.NEF").is_file() and (fx.dest / "Mai Anh" / "DSC_0003.NEF").is_file()


def test_planning_never_writes_db(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    mai = _subject(conn, "Mai")
    _occ(conn, fx.ids["pair"], mai, "suggested")
    conn.commit()
    before = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
              for t in ("subjects", "occurrences", "decisions", "assets")}
    run_export(plan_export(fx.project, [fx.ids["pair"], fx.ids["raw_only"]], fx.dest, layout=Layout.SUBJECTS))
    assert before == {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in before}
    assert not conn.in_transaction


def test_single_layout_unchanged_by_subjects(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    _occ(conn, fx.ids["raw_only"], _subject(conn, "Mai"))
    plan = plan_export(fx.project, [fx.ids["raw_only"]], fx.dest)
    assert _folders(plan) == {"": ["DSC_0003.NEF"]}


def test_stats_count_a_pair_once_when_both_halves_are_selected(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    raw, jpg = fx.files["pair"]
    plan = plan_export(fx.project, [raw, jpg], fx.dest, layout=Layout.SUBJECTS)
    assert plan.layout_stats.unknown_other == 1 and plan.layout_stats.per_folder == {UNKNOWN_FOLDER: 1}
    mai, lan = _subject(conn, "Mai"), _subject(conn, "Lan")
    _occ(conn, raw, mai)
    _occ(conn, raw, lan)
    plan = plan_export(fx.project, [raw, jpg], fx.dest, layout=Layout.SUBJECTS)
    assert plan.layout_stats.multi_subject == 1


# ---- CR-P3-A01: final folder names unique (Windows, case-insensitive) -------------------------------------------

def _assert_unique(folders: dict[int, str]) -> None:
    finals = [unicodedata.normalize("NFC", n).casefold() for n in folders.values()]
    assert len(finals) == len(set(finals)), folders
    assert UNKNOWN_FOLDER.casefold() not in finals
    assert all(len(n) <= MAX_FOLDER_CHARS and n == n.rstrip(". ") and n.strip() == n for n in folders.values())


def test_collision_after_suffix(fx) -> None:  # noqa: ANN001
    """Review CR-P3-A01: 12 "Mai" → "Mai (#12)", but subject 45 is literally named "Mai (#12)"."""
    conn = fx.project.conn
    first, second = _subject(conn, "Mai"), _subject(conn, "Mai")
    literal = _subject(conn, f"Mai (#{first})")
    folders = subject_folders(conn)
    _assert_unique(folders)
    assert folders[first] == f"Mai (#{first})" and folders[second] == f"Mai (#{second})"
    assert folders[literal] == f"Mai (#{first}) (#{literal})"


def test_literal_name_first_then_suffixed_twin(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    literal = _subject(conn, "Lan (#99)")  # created before the subjects whose suffix would produce it
    conn.execute("INSERT INTO subjects (id, display_name, created_at) VALUES (99, 'Lan', ?)", (utc_now(),))
    other = _subject(conn, "Lan")
    folders = subject_folders(conn)
    _assert_unique(folders)
    assert folders[99] != folders[literal]


def test_long_names_stay_unique_and_short(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    ids = [_subject(conn, "Á" * 70) for _ in range(3)] + [_subject(conn, "Á" * 60 + "B")]
    folders = subject_folders(conn)
    _assert_unique(folders)
    assert all(folders[i].endswith(f"(#{i})") for i in ids)  # equal after the 60-character cut


def test_unicode_forms_and_similar_names_clash(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    nfc = _subject(conn, "Hằng")
    nfd = _subject(conn, unicodedata.normalize("NFD", "Hằng"))
    names = [_subject(conn, n) for n in ("Ren", "ren ", "REN.", "Ren?")]  # Ren / ren / REN equal; Ren_ differs
    folders = subject_folders(conn)
    _assert_unique(folders)
    assert folders[nfc] == f"Hằng (#{nfc})" and folders[nfd] == f"Hằng (#{nfd})"
    assert [folders[i] for i in names] == [f"Ren (#{names[0]})", f"ren (#{names[1]})", f"REN (#{names[2]})", "Ren_"]


@pytest.mark.parametrize("name", [UNKNOWN_FOLDER, UNKNOWN_FOLDER.upper(), unicodedata.normalize("NFD", UNKNOWN_FOLDER),
                                  UNKNOWN_FOLDER + ".", f"  {UNKNOWN_FOLDER}  "])
def test_unknown_folder_name_never_taken(fx, name: str) -> None:  # noqa: ANN001
    conn = fx.project.conn
    sid = _subject(conn, name)
    folders = subject_folders(conn)
    _assert_unique(folders)
    assert folders[sid].endswith(f"(#{sid})")


def test_names_stable_between_runs(fx) -> None:  # noqa: ANN001
    conn = fx.project.conn
    for n in ("Mai", "mai", "Mai (#1)", "Lan", None, "???", "Á" * 70):
        _subject(conn, n)
    assert subject_folders(conn) == subject_folders(conn)
