"""F3 Batch 0: the read-only grouping diagnostic (metrics, labels, baseline rebuild, read-only, offline)."""

from __future__ import annotations

import csv
import hashlib
import json
import socket
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from app.diagnostics import grouping as dg
from app.identity import actions
from app.identity.cluster import recluster
from app.storage.project import DB_NAME, Project

RNG = np.random.default_rng(11)
T0 = datetime(2026, 10, 25, 10, 0, 0)


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def _near(base: np.ndarray, noise: float) -> np.ndarray:
    return _unit(base + _unit(RNG.normal(size=base.size)) * noise)


def _add(p: Project, asset: int, face: np.ndarray | None, outfit: np.ndarray | None, seconds: int,
         main: int = 1) -> int:
    conn = p.conn
    if not conn.execute("SELECT 1 FROM assets WHERE id = ?", (asset,)).fetchone():
        conn.execute(
            """INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, capture_time, added_at, updated_at)
               VALUES (?, 1, ?, '.jpg', 'raster', 'verified', 1, 1, ?, 'ok', ?, 'n', 'n')""",
            (asset, f"DSC_{asset:04d}.JPG", str(asset), (T0 + timedelta(seconds=seconds)).isoformat()))
    occ = int(conn.execute(
        """INSERT INTO occurrences (asset_id, person_box, prominence, is_main, analysis_version, created_at)
           VALUES (?, '[0.1,0.1,0.5,0.8]', 1.0, ?, 1, 'n')""", (asset, main)).lastrowid)
    for kind, vec in (("face", face), ("outfit", outfit)):
        if vec is not None:
            conn.execute("INSERT INTO occurrence_vectors VALUES (?, ?, 't', ?)", (occ, kind, vec.astype("<f4").tobytes()))
    return occ


def _partition(p: Project) -> set[frozenset[int]]:
    groups: dict[int, set[int]] = {}
    for occ, sid in p.conn.execute("SELECT id, subject_id FROM occurrences WHERE subject_id IS NOT NULL"):
        groups.setdefault(sid, set()).add(occ)
    return {frozenset(g) for g in groups.values()}


@pytest.fixture()
def shoot(tmp_path: Path):
    """Two customers: K1 in two costumes 40 min apart (+ a face-less burst of look A 8 min later), K2 in one."""
    p = Project.create(tmp_path / "session", "x")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    k1, k2 = _unit(RNG.normal(size=128)), _unit(RNG.normal(size=128))
    look_a, look_b, look_c = (_unit(RNG.random(96)) for _ in range(3))
    occ: dict[str, list[int]] = {"K1-A": [], "K1-A2": [], "K1-B": [], "K2-A": []}
    asset = 0
    for j in range(5):  # K1, costume A, faces visible
        asset += 1
        occ["K1-A"].append(_add(p, asset, _near(k1, 0.3), _near(look_a, 0.05), j * 20))
    for j in range(3):  # K1, costume A again 8 min later, back to the camera (no face)
        asset += 1
        occ["K1-A2"].append(_add(p, asset, None, _near(look_a, 0.05), 480 + j * 20))
    k1_makeup = _near(k1, 1.2)  # K1 in costume B: makeup changes the face a lot
    for j in range(5):  # K1, costume B 40 min later
        asset += 1
        occ["K1-B"].append(_add(p, asset, _near(k1_makeup, 0.3), _near(look_b, 0.05), 2400 + j * 20))
    for j in range(5):  # K2, costume C, in between
        asset += 1
        occ["K2-A"].append(_add(p, asset, _near(k2, 0.3), _near(look_c, 0.05), 1200 + j * 20))
    recluster(p)
    yield p, occ
    p.close()


def _sid_of(p: Project, occ_id: int) -> int:
    return p.conn.execute("SELECT subject_id FROM occurrences WHERE id = ?", (occ_id,)).fetchone()[0]


def _label_like_owner(p: Project, occ: dict[str, list[int]]) -> None:
    """The owner corrects the copy: the face-less burst joins look A, then labels every subject by name."""
    a = _sid_of(p, occ["K1-A"][0])
    a2 = _sid_of(p, occ["K1-A2"][0])
    if a2 is not None and a2 != a:
        actions.merge_subjects(p.conn, a, a2)
    actions.rename_subject(p.conn, a, "K1-A")
    actions.rename_subject(p.conn, _sid_of(p, occ["K1-B"][0]), "k1 - b")
    actions.rename_subject(p.conn, _sid_of(p, occ["K2-A"][0]), "K2-A")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ metrics
