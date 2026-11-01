"""F3 P0-A (same-label co-occurrence) and P0-B (learning audit) diagnostics: synthetic cases."""

from __future__ import annotations

import csv
import json
import shutil
import socket
from pathlib import Path

import numpy as np

from app.diagnostics import cooccurrence as co
from app.diagnostics import grouping as dg
from app.diagnostics import learning_audit as la
from app.identity.cluster import SFACE_HSV, recluster
from app.identity.features import OUTFIT_VERSION
from app.learning import tuning
from app.learning.store import LearningStore, PairEvidence
from app.storage.project import Project
from app.workers.analyze_job import FACE_VECTOR_VERSION

RNG = np.random.default_rng(5)
B = co.Box


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


# ------------------------------------------------------------------ P0-A classification
def test_classes_on_synthetic_boxes() -> None:
    body = B(0.1, 0.1, 0.4, 0.8)
    face_in_body = B(0.25, 0.15, 0.1, 0.1)
    assert co.classify(None, face_in_body, body, None, None)[0] == "duplicate_face_only"
    assert co.classify(body, None, B(0.12, 0.12, 0.36, 0.75), None, 0.2)[0] == "duplicate_overlapping_bodies"
    left, right = B(0.05, 0.1, 0.3, 0.8), B(0.6, 0.12, 0.3, 0.75)
    assert co.classify(left, None, right, None, 0.9)[0] == "possible_reflection"
    assert co.classify(left, None, right, None, 0.1)[0] == "two_people_same_label"
    assert co.classify(left, None, right, None, 0.45)[0] == "undetermined"  # ambiguous: the owner decides
    assert co.classify(left, None, right, None, None)[0] == "undetermined"  # no faces to compare
    assert co.classify(None, None, right, None, 0.9)[0] == "undetermined"  # missing boxes
    # A face far away from the other body is not a duplicate of it
    assert co.classify(None, B(0.8, 0.8, 0.1, 0.1), body, None, None)[0] != "duplicate_face_only"


def _session(tmp: Path) -> tuple[Project, dict[str, int]]:
    """Photo 1: K1 counted twice (a face-only box inside K1's body) -> two subjects both labelled K1-A.
    Photo 2: K1 and K2 together (different labels: never a pair). Photo 3: one occurrence with body+face."""
    p = Project.create(tmp / "session", "x")
    conn = p.conn
    conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    k1, k2, look = _unit(RNG.normal(size=128)), _unit(RNG.normal(size=128)), _unit(RNG.random(96))
    occ = {}

    def add(key: str, asset: int, person: list | None, face_box: list | None, face: np.ndarray | None) -> None:
        if not conn.execute("SELECT 1 FROM assets WHERE id = ?", (asset,)).fetchone():
            conn.execute("""INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size,
                            mtime_ns, quick_hash, status, capture_time, added_at, updated_at)
                            VALUES (?, 1, ?, '.jpg', 'raster', 'verified', 1, 1, ?, 'ok', ?, 'n', 'n')""",
                         (asset, f"SECRET_{asset:04d}.JPG", str(asset), f"2026-10-25T10:00:{asset:02d}"))
        o = int(conn.execute("""INSERT INTO occurrences (asset_id, person_box, face_box, prominence, is_main,
                                analysis_version, created_at) VALUES (?, ?, ?, 1.0, 1, 1, 'n')""",
                             (asset, json.dumps(person) if person else None, json.dumps(face_box) if face_box else None)
                             ).lastrowid)
        if face is not None:
            conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'face', 't', ?)", (o, face.astype("<f4").tobytes()))
        conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'outfit', 't', ?)", (o, look.astype("<f4").tobytes()))
        occ[key] = o

    add("p1_body", 1, [0.1, 0.1, 0.4, 0.8], [0.25, 0.15, 0.1, 0.1], k1)
    add("p1_face", 1, None, [0.25, 0.15, 0.1, 0.1], k1)
    add("p2_k1", 2, [0.05, 0.1, 0.3, 0.8], [0.1, 0.12, 0.1, 0.1], k1)
    add("p2_k2", 2, [0.6, 0.1, 0.3, 0.8], [0.65, 0.12, 0.1, 0.1], k2)
    add("p3_k1", 3, [0.1, 0.1, 0.4, 0.8], [0.25, 0.15, 0.1, 0.1], k1)
    recluster(p)
    # The owner's labels: two subjects named K1-A (photo 1's two occurrences end up in different subjects)
    for key, name in (("p1_body", "K1-A"), ("p1_face", "K1-A"), ("p2_k1", "K1-A"), ("p2_k2", "K2-A"),
                      ("p3_k1", "K1-A")):
        sid = int(conn.execute("INSERT INTO subjects (display_name, user_locked, created_at) VALUES (?, 1, 'n')",
                               (f"Bí mật {name}",)).lastrowid)
        conn.execute("UPDATE subjects SET display_name = ? WHERE id = ?", (name, sid))
        conn.execute("UPDATE occurrences SET subject_id = ?, assignment = 'manual' WHERE id = ?", (sid, occ[key]))
    conn.commit()
    return p, occ


