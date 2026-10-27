"""ArcFace + ReID profile, the embed stage and per-user threshold tuning."""

from __future__ import annotations

import sqlite3
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.ai.identity_plus import ARCFACE_VERSION, BODY_VERSION
from app.ai.models import ModelRegistry, ModelState, load_manifest, sha256_of
from app.identity.cluster import (
    ARCFACE_REID, SFACE_HSV, Occ, group, look_similarity, pair_link, recluster, session_profile,
)
from app.identity.features import OUTFIT_VERSION
from app.learning.store import CueVersions, IdentityExample, LearningStore, PairEvidence
from app.learning.teacher import Teacher
from app.learning.tuning import MAX_SHIFT, _arrays, _linked, tune, tune_from_store
from app.storage.project import Project
from app.workers import embed_job
from app.workers.analyze_job import FACE_VECTOR_VERSION
from tests.unit.test_identity_cluster import RED, _add, _person, _shot, _subjects

V_ARC = CueVersions(FACE_VECTOR_VERSION, OUTFIT_VERSION, ARCFACE_VERSION, BODY_VERSION)
V_OLD = CueVersions(FACE_VECTOR_VERSION, OUTFIT_VERSION, "", "")


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "s", "x")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    yield p
    p.close()


def _vec(project: Project, occ: int, kind: str, v: np.ndarray) -> None:
    project.conn.execute("INSERT INTO occurrence_vectors VALUES (?, ?, 'v', ?)", (occ, kind, v.astype("<f4").tobytes()))


# ------------------------------------------------------------------ profile


def test_session_uses_arcface_only_when_it_has_arcface_vectors(project: Project) -> None:
    a, b = _person(), _person()
    occs = [_add(project, i, _shot(a), outfit=RED) for i in (1, 2)] + [_add(project, 3, _shot(b), outfit=RED)]
    assert session_profile(project.conn) is SFACE_HSV
    # ArcFace says 1 and 3 are the same person, SFace says 1 and 2: the ArcFace vectors must win.
    arc_x, arc_y = _person(), _person()
    for occ, arc in zip(occs, (_shot(arc_x, 0.1), _shot(arc_y, 0.1), _shot(arc_x, 0.1))):
        _vec(project, occ, "face_arc", arc)
    assert session_profile(project.conn) is ARCFACE_REID
    report = recluster(project)
    assert report.profile == "arcface+reid"
    assert sorted(_subjects(project).values()) == [[1, 3], [2]]


def test_look_mixes_colours_and_body_only_in_the_arcface_profile() -> None:
    body1, body2 = _person(), _person()
    a = Occ(1, 1, 0.0, None, RED, "none", None, None, body=body1)
    b = Occ(2, 2, 0.0, None, RED, "none", None, None, body=body2)
    assert look_similarity(a, b, SFACE_HSV) == pytest.approx(1.0)
    mixed = look_similarity(a, b, ARCFACE_REID)
    w = ARCFACE_REID.body_weight
    assert mixed == pytest.approx((1 - w) + w * float(body1 @ body2), abs=1e-5) and mixed < 0.9


def test_same_outfit_different_body_does_not_link_in_arcface_profile() -> None:
    """Two cosplayers in the same colours, no faces: the whole-body vector keeps them apart."""
    body1, body2 = _person(), _person()
    occs = [Occ(1, 1, 0.0, None, RED, "none", None, None, body=_shot(body1, 0.1)),
            Occ(2, 2, 60.0, None, RED, "none", None, None, body=_shot(body2, 0.1)),
            Occ(3, 3, 90.0, None, RED, "none", None, None, body=_shot(body1, 0.1))]
    members = sorted(sorted(occs[m].id for m in g.members) for g in group(occs, profile=ARCFACE_REID).groups if g.members)
    assert members == [[1, 3]]  # 2 is left alone (a lone face-less photo is not a person of its own)
    members_sface = sorted(sorted(occs[m].id for m in g.members) for g in group(occs).groups if g.members)
    assert members_sface == [[1, 2, 3]]  # colours alone cannot tell them apart