def test_metrics_on_a_hand_computed_case() -> None:
    truth = {1: "a", 2: "a", 3: "a", 4: "b", 5: "b"}
    pred = {1: "x", 2: "x", 3: "y", 4: "y", 5: "z"}
    m = dg.grouping_metrics(truth, pred)
    # pairs: true a: 3, b: 1 -> 4; predicted x: 1, y: 1 -> 2; correct: (1,2) -> 1
    assert m["pairwise_precision"] == 0.5 and m["pairwise_recall"] == 0.25
    assert m["clusters"] == 3 and m["true_groups"] == 2
    assert m["false_merge_clusters"] == 1  # y holds a and b
    assert m["false_split_groups"] == 2 and m["false_split_extra_clusters"] == 2  # a in x,y; b in y,z
    # B-cubed precision: items 1,2 -> 1; 3 -> 1/2; 4 -> 1/2; 5 -> 1 => 4/5
    assert m["bcubed_precision"] == 0.8
    assert m["manual_corrections"] == {"photo_moves": 1, "merges": 1, "total": 2}


def test_perfect_grouping_and_unassigned_items() -> None:
    truth = {1: "a", 2: "a", 3: "b"}
    perfect = dg.grouping_metrics(truth, {1: 7, 2: 7, 3: 8})
    assert perfect["pairwise_precision"] is None or perfect["pairwise_precision"] == 1.0
    assert perfect["bcubed_f1"] == 1.0 and perfect["manual_corrections"]["total"] == 0
    alone = dg.grouping_metrics(truth, {1: 7})  # 2 and 3 not grouped: each its own cluster
    assert alone["false_split_groups"] == 1 and alone["manual_corrections"]["merges"] == 1


def test_label_parsing_never_splits_composite_labels() -> None:
    assert dg.parse_subject_label("K1-A") == dg.Label("1", "1-A")
    assert dg.parse_subject_label(" k12 - b ") == dg.Label("12", "12-B")
    assert dg.parse_subject_label("K3") == dg.Label("3", None)
    for name in ("K1-A+K2-A", "K1-A+B", "?", "Mai", "", None, "K1-AB"):
        assert dg.parse_subject_label(name) == dg.UNCERTAIN


def test_csv_labels_are_per_occurrence_and_override_names(shoot, tmp_path: Path) -> None:
    p, occ = shoot
    _label_like_owner(p, occ)
    path = tmp_path / "labels.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["occurrence_id", "photo", "person", "look"])
        w.writerow([occ["K2-A"][0], "", "?", ""])  # unsure about this one
        w.writerow(["", "DSC_0002.JPG", "1", "a"])
        w.writerow(["999999", "", "1", "a"])  # unknown occurrence
    labels, stats = dg.read_labels(p.conn, path)
    assert labels[occ["K2-A"][0]] == dg.UNCERTAIN
    assert labels[occ["K1-A"][1]] == dg.Label("1", "1-A")
    assert stats["csv_rows_applied"] == 2 and stats["csv_rows_unknown"] == 1
    assert stats["uncertain"] >= 1


# ----------------------------------------------------- baseline and report
def test_baseline_rebuild_equals_the_first_automatic_grouping(shoot, tmp_path: Path) -> None:
    p, occ = shoot
    first = _partition(p)
    _label_like_owner(p, occ)
    actions.mark_different(p.conn, _sid_of(p, occ["K1-B"][0]), _sid_of(p, occ["K2-A"][0]))
    actions.remove_photos_from_subject(p.conn, _sid_of(p, occ["K2-A"][0]), [16])
    recluster(p)
    assert _partition(p) != first  # the owner's corrections changed the grouping
    p.conn.commit()
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / DB_NAME).write_bytes((p.folder / DB_NAME).read_bytes())
    for suffix in ("-wal",):
        if (p.folder / f"{DB_NAME}{suffix}").is_file():
            (copy / f"{DB_NAME}{suffix}").write_bytes((p.folder / f"{DB_NAME}{suffix}").read_bytes())
    with Project.open(copy) as q:
        rebuilt = dg.rebuild(q, None)
    groups: dict[object, set[int]] = {}
    for i, c in rebuilt.items():
        groups.setdefault(c, set()).add(i)
    assert {frozenset(g) for g in groups.values()} == first


