"""M6: shot size rule (spec v6 §5, SZ-01a…05) on synthetic boxes, and the analysis job with a stand-in detector.

These cases check the RULE only (boxes are given). How well YOLOX / YuNet find the boxes on real event photos is
[Ảnh mẫu]: scored with the sample-labelling scorer (M9) on the owner's photos.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.media import analysis
from app.media import cameras as cam
from app.media import event as ev
from app.media import labels as lb
from app.media import moments as mo
from app.media.shot import Subject, classify, subjects_from
from app.storage import provenance
from tests.media.fixtures import hashes, photo

W, H = 6000, 4000


def _face(h_frac: float, x: float = 2800, y: float = 600) -> tuple[float, float, float, float]:
    fh = h_frac * H
    return (x, y, fh * 0.8, fh)


def test_sz01a_blurred_close_up_with_a_face_is_can() -> None:
    r = classify([Subject((2000, 300, 2200, 3700), _face(0.25), 0.9)], W, H)
    assert (r.value, r.path) == ("can", "face")


def test_sz01b_close_up_without_a_face_is_unknown() -> None:
    r = classify([Subject((1500, 0, 3000, 3990), None, 0.8)], W, H)
    assert (r.value, r.path, r.confidence) == ("?", "body", None)


@pytest.mark.parametrize("x", [0, 2600, W - 1500])
def test_sz02_subject_at_the_edge_has_the_same_size_as_in_the_middle(x: float) -> None:
    person = (x, 800, 1500, 3000)
    r = classify([Subject(person, _face(0.08, x + 500, 900), 0.9)], W, H)
    assert r.value == "trung"


def test_sz03_object_close_up_without_people_is_unknown() -> None:
    r = classify([], W, H)
    assert (r.value, r.path) == ("?", "none")


def test_sz04_wide_hall_small_people_no_faces_is_toan() -> None:
    crowd = [Subject((300 + 500 * i, 1500, 150, 500), None, 0.6) for i in range(10)]
    assert classify(crowd, W, H).value == "toan"
    tiny_faces = [Subject((300 + 500 * i, 1500, 150, 500), _face(0.02, 320 + 500 * i, 1520), 0.8) for i in range(3)]
    assert classify(tiny_faces, W, H).value == "toan"


def test_sz05_audience_head_in_the_foreground_is_not_the_subject() -> None:
    head = Subject((2000, 2600, 2000, 1400), None, 0.7)  # big, blurred, touches the bottom edge, no face
    speaker = Subject((2800, 900, 300, 900), _face(0.03, 2850, 920), 0.85)
    r = classify([head, speaker], W, H)
    assert r.value == "toan" and r.subject == speaker
    assert r.measures["n_excluded"] == 1


def test_back_turned_and_cut_people_are_not_the_subject() -> None:
    back = Subject((1000, 200, 2500, 3600), None, 0.9)  # large, no face while someone else shows one
    cut = Subject((0, 300, 400, 3600), _face(0.2, 20, 320), 0.9)  # a sliver along the left edge
    speaker = Subject((4000, 1000, 900, 2500), _face(0.07, 4200, 1050), 0.8)
    r = classify([back, cut, speaker], W, H)
    assert r.value == "trung" and r.subject == speaker and r.measures["n_excluded"] == 2


def test_faces_pair_with_the_tightest_person() -> None:
    subjects = subjects_from([((0, 0, 1000, 2000), 0.9), ((100, 100, 400, 900), 0.8)],
                             [((200, 150, 100, 120), 0.95), ((3000, 3000, 50, 60), 0.9)])
    assert subjects[1].face == (200, 150, 100, 120) and subjects[0].face is None
    assert subjects[2].person is None and subjects[2].face == (3000, 3000, 50, 60)


# ------------------------------------------------------------------------------------------ the analysis job
DAY = datetime(2026, 6, 19, 9, 0, 0)


def _event(tmp_path: Path, n: int = 4):  # noqa: ANN202
    shoot = tmp_path / "MayA"
    for i in range(n):
        gap = 0 if i < 2 else 1800  # two moments: 09:00 and 09:30
        photo(shoot / f"P{i}.jpg", i, taken=(DAY + timedelta(seconds=60 * i + gap)).strftime("%Y:%m:%d %H:%M:%S"),
              make="NIKON", model="Z 6", size=(600, 400))
    e = ev.create_event("M6", tmp_path / "media")
    cam.import_folder(e, shoot)
    ids = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    return e, ids, shoot


def _fake(sizes: dict[int, float | None]):  # noqa: ANN202
    """A stand-in detector: photo i shows one person whose face is sizes[i] of the height (None: no person)."""
    calls = []

    def detect(bgr):  # noqa: ANN001, ANN202
        i = len(calls)
        calls.append(i)
        h, w = bgr.shape[:2]
        f = sizes.get(i)
        if f is None:
            return [], []
        return [((w * 0.3, h * 0.05, w * 0.4, h * 0.9), 0.9)], [((w * 0.45, h * 0.1, f * h * 0.8, f * h), 0.95)]

    return detect, calls


def test_analysis_writes_shot_sizes_with_their_run_and_keeps_user_choices(tmp_path: Path) -> None:
    e, ids, shoot = _event(tmp_path)
    before = hashes(shoot)
    lb.confirm(e, [ids["P3"]], "shot", "toan")  # the user's size: never overwritten
    detect, _ = _fake({0: 0.25, 1: 0.08, 2: None, 3: 0.3})
    s = analysis.analyse_event(e, detect=detect)
    assert (s.analysed, s.failed, s.unavailable) == (4, 0, None)
    got = {k: lb.labels_of(e.conn, a)["shot"] for k, a in ids.items()}
    assert got["P0"] == [("can", "suggested", 0.95)] and got["P1"][0][:2] == ("trung", "suggested")
    assert got["P2"] == [("?", "unknown", None)] and got["P3"] == [("toan", "confirmed", None)]
    run = e.conn.execute("SELECT mode, stage FROM analysis_runs WHERE id = ?", (s.run_id,)).fetchone()
    assert tuple(run) == ("media", analysis.STAGE)
    assert {r[0] for r in e.conn.execute("SELECT DISTINCT run_id FROM labels WHERE state = 'suggested'")} == {s.run_id}
    assert analysis.progress_of(e.conn) == {"total": 4, "done": 4, "failed": 0, "waiting": 0}
    assert s.moments == 2 and len(mo.moments(e.conn)) == 2
    assert hashes(shoot) == before
    again = analysis.analyse_event(e, detect=_fake({})[0])  # resumable: nothing left to do
    assert (again.analysed, again.already_done, again.run_id) == (0, 4, None)
    e.close()


def test_cancel_keeps_what_is_done_and_a_bad_photo_does_not_stop_the_event(tmp_path: Path) -> None:
    e, ids, _ = _event(tmp_path)
    calls = []

    def detect(bgr):  # noqa: ANN001, ANN202
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("decoder crashed")
        return [], []

    s = analysis.analyse_event(e, detect=detect, should_cancel=lambda: len(calls) >= 3)
    assert s.cancelled and (s.analysed, s.failed) == (2, 1)
    assert analysis.progress_of(e.conn)["waiting"] == 1
    assert mo.moments(e.conn) == []  # cancelled before the moments step
    s2 = analysis.analyse_event(e, detect=lambda bgr: ([], []))
    assert s2.analysed == 1 and not s2.cancelled and len(mo.moments(e.conn)) == 2
    e.close()


def test_without_detection_weights_nothing_is_guessed(tmp_path: Path) -> None:
    e, ids, _ = _event(tmp_path)

    class NoModels:
        def available(self, model_id: str) -> bool:
            return False

    s = analysis.analyse_event(e, registry=NoModels())
    assert s.unavailable == analysis.NO_DETECTION and s.analysed == 0 and s.run_id is None
    assert e.conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0] == 0
    assert analysis.progress_of(e.conn)["waiting"] == 4  # stays ⏳, not "Chưa xác định"
    assert len(mo.moments(e.conn)) == 2  # moments need no model (MT-F1)
    e.close()


def test_real_detectors_open_only_media_weights(tmp_path: Path) -> None:
    """With the dev weights: the job goes through MediaRegistry and the run lists only YOLOX / YuNet (report A)."""
    from app.ai.policy import LOAD_LOG
    from app.media.models import MediaRegistry

    media = MediaRegistry()
    if not analysis.detection_available(media):
        pytest.skip("YOLOX-S / YuNet with a pinned SHA-256 are not in this models folder")
    e, ids, _ = _event(tmp_path, n=2)
    s = analysis.analyse_event(e, registry=media, prefer_gpu=False)
    assert s.analysed == 2 and s.unavailable is None
    used = {m["model_id"] for m in s.models}
    assert used and used <= {"person_detector_s", "person_detector_m", "face_detector"}
    assert set(media.loaded) <= {"person_detector_s", "person_detector_m", "face_detector"}
    opened = set(LOAD_LOG.report()["opened"])
    assert not opened & {"face_embedder", "clip_l14_image", "arcface_r50", "topiq_iaa", "person_reid"}
    assert provenance.run_models(e.conn, s.run_id) == s.models
    e.close()
