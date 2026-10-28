"""Learned sharpness: the owner's Q/W/R labels teach where "nét căng / hơi soft / lệch nét" lie per camera."""

from __future__ import annotations

import numpy as np

from app.learning.focus import FocusExample, train_focus

CAM = "NIKON Z 5 + 24-70mm f/2.8G"


def _examples(n_each: int, rng: np.random.Generator, camera: str = CAM, noise: bool = False) -> list[FocusExample]:
    out = []
    centres = {0: 0.40, 1: 0.28, 2: 0.12}  # this camera's sharp eyes measure only ~0.40 (owner's Z5 shoot)
    for label, centre in centres.items():
        for i in range(n_each):
            eye = float(rng.uniform(0.05, 0.5)) if noise else centre + float(rng.normal(0, 0.02))
            out.append(FocusExample(label, f"g{i % 3}", camera, {"eye_sharp": eye, "tech_iqa": 0.6}))
    return out


def test_learns_this_cameras_scale() -> None:
    status = train_focus(_examples(10, np.random.default_rng(0)))[CAM]
    assert status.ready, status.reason
    m = status.model
    assert m.score({"eye_sharp": 0.41, "tech_iqa": 0.6}) > 80  # sharp for THIS camera (absolute scale said 43)
    assert 25 < m.score({"eye_sharp": 0.28, "tech_iqa": 0.6}) < 75
    assert m.score({"eye_sharp": 0.10, "tech_iqa": 0.6}) < 25
    assert m.label({"eye_sharp": 0.10, "tech_iqa": 0.6}) == "missed"


def test_needs_enough_labels_of_each_kind() -> None:
    status = train_focus(_examples(4, np.random.default_rng(1)))[CAM]
    assert not status.ready and "8" in status.reason


def test_labels_that_the_measurements_cannot_explain_are_not_used() -> None:
    status = train_focus(_examples(12, np.random.default_rng(2), noise=True))[CAM]
    assert not status.ready and "khớp" in status.reason


def test_each_camera_learns_separately() -> None:
    other = "SONY ILCE-7M4 + FE 85mm F1.8"
    result = train_focus(_examples(10, np.random.default_rng(3)) + _examples(2, np.random.default_rng(4), other))
    assert result[CAM].ready and not result[other].ready


def test_labels_are_kept_in_the_session_and_in_the_learning_store(tmp_path) -> None:  # noqa: ANN001
    from app.learning.store import LearningStore
    from app.learning.teacher import Teacher, photo_key
    from app.storage import decisions
    from app.storage.project import Project

    with Project.create(tmp_path / "s", "t") as project:
        conn = project.conn
        src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
        aid = conn.execute(
            "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
            "quick_hash, status, added_at, updated_at) VALUES (?, 'a.nef', 'nef', 'raw', 'full', 1, 1, 'h', 'ok', "
            "'t', 't')", (src,)).lastrowid
        decisions.set_focus(conn, aid, "soft")
        assert decisions.get(conn, aid).focus == "soft"
        decisions.set_focus(conn, aid, None)
        assert decisions.get(conn, aid).focus is None
    store = LearningStore(tmp_path / "learning")
    t = Teacher(store)
    key = photo_key("s", 1)
    t.focus_labeled(key, CAM, "g", "sharp", {"eye_sharp": 0.4})
    t.focus_labeled(key, CAM, "g", "missed", {"eye_sharp": 0.4})  # changed its mind: replaced
    ex = store.focus_examples()
    assert [(e.label, e.camera, e.features["eye_sharp"]) for e in ex] == [(2, CAM, 0.4)]
    t.focus_labeled(key, CAM, "g", None, {})
    assert store.focus_examples() == []
    store.close()


def test_session_reference_lifts_a_camera_whose_sharp_photos_measure_low() -> None:
    from app.learning import focus
    from app.quality.score import score

    focus.use_models({})
    values = {i: {"eye_sharp": 0.30 + 0.01 * (i % 10)} for i in range(12)}  # this camera: best ~0.39
    cams = dict.fromkeys(values, ("NIKON", "Z 5", "24-70mm"))
    over = focus.focus_overrides(cams, values)
    assert over[9].factor == 2.0 or over[9].factor > 1.5  # lifted (capped at 2x)
    plain, lifted = score(values[9]), score(values[9], over[9])
    assert lifted.parts["focus"] > plain.parts["focus"] + 20
    assert "buổi này" in lifted.reasons["focus"]
    few = focus.focus_overrides(dict(list(cams.items())[:5]), dict(list(values.items())[:5]))
    assert few == {}  # under 10 photos of one camera: the fixed scale stays


def test_session_reference_never_lowers_and_is_capped() -> None:
    from app.learning import focus

    focus.use_models({})
    sharp = {i: {"eye_sharp": 0.8} for i in range(12)}
    assert focus.focus_overrides(dict.fromkeys(sharp, (None, None, None)), sharp) == {}
    blurry = {i: {"eye_sharp": 0.05} for i in range(12)}
    over = focus.focus_overrides(dict.fromkeys(blurry, (None, None, None)), blurry)
    assert over[0].factor == focus.SESSION_MAX_FACTOR


def test_a_ready_learned_model_replaces_the_focus_part_and_warns_when_missed() -> None:
    from app.learning import focus
    from app.quality.score import score

    status = train_focus(_examples(10, np.random.default_rng(0)))
    focus.use_models(status)
    try:
        values = {1: {"eye_sharp": 0.41, "tech_iqa": 0.6}, 2: {"eye_sharp": 0.10, "tech_iqa": 0.6}}
        cams = dict.fromkeys(values, ("NIKON Z 5", None, "24-70mm f/2.8G"))
        assert focus.camera_key(*cams[1]) == CAM
        over = focus.focus_overrides(cams, values)
        good, bad = score(values[1], over[1]), score(values[2], over[2])
        assert good.parts["focus"] > 80 and "bạn dạy" in good.reasons["focus"]
        assert bad.parts["focus"] < 25 and "lệch nét / rung" in bad.warnings
    finally:
        focus.use_models({})


def test_camera_key_names_body_and_lens_once() -> None:
    from app.learning.focus import camera_key

    assert camera_key("NIKON CORPORATION", "NIKON Z 5", "24-70mm f/2.8G") == "NIKON Z 5 + 24-70mm f/2.8G"
    assert camera_key("SONY", "ILCE-7M4", None) == "Sony ILCE-7M4"
    assert camera_key(None, None, None) == "máy không rõ"