def test_report_measures_both_levels_and_is_read_only(shoot, tmp_path: Path) -> None:
    p, occ = shoot
    _label_like_owner(p, occ)
    p.conn.commit()
    files = [f for f in (p.folder / DB_NAME, p.folder / f"{DB_NAME}-wal") if f.is_file()]
    before = {f.name: _sha(f) for f in files}
    report = dg.diagnose(p.folder, None)
    assert {f.name: _sha(f) for f in files} == before
    assert report["read_only"]["unchanged"] is True
    base = report["reconstructed_baseline"]
    assert base["deterministic"] is True
    # Automatic grouping (rules as designed): look A split by the face-less burst, K1's costumes apart.
    person, look = base["default"]["person"], base["default"]["look"]
    assert person["true_groups"] == 2 and person["false_split_groups"] == 1
    assert look["true_groups"] == 3
    assert person["pairwise_precision"] == 1.0  # no different customers joined
    pairs = report["evidence"]["cluster_pairs"]
    assert pairs.get("same_person_other_look", 0) >= 1  # H1
    assert pairs.get("different_person", 0) >= 1
    # Owner-corrected state is perfect at look level (sanity check of the labels)
    assert report["current_state"]["look"]["bcubed_f1"] == 1.0
    text = json.dumps(report)
    assert "DSC_" not in text and "K1-A" not in text and "k1 - b" not in text  # numbers only


def test_cli_blocks_network_and_never_touches_photos(shoot, tmp_path: Path, monkeypatch) -> None:
    p, occ = shoot
    _label_like_owner(p, occ)
    p.conn.commit()
    for name in ("connect", "connect_ex"):  # restore the socket functions the CLI replaces
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "DSC_0001.JPG").write_bytes(b"original photo bytes")
    photo_hash = _sha(photos / "DSC_0001.JPG")
    data = tmp_path / "data"
    monkeypatch.setattr("app.branding.data_dir", lambda: data)
    from app.storage.sessions import session_dir

    target = session_dir(data / "sessions", photos)
    target.parent.mkdir(parents=True)
    (target).mkdir()
    (target / DB_NAME).write_bytes((p.folder / DB_NAME).read_bytes())
    out = tmp_path / "report.json"
    code = dg.run_cli([str(photos), str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0 and report["ok"] is True and report["network_attempts"] == 0
    assert _sha(photos / "DSC_0001.JPG") == photo_hash
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 80))  # blocked while the diagnostic runs (same process)


def test_cli_reports_a_missing_session(tmp_path: Path, monkeypatch) -> None:
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    monkeypatch.setattr("app.branding.data_dir", lambda: tmp_path / "data")
    out = tmp_path / "r.json"
    assert dg.run_cli([str(tmp_path / "nowhere"), str(out)]) == 1
    assert "no KiraPick session" in json.loads(out.read_text(encoding="utf-8"))["error"]


def test_tuned_baseline_is_reported_when_learning_applies(shoot, monkeypatch) -> None:
    from app.learning.tuning import Tuning

    p, occ = shoot
    _label_like_owner(p, occ)
    p.conn.commit()
    monkeypatch.setattr("app.learning.tuning.tune_from_store",
                        lambda folder, base: Tuning(face=0.04, look=0.02, applied=True))
    report = dg.diagnose(p.folder, None)
    assert report["tuning"] == {"applied": True, "face_shift": 0.04, "look_shift": 0.02}
    assert "tuned" in report["reconstructed_baseline"] and isinstance(report["reconstructed_baseline"]["tuned_equals_default"], bool)