def test_same_label_pairs_counts_and_local_list(tmp_path: Path) -> None:
    p, occ = _session(tmp_path)
    p.close()
    listing = tmp_path / "local" / "cooccurrence.csv"
    listing.parent.mkdir()
    report = dg.diagnose(p.folder, None, cooccurrence_list=listing)
    c = report["cooccurrence"]
    assert c["pairs"] == 1 and c["photos"] == 1 and c["hypotheses_only"] is True
    assert c["by_class"]["duplicate_face_only"] == 1 and sum(c["by_class"].values()) == 1
    assert c["local_list_written"] is True
    rows = list(csv.DictReader(open(listing, encoding="utf-8-sig")))
    assert rows[0]["photo"] == "SECRET_0001.JPG" and rows[0]["subject_a"] == rows[0]["subject_b"] == "K1-A"
    assert rows[0]["hypothesis"] == "duplicate_face_only" and rows[0]["owner_verdict"] == ""
    text = json.dumps(report, ensure_ascii=False)
    assert "SECRET" not in text and "K1-A" not in text and "cooccurrence.csv" not in text


def test_no_local_list_without_the_flag(tmp_path: Path) -> None:
    p, _ = _session(tmp_path)
    p.close()
    before = sorted(x.name for x in tmp_path.rglob("*") if x.is_file() and p.folder not in x.parents)
    report = dg.diagnose(p.folder, None)
    after = sorted(x.name for x in tmp_path.rglob("*") if x.is_file() and p.folder not in x.parents)
    assert report["cooccurrence"]["local_list_written"] is False and before == after


def test_cli_flag_parsing(tmp_path: Path, monkeypatch) -> None:
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    seen = {}
    monkeypatch.setattr(dg, "diagnose", lambda s, lf, labels, listing: seen.update(labels=labels, listing=listing)
                        or {"read_only": {"unchanged": True}})
    monkeypatch.setattr("app.branding.data_dir", lambda: tmp_path / "data")
    out = tmp_path / "r.json"
    assert dg.run_cli(["F", str(out), "--cooccurrence-list", str(tmp_path / "l.csv")]) == 0
    assert seen == {"labels": None, "listing": tmp_path / "l.csv"}
    assert dg.run_cli(["F", str(out), str(tmp_path / "lab.csv"), "--cooccurrence-list", str(tmp_path / "l.csv")]) == 0
    assert seen["labels"] == tmp_path / "lab.csv"
    assert dg.run_cli(["F", str(out), "--cooccurrence-list", str(out)]) == 2  # never the report file
    assert dg.run_cli(["F", str(out), "--cooccurrence-list"]) == 2


# ------------------------------------------------------------------ P0-B learning audit
def _learning(folder: Path, cross_costume_merges: int) -> None:
    store = LearningStore(folder)
    near = 60.0
    for _ in range(4):  # real merges: same look, faces alike
        store.add_identity("merge", True, [PairEvidence(0.85, 0.9, near)] * 3, FACE_VECTOR_VERSION, OUTFIT_VERSION)
    for _ in range(4):  # "different": faces 0.67, photos close in time: linked by default (face_strong 0.65)
        store.add_identity("different", False, [PairEvidence(0.67, 0.5, near)] * 3, FACE_VECTOR_VERSION,
                           OUTFIT_VERSION)
    for _ in range(cross_costume_merges):  # merges across costumes: look clearly different
        store.add_identity("merge", True, [PairEvidence(0.6, 0.3, 4000.0)] * 2, FACE_VECTOR_VERSION, OUTFIT_VERSION)
    store.add_identity("remove", False, [PairEvidence(0.2, 0.4, near)], FACE_VECTOR_VERSION, OUTFIT_VERSION)
    store.add_identity("merge", True, [PairEvidence(0.8, 0.9, near)], "old-face", "old-outfit")  # outdated cues
    store.close()


def _copy(folder: Path, tmp: Path) -> Path:
    dst = tmp / "copy"
    shutil.copytree(folder, dst)
    return dst