# ------------------------------------------------------------------ embed stage


class _FakeRefiner:
    def refine(self, bgr, nbox):  # noqa: ANN001, ANN201
        from app.quality.measure import FaceGeometry

        return FaceGeometry((0, 0, 10, 10), np.zeros((5, 2), np.float32), 0.9)


class _FakeEmbed:
    def __init__(self, n: int) -> None:
        self.n = n

    def embed(self, bgr, what):  # noqa: ANN001, ANN201
        v = np.ones(self.n, np.float32)
        return v / np.linalg.norm(v)


class _FakeModels:
    refiner, face, body = _FakeRefiner(), _FakeEmbed(512), _FakeEmbed(768)


def test_embed_stage_adds_vectors_without_touching_occurrences(project: Project) -> None:
    occ = _add(project, 1, _shot(_person()), outfit=RED)
    project.conn.execute("UPDATE occurrences SET face_box = '[0.2, 0.2, 0.1, 0.1]', face_score = 0.9 WHERE id = ?",
                         (occ,))
    lone = _add(project, 1, None)  # a second person, no face
    project.conn.execute("INSERT INTO stage_status VALUES (1, 'detect', 1, 'done', 1, NULL, 'n')")
    assert [a for a, _ in embed_job.queue(project)] == [1]
    before = project.conn.execute("SELECT * FROM occurrences ORDER BY id").fetchall()
    rows = project.conn.execute("SELECT id, person_box, face_box, face_score FROM occurrences").fetchall()
    embed_job.store(project, 1, embed_job.vectors_for(np.zeros((40, 40, 3), np.uint8), rows, _FakeModels()))
    kinds = project.conn.execute("SELECT occurrence_id, kind, model_version FROM occurrence_vectors "
                                 "WHERE kind IN ('face_arc', 'body') ORDER BY 1, 2").fetchall()
    assert [tuple(k) for k in kinds] == [(occ, "body", BODY_VERSION), (occ, "face_arc", ARCFACE_VERSION),
                                         (lone, "body", BODY_VERSION)]
    assert project.conn.execute("SELECT * FROM occurrences ORDER BY id").fetchall() == before
    assert embed_job.queue(project) == []  # done: not queued again


def test_embed_stage_does_nothing_without_its_models(project: Project, tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path / "no-models")
    assert embed_job.run(project, registry, lambda *a: None, lambda: False) == (0, 0, False)


def test_fetch_extracts_the_pinned_member_of_a_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.fetch_models as fetch

    payload = b"fake model weights" * 100
    archive = tmp_path / "srv" / "pack.zip"
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("other.onnx", b"x")
        zf.writestr("w.onnx", payload)
    (tmp_path / "w.onnx").write_bytes(payload)
    spec = replace(load_manifest()["face_embedder_arcface"], file="w.onnx", sha256=sha256_of(tmp_path / "w.onnx"),
                   size=len(payload), archive_member="w.onnx", url=archive.as_uri())
    (tmp_path / "w.onnx").unlink()
    dest = tmp_path / "models"
    monkeypatch.setattr(fetch, "ModelRegistry", lambda d: ModelRegistry(d, {spec.id: spec}))
    monkeypatch.setattr("sys.argv", ["fetch", "--dest", str(dest)])
    assert fetch.main() == 0
    assert (dest / "w.onnx").read_bytes() == payload
    assert sorted(p.name for p in dest.iterdir()) == ["w.onnx"]  # the archive itself is not kept
    assert ModelRegistry(dest, {spec.id: spec}).status(spec.id).state is ModelState.READY