# ----------------------------------------------- Batch 0 review follow-ups
def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> Path:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def test_csv_duplicates_conflicts_unknown_and_invalid_rows(shoot, tmp_path: Path) -> None:
    p, occ = shoot
    a, b = occ["K1-A"][0], occ["K2-A"][0]
    path = _write_csv(tmp_path / "l.csv", ["occurrence_id", "photo", "person", "look"], [
        [a, "", "1", "A"], [a, "", "1", "a"],  # duplicate (same label)
        [b, "", "2", "A"], ["", "DSC_0014.JPG", "1", "A"],  # photo 14's occurrence is b: conflict
        ["999999", "", "1", "A"],  # unknown id
        ["12x", "", "1", "A"], ["", "", "1", "A"],  # invalid
    ])
    labels, stats = dg.read_labels(p.conn, path)
    assert occ["K2-A"][0] == p.conn.execute(
        "SELECT o.id FROM occurrences o JOIN assets s ON s.id = o.asset_id WHERE s.relative_path = 'DSC_0014.JPG'"
    ).fetchone()[0]
    assert labels[a] == dg.Label("1", "1-A")
    assert labels[b] == dg.UNCERTAIN  # contradicting rows are never guessed
    assert stats["csv_rows_duplicate"] == 1 and stats["csv_conflicting_occurrences"] == 1
    assert stats["csv_rows_unknown"] == 1 and stats["csv_rows_invalid"] == 2


def test_csv_without_required_columns_is_refused(shoot, tmp_path: Path) -> None:
    p, _ = shoot
    with pytest.raises(dg.LabelsError):
        dg.read_labels(p.conn, _write_csv(tmp_path / "bad.csv", ["file", "who"], [["a", "1"]]))


def test_snapshot_includes_committed_wal_changes_and_excludes_uncommitted_ones(shoot, tmp_path: Path) -> None:
    p, occ = shoot
    p.conn.commit()
    _label_like_owner(p, occ)  # committed, still in the write-ahead log (connection kept open)
    p.conn.commit()
    assert (p.folder / f"{DB_NAME}-wal").stat().st_size > 0
    p.conn.execute("BEGIN IMMEDIATE")  # an active writer with uncommitted changes
    p.conn.execute("UPDATE subjects SET display_name = 'K9-Z'")
    try:
        files = [p.folder / DB_NAME, p.folder / f"{DB_NAME}-wal"]
        before = {f.name: _sha(f) for f in files}
        report = dg.diagnose(p.folder, None)
        assert {f.name: _sha(f) for f in files} == before
    finally:
        p.conn.execute("ROLLBACK")
    assert report["read_only"]["snapshot_method"] == "sqlite_backup_live"  # KiraPick's connection is open
    assert report["labels"]["person_labelled"] == 18  # the committed labels, not K9-Z
    assert report["current_state"]["person"]["true_groups"] == 2


def test_learning_db_and_session_files_stay_byte_identical(shoot, tmp_path: Path) -> None:
    from app.learning.store import LearningStore

    p, occ = shoot
    _label_like_owner(p, occ)
    p.conn.commit()
    learn = tmp_path / "learning"
    store = LearningStore(learn)
    store.close()
    watched = [f for f in (*learn.iterdir(), *p.folder.iterdir()) if f.is_file() and not f.name.endswith("-shm")]
    before = {str(f): _sha(f) for f in watched}
    report = dg.diagnose(p.folder, learn)
    assert {str(f): _sha(f) for f in watched} == before
    assert report["read_only"]["unchanged"] is True and report["read_only"]["files_hashed"] >= 2


def test_report_holds_no_names_paths_or_vectors(tmp_path: Path) -> None:
    p = Project.create(tmp_path / "s", "SECRET_PROJECT")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('C:/Users/secretuser/Ảnh', 'n')")
    face, look = _unit(RNG.normal(size=128)), _unit(RNG.random(96))
    for i in range(1, 5):
        _add(p, i, _near(face, 0.3), _near(look, 0.05), i * 10)
    p.conn.execute("UPDATE assets SET relative_path = 'SECRETPHOTO_' || id || '.JPG'")
    recluster(p)
    sid = p.conn.execute("SELECT subject_id FROM occurrences LIMIT 1").fetchone()[0]
    actions.rename_subject(p.conn, sid, "Nguyễn Bí Mật")
    p.conn.commit()
    report = dg.diagnose(p.folder, None)
    text = json.dumps(report, ensure_ascii=False)
    for secret in ("SECRET", "secretuser", "Nguyễn", "Bí Mật", "Ảnh", str(tmp_path)):
        assert secret not in text
    p.close()