def test_audit_counts_grid_cv_and_contamination(tmp_path: Path) -> None:
    folder = tmp_path / "learning"
    _learning(folder, cross_costume_merges=3)
    copy = _copy(folder, tmp_path)
    report, filtered = la.audit(copy, SFACE_HSV)
    by = report["counts"]["by_kind"]
    assert by["merge_same"]["answers"] == 8 and by["merge_same"]["pairs"] == 4 * 3 + 3 * 2 + 1
    assert by["merge_same"]["pairs_current_face"] == 18  # the outdated row does not count
    assert by["different_different"]["answers"] == 4 and by["remove_different"]["answers"] == 1
    store = LearningStore(copy)
    expected = tuning.tune(store.identity_examples(), SFACE_HSV)
    store.close()
    t = report["tuning"]
    assert (t["applied"], t["face_shift"], t["look_shift"]) == (expected.applied, expected.face, expected.look)
    assert len(report["cost_grid"]) == len(tuning._SHIFTS) ** 2
    assert "face_p000_look_p000" in report["cost_grid"]
    cv = report["cross_validation"]
    assert cv["tuned_total"] >= 0 and cv["default_total"] >= 0 and any(k.startswith("fold_") for k in cv)
    assert t["applied"] is True and t["face_shift"] > 0  # stricter faces, learnt from the "different" answers
    assert report["answers_changed_by_learnt_tuning"] == {"different_different": 4}
    assert cv["tuned_total"] < cv["default_total"]
    pc = report["possible_contamination"]
    assert pc["hint_only"] is True and pc["same_answers_below_threshold"] == 3 and pc["by_kind"] == {"merge": 3}
    assert report["filtered_tuning"]["excluded_answers"] == 3
    assert filtered is not None
    dg.check_numbers_only({"learning_audit": report})


def test_audit_never_writes_the_learning_db_it_is_given_a_copy_of(tmp_path: Path) -> None:
    folder = tmp_path / "learning"
    _learning(folder, cross_costume_merges=2)
    before = {f.name: f.read_bytes() for f in folder.iterdir()}
    copy = _copy(folder, tmp_path)
    la.audit(copy, SFACE_HSV)
    assert {f.name: f.read_bytes() for f in folder.iterdir()} == before


def test_diagnose_reports_audit_and_filtered_learning(tmp_path: Path) -> None:
    p, _ = _session(tmp_path)
    p.close()
    folder = tmp_path / "learning"
    _learning(folder, cross_costume_merges=3)
    files = {f.name: f.read_bytes() for f in folder.iterdir()}
    report = dg.diagnose(p.folder, folder)
    assert {f.name: f.read_bytes() for f in folder.iterdir()} == files  # source learning.db untouched
    assert report["read_only"]["unchanged"] is True
    audit = report["learning_audit"]
    assert audit["available"] is True and audit["possible_contamination"]["same_answers_below_threshold"] == 3
    assert report["tuning"]["applied"] == audit["tuning"]["applied"]
    base = report["reconstructed_baseline"]
    assert base["filtered_learning_applied"] is True and "filtered_learning" in base and "tuned" in base
    assert base["filtered_learning"]["person"]["items"] == base["default"]["person"]["items"]


def test_audit_without_learning_data(tmp_path: Path) -> None:
    assert la.audit(None, SFACE_HSV) == ({"available": False}, None)
    report, filtered = la.audit(_copy(_empty(tmp_path), tmp_path), SFACE_HSV)
    assert report["tuning"]["reason_code"] == "no_usable_examples" and filtered is None


def _empty(tmp: Path) -> Path:
    LearningStore(tmp / "empty").close()
    return tmp / "empty"


def test_answer_kinds_numbers_pre_v5_rows_like_identity_examples(tmp_path: Path) -> None:
    folder = tmp_path / "l"
    _learning(folder, cross_costume_merges=0)
    store = LearningStore(folder)
    store.conn.execute("""INSERT INTO identity_feedback (created_on, app_version, face_version, outfit_version, kind,
                          same, face, outfit, dt_s, answer_id) VALUES ('2026-01-01', 'x', ?, ?, 'different', 0, 0.7,
                          0.5, 10, NULL)""", (FACE_VECTOR_VERSION, OUTFIT_VERSION))
    store.conn.commit()
    kinds = la.answer_kinds(store.conn)
    answers = {e.answer for e in store.identity_examples()}
    store.close()
    assert answers <= set(kinds) and kinds[min(answers)] == "different" and min(answers) < 0
    assert (folder / "learning.db").is_file()