def test_download_resumes_after_a_broken_transfer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import http.server
    import threading

    import scripts.fetch_models as fetch

    payload = bytes(range(256)) * 4000  # ~1 MB
    calls: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            rng = self.headers.get("Range")
            calls.append(rng)
            start = int(rng.split("=")[1].rstrip("-")) if rng else 0
            body = payload[start:]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if len(calls) == 1:  # first try: the connection drops half-way
                self.wfile.write(body[: len(body) // 2])
                self.wfile.flush()
                self.connection.shutdown(2)
                return
            self.wfile.write(body)

        def log_message(self, *a) -> None:  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    try:
        target = tmp_path / "m.onnx.part"
        fetch._download(f"http://127.0.0.1:{server.server_port}/m.onnx", target)
    finally:
        server.shutdown()
    assert target.read_bytes() == payload
    assert calls[0] is None and calls[1] == f"bytes={len(payload) // 2}-"  # continued, not restarted


def test_manifest_marks_arcface_as_non_commercial() -> None:
    specs = load_manifest()
    assert specs["face_embedder_arcface"].purpose == specs["body_reid"].purpose == "identity_plus"
    assert "NonCommercial" in specs["face_embedder_arcface"].license
    assert specs["body_reid"].license == "Apache-2.0"


# ------------------------------------------------------------------ learning


def _examples(rows: list[tuple[int, bool, float | None, float | None, float]], versions=V_ARC) -> list[IdentityExample]:
    """rows: (answer, same, arcface, outfit, dt_s); body = outfit so the look equals the outfit value."""
    return [IdentityExample(a, s, PairEvidence(None, o, dt, f, o), versions) for a, s, f, o, dt in rows]


def test_rules_and_vectorised_rules_agree() -> None:
    rng = np.random.default_rng(3)
    rows = [(i, bool(i % 2), float(rng.uniform(0.2, 0.9)) if i % 5 else None, float(rng.uniform(0.4, 1.0)),
             float(rng.choice([30, 200, 1000, 5000]))) for i in range(400)]
    d = _arrays(_examples(rows), ARCFACE_REID)
    for t in (ARCFACE_REID, ARCFACE_REID.shifted(0.04, -0.04)):
        expected = [pair_link(t, f, o, dt) is not None for _, _, f, o, dt in rows]
        assert _linked(d, t, np.ones(len(rows), bool)).tolist() == expected


def test_too_few_answers_keep_the_defaults() -> None:
    t = tune(_examples([(1, True, 0.6, 0.9, 60), (2, False, 0.7, 0.9, 60)]), ARCFACE_REID)
    assert not t.applied and "Cần thêm" in t.reason
    assert t.apply(ARCFACE_REID) is ARCFACE_REID
    assert not tune([], ARCFACE_REID).applied


def test_user_who_separates_lookalikes_gets_stricter_face_threshold() -> None:
    fs = ARCFACE_REID.face_strong
    rows = []
    for k in range(6):  # "different" answers: lookalike faces just above the face threshold, far apart in time
        rows += [(100 + k, False, fs + 0.01 + 0.005 * j, 0.95, 4000) for j in range(3)]
    for k in range(6):  # "same" answers: clear faces
        rows += [(200 + k, True, fs + 0.15, 0.95, 4000) for _ in range(3)]
    t = tune(_examples(rows), ARCFACE_REID)
    assert t.applied and t.face > 0 and t.face <= MAX_SHIFT
    tuned = t.apply(ARCFACE_REID)
    assert tuned.face_strong > fs + 0.02 and "khó gộp hơn" in t.describe()


def test_tuning_never_links_more_different_pairs_than_the_defaults() -> None:
    fs = ARCFACE_REID.face_strong
    rows = []
    for k in range(8):  # same person, faces a bit below the threshold: loosening would help ...
        rows += [(k, True, fs - 0.03, 0.2, 4000)]
    rows += [(50, False, fs - 0.03, 0.2, 4000), (51, False, fs - 0.03, 0.2, 4000)]  # ... but also join these
    t = tune(_examples(rows), ARCFACE_REID)
    assert not t.applied or t.face > -0.03


def test_examples_from_other_models_are_ignored() -> None:
    old = [IdentityExample(k, k % 2 == 0, PairEvidence(0.7, 0.9, 60), V_OLD) for k in range(10)]  # SFace only
    assert _arrays(old, ARCFACE_REID) is None  # faces not measured with ArcFace: nothing for that profile
    assert _arrays(old, SFACE_HSV) is not None
    assert _arrays(_examples([(k, k % 2 == 0, 0.7, 0.9, 60) for k in range(10)]), ARCFACE_REID) is not None


def test_store_v5_keeps_all_cues_and_upgrades_v4(tmp_path: Path) -> None:
    from app.learning import store as store_module

    folder = tmp_path / "learning"
    folder.mkdir()
    old = sqlite3.connect(folder / "learning.db")
    old.executescript(store_module._SCHEMA + store_module._SCHEMA_V2 + store_module._SCHEMA_V3 + store_module._SCHEMA_V4)
    old.execute("INSERT INTO identity_feedback (created_on, app_version, face_version, outfit_version, kind, same, face) "
                "VALUES ('2026-10-27', 'x', 'f', 'o', 'merge', 1, 0.7)")
    old.execute("PRAGMA user_version = 4")
    old.commit()
    old.close()
    store = LearningStore(folder)
    store.add_identity("different", False, [PairEvidence(0.5, 0.8, 30, 0.4, 0.6), PairEvidence(0.5, None, 40)],
                       "f", "o", ARCFACE_VERSION, BODY_VERSION)
    ex = store.identity_examples()
    assert len(ex) == 3 and ex[0].answer == ex[1].answer and ex[2].answer < 0  # pre-v5 row: its own answer
    newest = [e for e in ex if e.pair.face_arc is not None][0]
    assert newest.pair.body == 0.6 and newest.versions.arc == ARCFACE_VERSION
    assert [e for e in ex if e.pair.dt_s == 40][0].versions.arc == ""  # no ArcFace number: no version either
    store.close()


def test_teacher_records_arcface_and_body_numbers(project: Project, tmp_path: Path) -> None:
    from app.identity import actions

    a, b = _person(), _person()
    occs = [_add(project, 1, _shot(a), outfit=RED), _add(project, 2, _shot(b), minute=2, outfit=RED)]
    for occ in occs:
        _vec(project, occ, "face_arc", _person())
        _vec(project, occ, "body", _person())
    recluster(project)
    s1, s2 = sorted(_subjects(project))
    store = LearningStore(tmp_path / "learning")
    with project.transaction() as conn:
        Teacher(store).merged(conn, s1, s2)
        actions.merge_subjects(conn, s1, s2)
    [ex] = store.identity_examples()
    assert ex.same and None not in (ex.pair.face, ex.pair.face_arc, ex.pair.body, ex.pair.outfit)
    assert ex.versions == V_ARC
    store.close()
    assert not tune_from_store(tmp_path / "learning", ARCFACE_REID).applied  # one answer is not enough
    assert not tune_from_store(tmp_path / "nothing-here", ARCFACE_REID).applied


def test_learnt_shift_reaches_the_grouping(project: Project, tmp_path: Path) -> None:
    """analyze_job passes the tuning to recluster: a stricter face threshold splits a borderline pair."""
    face = _person()
    other = _unit_mix(face, ARCFACE_REID.face_strong + 0.02)
    o1 = _add(project, 1, _shot(face, 0.05), outfit=RED)
    o2 = _add(project, 2, _shot(face, 0.05), minute=50, outfit=_person())  # far apart in time, other outfit
    _vec(project, o1, "face_arc", face)
    _vec(project, o2, "face_arc", other)
    level = ARCFACE_REID.face_strong + 0.02
    recluster(project, lambda base: replace(base, face_strong=level - 0.05, face_certain=level - 0.01))
    assert len(_subjects(project)) == 1
    recluster(project, lambda base: replace(base, face_strong=level + 0.05, face_certain=level + 0.1))
    assert len(_subjects(project)) == 2


def _unit_mix(a: np.ndarray, similarity: float) -> np.ndarray:
    rng = np.random.default_rng(11)
    other = rng.normal(size=a.shape[0])
    other = other - (other @ a) * a
    other /= np.linalg.norm(other)
    v = similarity * a + (1 - similarity ** 2) ** 0.5 * other
    return (v / np.linalg.norm(v)).astype(np.float32)


# ------------------------------------------------------------------ real models (skip without weights)


def _registry_or_skip() -> ModelRegistry:
    registry = ModelRegistry()
    if not registry.ready("identity_plus") or registry.status("face_detector").state is not ModelState.READY:
        pytest.skip("ArcFace / ReID weights not fetched (scripts/fetch_models.py)")
    return registry


def test_real_arcface_and_reid_produce_unit_vectors() -> None:
    import cv2

    registry = _registry_or_skip()
    models = embed_job.Embedders(registry, prefer_gpu=False)
    from app.quality.measure import FACE_REFERENCE, FaceGeometry

    img = np.full((224, 224, 3), 128, np.uint8)
    cv2.circle(img, (112, 100), 60, (150, 170, 200), -1)
    geo = FaceGeometry((52, 40, 120, 120), FACE_REFERENCE * 2, 0.9)
    face = models.face.embed(img, geo)
    body = models.body.embed(img, (0.1, 0.0, 0.8, 1.0))
    assert face.shape == (512,) and body.shape == (768,)
    assert abs(float(np.linalg.norm(face)) - 1) < 1e-4 and abs(float(np.linalg.norm(body)) - 1) < 1e-4
    assert models.body.embed(img, (0.0, 0.0, 0.05, 0.05)) is None  # too small to describe a person


# ------------------------------------------------------------------ owner's report 2026-10-27 (bundle 3)


def test_person_never_prominent_in_a_small_group_is_background(project: Project) -> None:
    """A blurred person behind the cosplayer in 2 photos must not become a subject of their own."""
    lead, behind = _person(), _person()
    for asset in (1, 2):
        _add(project, asset, _shot(lead), minute=asset, outfit=RED)
        occ = _add(project, asset, _shot(behind), minute=asset, outfit=RED)
        project.conn.execute("UPDATE occurrences SET prominence = 0.5 WHERE id = ?", (occ,))
    recluster(project)
    assert sorted(_subjects(project).values()) == [[1, 2]]
    duo = []  # a duo partner close to the lead's size, or in many photos, stays a subject
    for asset in range(10, 15):
        _add(project, asset, _shot(lead), minute=20 + asset, outfit=RED)
        duo.append(_add(project, asset, _shot(behind), minute=20 + asset, outfit=RED))
    project.conn.executemany("UPDATE occurrences SET prominence = 0.6 WHERE id = ?", [(o,) for o in duo])
    recluster(project)
    assert len(_subjects(project)) == 2


def test_merging_keeps_one_occurrence_per_photo(project: Project) -> None:
    from app.identity import actions

    a, b = _person(), _person()
    main = _add(project, 1, _shot(a), outfit=RED)
    behind = _add(project, 1, _shot(b), outfit=RED)
    _add(project, 2, _shot(a), outfit=RED)
    project.conn.execute("UPDATE occurrences SET prominence = 0.5 WHERE id = ?", (behind,))
    with project.transaction() as conn:
        for sid, occ in ((1, main), (2, behind)):
            conn.execute("INSERT INTO subjects (id, created_at) VALUES (?, 'n')", (sid,))
            conn.execute("UPDATE occurrences SET subject_id = ?, assignment = 'auto' WHERE id = ?", (sid, occ))
        actions.merge_subjects(conn, 1, 2)
    rows = dict(project.conn.execute("SELECT id, subject_id FROM occurrences WHERE asset_id = 1").fetchall())
    assert rows == {main: 1, behind: None}
    assert project.conn.execute("SELECT excluded_subject_id FROM occurrences WHERE id = ?", (behind,)).fetchone()[0] == 1


def test_unidentified_lists_only_photos_without_any_subject(project: Project) -> None:
    from app.identity.actions import UNIDENTIFIED_ASSETS

    a = _person()
    _add(project, 1, _shot(a), outfit=RED)
    _add(project, 1, None)  # an unknown second person next to the known one
    _add(project, 2, _shot(a), outfit=RED)
    _add(project, 3, None)  # nobody known in this photo
    recluster(project)
    assert [r[0] for r in project.conn.execute(UNIDENTIFIED_ASSETS)] == [3]


def test_person_boxes_of_both_detectors_are_merged() -> None:
    """DSC_0117: YOLOX-M took a kigurumi cosplayer for a teddy bear; YOLOX-S found her."""
    from types import SimpleNamespace

    from app.ai.detect import PersonDetector

    def fake(cell: int, score: float) -> SimpleNamespace:
        def run(_names, _feeds):  # noqa: ANN001, ANN202
            out = np.zeros((1, 8400, 85), np.float32)
            out[0, :, 2:4] = np.log(4.0)  # 4 strides wide/high boxes, logits for "nobody" below
            out[0, cell, 4], out[0, cell, 5] = score, 1.0
            return [out]
        inner = SimpleNamespace(run=run, get_inputs=lambda: [SimpleNamespace(name="images")])
        return SimpleNamespace(session=inner, run=run, device="cuda", fallback_reason=None)

    medium_misses_her, small_finds_her = fake(0, 0.0), fake(4000, 0.87)
    found = PersonDetector(medium_misses_her, small_finds_her).detect(np.zeros((640, 640, 3), np.uint8))
    assert len(found) == 1 and found[0][1] == pytest.approx(0.87)
    assert PersonDetector(medium_misses_her).detect(np.zeros((640, 640, 3), np.uint8)) == []


def test_registry_accepts_float16_weights_only_from_the_pinned_original(tmp_path: Path) -> None:
    """scripts/shrink_models.py writes "<sha> <size> fp16w-of:<original sha>" next to the file."""
    import hashlib

    original, shrunk = b"original weights" * 100, b"half weights" * 50
    spec = replace(load_manifest()["face_embedder_arcface"], file="m.onnx",
                   sha256=hashlib.sha256(original).hexdigest(), size=len(original))
    (tmp_path / "m.onnx").write_bytes(shrunk)
    registry = lambda: ModelRegistry(tmp_path, {spec.id: spec})  # noqa: E731
    assert registry().status(spec.id).state is ModelState.CORRUPT  # no sidecar: not the pinned file
    sidecar = tmp_path / "m.onnx.sha256"
    sidecar.write_text(f"{hashlib.sha256(shrunk).hexdigest()} {len(shrunk)} fp16w-of:{'0' * 64}\n")
    assert registry().status(spec.id).state is ModelState.CORRUPT  # made from some other file
    sidecar.write_text(f"{hashlib.sha256(shrunk).hexdigest()} {len(shrunk)} fp16w-of:{spec.sha256}\n")
    assert registry().status(spec.id).state is ModelState.READY
    (tmp_path / "m.onnx").write_bytes(shrunk[:-1] + b"X")  # tampered after shrinking
    assert registry().status(spec.id).state is ModelState.CORRUPT


def test_new_subject_from_photos_survives_regrouping(project: Project) -> None:
    from app.identity import actions

    a, stranger = _person(), _person()
    for asset in (1, 2):
        _add(project, asset, _shot(a), outfit=RED)
    lone = _add(project, 3, _shot(stranger), minute=30, outfit=RED)
    project.conn.execute("UPDATE occurrences SET prominence = 0.5 WHERE id = ?", (lone,))  # a 'background' group
    recluster(project)
    assert sorted(_subjects(project).values()) == [[1, 2]]  # photo 3 is nobody yet
    with project.transaction() as conn:
        sid = actions.create_subject(conn, [3], "  Kana ")
    recluster(project)
    assert _subjects(project)[sid] == [3] and actions.subject_label(project.conn, sid) == "Kana"
    with project.transaction() as conn:
        unnamed = actions.create_subject(conn, [3], from_subject=sid)  # moved out of Kana, no name: a number
    recluster(project)
    assert _subjects(project).get(unnamed) == [3] and sid not in _subjects(project)
    assert project.conn.execute("SELECT 1 FROM subjects WHERE id = ?", (sid,)).fetchone()  # a named subject stays


def test_new_subjects_are_numbered_in_shooting_order_and_list_orders(project: Project) -> None:
    from app.identity import actions

    early, late = _person(), _person()
    for asset, minute in ((1, 50), (2, 51), (3, 52)):  # the later person has more photos
        _add(project, asset, _shot(late), minute=minute, outfit=RED)
    for asset, minute in ((4, 1), (5, 2)):
        _add(project, asset, _shot(early), minute=minute, outfit=RED)
    recluster(project)
    subjects = _subjects(project)
    first, second = sorted(subjects)
    assert subjects[first] == [4, 5] and subjects[second] == [1, 2, 3]  # numbered by time, not size
    assert [r["id"] for r in actions.subjects_summary(project.conn, "number")] == [first, second]
    assert [r["id"] for r in actions.subjects_summary(project.conn, "photos")] == [second, first]
    assert [r["id"] for r in actions.subjects_summary(project.conn, "time")] == [first, second]
    actions.rename_subject(project.conn, second, "Aki")
    assert [r["id"] for r in actions.subjects_summary(project.conn, "name")] == [second, first]


def test_renumbering_keeps_every_reference(project: Project) -> None:
    import json

    from app.identity import actions

    people = [_person() for _ in range(3)]
    for k, face in enumerate(people):
        for j in range(2):
            _add(project, 10 * k + j + 1, _shot(face), minute=20 * k + j, outfit=RED)
    recluster(project)
    by_time = [r["id"] for r in actions.subjects_summary(project.conn, "time")]
    with project.transaction() as conn:  # make the numbers jump, as after many corrections
        conn.execute("PRAGMA defer_foreign_keys = ON")
        for old, new in zip(by_time, (57, 12, 60)):
            for table, col in (("subjects", "id"), ("occurrences", "subject_id")):
                conn.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (new, old))
        actions.rename_subject(conn, 12, "Aki")
        actions.mark_different(conn, 57, 60)
        conn.execute("INSERT INTO decisions (asset_id, subject_id, flag, updated_at) VALUES (1, 57, 'keep', 'n')")
        conn.execute("INSERT INTO pick_runs (id, created_at, params_json) VALUES (1, 'n', ?)",
                     (json.dumps({"mode": "in_view", "subject_id": 60}),))
    before = {tuple(v): None for v in _subjects(project).values()}
    with project.transaction() as conn:
        mapping = actions.renumber_subjects(conn)
    assert mapping == {57: 1, 12: 2, 60: 3}
    after = _subjects(project)
    assert sorted(after) == [1, 2, 3] and {tuple(v) for v in after.values()} == set(before)
    assert after[1] == [1, 2] and actions.subject_label(project.conn, 2) == "Aki"
    assert [tuple(r) for r in project.conn.execute("SELECT a, b FROM subject_pairs")] == [(1, 3)]
    assert project.conn.execute("SELECT subject_id FROM decisions").fetchone()[0] == 1
    assert json.loads(project.conn.execute("SELECT params_json FROM pick_runs").fetchone()[0])["subject_id"] == 3
    assert project.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    with project.transaction() as conn:
        assert actions.renumber_subjects(conn) == {}  # already 1, 2, 3


def test_gpu_failure_at_run_time_switches_the_model_to_cpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Installer 2.0.4 on DirectML: every photo failed in the quality stage; a GPU error must not lose them."""
    from app.ai import runtime

    model = ModelRegistry().status("face_detector").path  # any small model file; never really loaded here
    calls: list[str] = []

    class Broken:
        def run(self, *_a):  # noqa: ANN002, ANN202
            calls.append("gpu")
            raise RuntimeError("DML: operator not supported for this shape")

    class Cpu:
        def __init__(self, path, sess_options=None, providers=None):  # noqa: ANN001
            assert providers == ["CPUExecutionProvider"] and Path(path) == model

        def run(self, *_a):  # noqa: ANN002, ANN202
            calls.append("cpu")
            return ["ok"]

    monkeypatch.setattr(runtime.ort, "InferenceSession", Cpu)
    session = runtime.Session(Broken(), "directml", None, model)
    assert session.run(None, {}) == ["ok"] and session.device == "cpu"
    assert "chuyển sang CPU" in session.fallback_reason
    assert session.run(None, {}) == ["ok"] and calls == ["gpu", "cpu", "cpu"]  # stays on the CPU
    cpu_only = runtime.Session(Broken(), "cpu", None, model)
    with pytest.raises(RuntimeError):  # a CPU error is a real error
        cpu_only.run(None, {})


def test_fastest_graphics_card_is_chosen_and_slow_ones_are_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner's laptop: Intel UHD (adapter 0, draws the screen) + RTX 2080 (adapter 1). DirectML on
    adapter 0 was slower than the CPU; the fastest adapter must be found and used."""
    import time
    from types import SimpleNamespace

    from app.ai import runtime

    def slow(ms: float):  # noqa: ANN202
        def run(*_a):  # noqa: ANN002, ANN202
            time.sleep(ms / 1000)
            return [None]
        return run

    def fake_ort_session(path, sess_options=None, providers=None):  # noqa: ANN001, ANN202
        device = providers[0][1]["device_id"]
        return SimpleNamespace(run=slow(timings[device]), get_providers=lambda: ["DmlExecutionProvider"],
                               get_inputs=lambda: [SimpleNamespace(name="x", shape=[1, 3, 8, 8])])

    def fake_create_session(model, prefer_gpu=True, **_k):  # noqa: ANN001, ANN202 - the CPU
        inner = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name="x", shape=[1, 3, 8, 8])])
        return SimpleNamespace(session=inner, run=slow(10), device="cpu", fallback_reason=None)

    monkeypatch.setattr(runtime, "configure", lambda: SimpleNamespace(available=["DmlExecutionProvider", "CPUExecutionProvider"]))
    monkeypatch.setattr(runtime, "list_gpus", lambda: [
        {"index": 0, "name": "Intel(R) UHD Graphics", "software": False},
        {"index": 1, "name": "NVIDIA GeForce RTX 2080 Super with Max-Q Design", "software": False},
        {"index": 2, "name": "Microsoft Basic Render Driver", "software": True}])
    monkeypatch.setattr(runtime.ort, "InferenceSession", fake_ort_session)
    monkeypatch.setattr(runtime, "create_session", fake_create_session)
    try:
        timings = {0: 40, 1: 2}
        runtime._speed_cache.clear()
        use, note = runtime.gpu_speed_check(Path("m.onnx"), runs=2)
        assert use and runtime._dml_device == 1 and "RTX 2080" in note and "Intel" in note, note
        assert runtime._gpu_attempts(["DmlExecutionProvider"], 1024) == [
            ("directml", [("DmlExecutionProvider", {"device_id": 1}), "CPUExecutionProvider"])]

        timings = {0: 40, 1: 30}  # every card slower than the CPU (10 ms): CPU
        runtime._speed_cache.clear()
        runtime._dml_device = None
        use, note = runtime.gpu_speed_check(Path("m.onnx"), runs=2)
        assert not use and "chậm hơn CPU" in note and runtime._dml_device is None, note
    finally:
        runtime._speed_cache.clear()
        runtime._dml_device = None