def test_numbers_only_check_rejects_stray_text_and_vectors() -> None:
    dg.check_numbers_only({"labels": {"occurrences": 3}, "limitations": list(dg.LIMITS_ALWAYS)})
    for bad in ({"name": "Mai"}, {"x": {"DSC_0001": 1}}, {"v": [0.1] * 128}, {"limitations": ["C:/Users/x"]},
                {"error": b"bytes"}):
        with pytest.raises(ValueError):
            dg.check_numbers_only(bad)


def test_cli_error_reports_never_carry_messages_of_unknown_errors(tmp_path: Path, monkeypatch) -> None:
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    monkeypatch.setattr("app.branding.data_dir", lambda: tmp_path / "data")

    def boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("C:/Users/secretuser/Ảnh/DSC_0001.JPG")

    monkeypatch.setattr(dg, "diagnose", boom)
    out = tmp_path / "r.json"
    assert dg.run_cli([str(tmp_path / "x"), str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["error"] == "RuntimeError"
    assert (tmp_path / "r.json.traceback.txt").is_file()  # local detail, separate file


def test_closed_session_gets_no_new_files_next_to_it(shoot) -> None:
    """KiraPick closed (log checkpointed): reading must not even create empty -wal/-shm files."""
    p, occ = shoot
    _label_like_owner(p, occ)
    p.conn.commit()
    folder = p.folder
    p.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    p.close()
    for leftover in (folder / f"{DB_NAME}-wal", folder / f"{DB_NAME}-shm"):
        leftover.unlink(missing_ok=True)
    before = {f.name: _sha(f) for f in folder.iterdir() if f.is_file()}
    report = dg.diagnose(folder, None)
    assert {f.name: _sha(f) for f in folder.iterdir() if f.is_file()} == before
    assert report["read_only"]["wal_present"] is False and report["read_only"]["no_new_files"] is True
    assert report["read_only"]["unchanged"] is True
    assert report["labels"]["person_labelled"] == 18
    p.conn = __import__("sqlite3").connect(":memory:")  # the fixture closes it again


def _closed_copy(p: Project, occ: dict, tmp: Path, keep_wal: bool) -> Path:
    """A closed session folder, optionally with committed changes still in its -wal and no -shm."""
    import shutil

    _label_like_owner(p, occ)
    p.conn.commit()
    folder = tmp / "closed"
    folder.mkdir()
    if keep_wal:  # as after a crash: .db + -wal, no -shm
        p.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        shutil.copyfile(p.folder / DB_NAME, folder / DB_NAME)
        shutil.copyfile(p.folder / f"{DB_NAME}-wal", folder / f"{DB_NAME}-wal")
    else:
        p.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copyfile(p.folder / DB_NAME, folder / DB_NAME)
    return folder


def _state(folder: Path) -> dict[str, str]:
    return {f.name: _sha(f) for f in folder.iterdir() if f.is_file()}


@pytest.mark.parametrize("keep_wal", [False, True], ids=["no-wal", "wal-without-shm"])
def test_closed_sessions_are_never_opened_by_sqlite(shoot, tmp_path: Path, keep_wal: bool, monkeypatch) -> None:
    import sqlite3

    p, occ = shoot
    folder = _closed_copy(p, occ, tmp_path, keep_wal)
    before = _state(folder)
    real = sqlite3.connect

    def guarded(target, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        assert str(folder) not in str(target) and folder.resolve().as_uri() not in str(target)
        return real(target, *a, **k)

    monkeypatch.setattr(sqlite3, "connect", guarded)
    report = dg.diagnose(folder, None)
    assert _state(folder) == before  # same names (no -shm/-wal created) and same bytes
    ro = report["read_only"]
    assert ro["snapshot_method"] == "file_copy_closed" and ro["unchanged"] and ro["no_new_files"]
    assert ro["kirapick_seemed_open"] is False
    assert report["labels"]["person_labelled"] == 18  # committed changes in the -wal are included


@pytest.mark.skipif(not hasattr(__import__("os"), "geteuid") or __import__("os").geteuid() == 0,
                    reason="root ignores directory permissions (checked on Windows CI with an ACL)")
def test_read_only_source_directory(shoot, tmp_path: Path) -> None:
    p, occ = shoot
    folder = _closed_copy(p, occ, tmp_path, keep_wal=True)
    before = _state(folder)
    folder.chmod(0o555)
    try:
        report = dg.diagnose(folder, None)
    finally:
        folder.chmod(0o755)
    assert _state(folder) == before and report["read_only"]["unchanged"] is True
