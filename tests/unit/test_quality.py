"""Quality measurements, rubric and best-shot selection on synthetic data with known answers."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.quality.measure import FaceGeometry, edge_sharpness, exposure, eye_region, framing, layout_descriptor
from app.quality.score import WEIGHTS, score
from app.quality.select import Candidate, choose, save_run, select_in_view, select_per_person
from app.quality.score import Score
from app.storage import decisions
from app.storage.project import Project


def _texture(size: int = 200, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.kron(rng.integers(0, 2, (size // 10, size // 10)), np.ones((10, 10))) * 160 + 40
    return img.astype(np.uint8)  # crisp 10 px checker cells: one-pixel edges


def test_edge_sharpness_falls_with_blur_and_ignores_brightness() -> None:
    sharp = _texture()
    values = [edge_sharpness(cv2.GaussianBlur(sharp, (0, 0), s)) if s else edge_sharpness(sharp) for s in (0, 1, 2, 4)]
    assert values[0] > 0.8 and values == sorted(values, reverse=True) and values[3] < 0.2
    darker = (sharp.astype(np.float32) * 0.4).astype(np.uint8)  # same focus, less light
    assert abs(edge_sharpness(darker) - values[0]) < 0.1
    assert edge_sharpness(np.full((100, 100), 128, np.uint8)) is None  # flat: cannot judge focus
    assert edge_sharpness(sharp[:10, :10]) is None  # too small


def test_eye_region_exposure_framing() -> None:
    face = FaceGeometry((100, 100, 200, 200), np.array([[150, 170], [250, 170], [200, 220], [160, 260], [240, 260]],
                                                       np.float32), 0.9)
    x0, y0, x1, y1 = eye_region(face, 1000, 1000)
    assert x0 < 150 and x1 > 250 and y0 < 170 < y1 and y1 - y0 < 100
    bright = np.full((50, 50, 3), 255, np.uint8)
    assert exposure(bright)["clip"] == 1.0 and exposure(np.zeros((50, 50, 3), np.uint8))["dark"] == 1.0
    f = framing((0.0, 0.1, 0.3, 0.8), (0.1, 0.0, 0.1, 0.1))
    assert f["cut_side"] == 1.0 and f["cut_head"] == 1.0 and f["area"] == pytest.approx(0.24)
    assert framing(None, None)["area"] is None


def test_layout_tells_poses_apart() -> None:
    def figure(arm_up: bool, shift: int = 0) -> np.ndarray:
        img = np.full((400, 300, 3), 30, np.uint8)
        cv2.rectangle(img, (130 + shift, 120), (170 + shift, 330), (220, 220, 220), -1)  # body
        cv2.circle(img, (150 + shift, 95), 22, (220, 220, 220), -1)  # head
        end = (210 + shift, 40) if arm_up else (220 + shift, 240)
        cv2.line(img, (165 + shift, 140), end, (220, 220, 220), 12)
        return img
    box = (100 / 300, 20 / 400, 140 / 300, 330 / 400)
    up, up2, down = (layout_descriptor(figure(a, s), box) for a, s in ((True, 0), (True, 2), (False, 0)))
    assert float(up @ up2) > float(up @ down) + 0.1
    assert layout_descriptor(figure(True), None) is None


def test_rubric_spreads_missing_weight_and_warns() -> None:
    full = score({"eye_sharp": 0.8, "face_quality": 0.8, "face_clip": 0.0, "face_luma": 55, "area": 0.4,
                  "offcentre": 0.1, "cut_head": 0.0, "cut_side": 0.0})
    total_weight = sum(WEIGHTS.values())
    assert full.total == 100 and not full.warnings
    assert full.confidence == pytest.approx(1 - (WEIGHTS["eyes"] + WEIGHTS["aesthetic"]) / total_weight, abs=0.01)
    no_face = score({"body_sharp": 0.8, "body_clip": 0.0, "body_luma": 55, "area": 0.4, "offcentre": 0.1})
    assert no_face.parts["face"] is None and no_face.total == 100  # N/A is not a zero
    assert no_face.confidence == pytest.approx(
        1 - (WEIGHTS["face"] + WEIGHTS["eyes"] + WEIGHTS["aesthetic"]) / total_weight, abs=0.01)
    bad = score({"eye_sharp": 0.1, "face_quality": 0.2, "face_clip": 0.3, "face_luma": 95, "area": 0.4,
                 "cut_head": 1.0})
    assert bad.total < 25 and len(bad.warnings) == 4
    low_key = score({"body_sharp": 0.8, "body_clip": 0.0, "body_luma": 12, "area": 0.4})
    assert low_key.parts["exposure"] >= 50  # dark, intentional lighting is only mildly penalised
    assert score({}).total is None


def _cand(i: int, total: float, layout: np.ndarray, t: float) -> Candidate:
    return Candidate(i, i, Score(total, {}, 1.0), t, layout)


def test_selection_prefers_different_poses_over_burst_copies() -> None:
    a, b = np.eye(4, dtype=np.float32)[0], np.eye(4, dtype=np.float32)[1]
    cands = [_cand(1, 90, a, 0), _cand(2, 89, a, 0.5), _cand(3, 88, a, 1.0),  # one burst, same pose
             _cand(4, 80, b, 60), _cand(5, 30, b, 120)]
    picked = [c.asset_id for c, _ in choose(cands, 2)]
    assert picked == [1, 4]  # second pick is the other pose, not the 89-point copy
    assert [c.asset_id for c, _ in choose(cands, 10)][:2] == [1, 4] and len(choose(cands, 10)) == 5
    assert choose([Candidate(9, 9, Score(None, {}, 0), None, None)], 3) == []  # unscored never picked


# ---------------------------------------------------------------- with a DB


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "s", "x")
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/r', 'n')")
    yield p
    p.close()


def add_scored(p: Project, asset: int, subject: int | None, sharp: float, layout: np.ndarray, second: int = 0) -> None:
    conn = p.conn
    if not conn.execute("SELECT 1 FROM assets WHERE id = ?", (asset,)).fetchone():
        conn.execute(
            """INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, capture_time, added_at, updated_at)
               VALUES (?, 1, ?, '.nef', 'raw', 'verified', 1, 1, ?, 'ok', ?, 'n', 'n')""",
            (asset, f"DSC_{asset:04d}.NEF", str(asset), f"2026-10-25T10:{asset % 60:02d}:{second:02d}"))
    if subject is not None and not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject,)).fetchone():
        conn.execute("INSERT INTO subjects (id, created_at) VALUES (?, 'n')", (subject,))
    occ = int(conn.execute(
        """INSERT INTO occurrences (asset_id, person_box, prominence, is_main, subject_id, assignment, analysis_version,
           created_at) VALUES (?, '[0.2,0.1,0.5,0.8]', 1.0, 1, ?, 'auto', 1, 'n')""", (asset, subject)).lastrowid)
    conn.execute("""INSERT INTO measurements (asset_id, occurrence_id, extractor, extractor_version, input_source,
                    values_json, computed_at) VALUES (?, ?, 'quality', 'q1', 'embedded_jpeg', ?, 'n')""",
                 (asset, occ, json.dumps({"body_sharp": sharp, "body_clip": 0.0, "body_luma": 50, "area": 0.4,
                                          "offcentre": 0.1})))
    conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'layout', 'v', ?)", (occ, layout.astype("<f4").tobytes()))


def test_per_person_selection_and_saved_run(project: Project) -> None:
    a, b = np.eye(4, dtype=np.float32)[0], np.eye(4, dtype=np.float32)[1]
    for asset, sharp, lay in ((1, 0.7, a), (2, 0.69, a), (3, 0.5, b), (4, 0.3, b)):
        add_scored(project, asset, 1, sharp, lay)
    add_scored(project, 5, 2, 0.6, a)  # another person with a single photo
    add_scored(project, 3, 2, 0.6, b)  # photo 3 also shows person 2
    picks = select_per_person(project.conn, 2)
    by_person = {}
    for p in picks:
        by_person.setdefault(p.subject_id, []).append(p.asset_id)
    assert by_person == {1: [1, 3], 2: [5, 3]} or by_person == {1: [1, 3], 2: [3, 5]}
    with project.transaction() as conn:
        save_run(conn, picks, {"n": 2})
        save_run(conn, select_in_view(conn, 1, {1, 2, 4}), {"n": 1})  # replaces the previous run
    assert [r[0] for r in project.conn.execute("SELECT asset_id FROM picks")] == [1]
    assert decisions.get(project.conn, 1).flag is None  # choosing never sets a flag by itself


def test_explanation_lists_strengths_weaknesses_and_not_judged() -> None:
    good = score({"eye_sharp": 0.8, "face_quality": 0.8, "face_clip": 0.0, "face_luma": 55, "area": 0.4,
                  "offcentre": 0.1, "cut_head": 0.0, "cut_side": 0.0, "face_sharp": 0.7, "blink": 0.05})
    assert good.strengths == ["mắt mở", "nét ở mắt", "mặt rõ, dễ nhìn", "sáng tốt, mặt không cháy",
                              "bố cục gọn, đủ người"]
    assert not good.weaknesses and good.not_rated == ["thẩm mỹ tổng thể (chưa có mô hình)"]
    closed = score({"eye_sharp": 0.8, "blink": 0.7, "area": 0.4})
    assert "mắt nhắm hoặc nhìn xuống (nếu cố ý thì bỏ qua)" in closed.weaknesses and closed.parts["eyes"] == 15
    sleepy = score({"eye_sharp": 0.8, "blink": 0.4, "area": 0.4})
    assert "mắt hơi khép / lim dim" in sleepy.weaknesses and 40 < sleepy.parts["eyes"] < 100
    back_view = score({"body_sharp": 0.5, "body_clip": 0.0, "body_luma": 12, "area": 0.03, "cut_side": 1.0})
    assert "nét chưa tới, hơi mềm" in back_view.weaknesses
    assert "tối (nếu chụp low-key có chủ ý thì bỏ qua)" in back_view.weaknesses
    assert {"người bị cắt ở mép ảnh", "người quá nhỏ trong khung"} <= set(back_view.weaknesses)
    assert any(t.startswith("khuôn mặt (không thấy rõ mặt") for t in back_view.not_rated)
    assert "mắt nhắm/mở (không thấy rõ mắt)" in back_view.not_rated
    burnt = score({"eye_sharp": 0.1, "face_quality": 0.2, "face_clip": 0.3, "face_luma": 70, "area": 0.4})
    assert burnt.weaknesses.count("mặt bị cháy sáng") == 1 and "lệch nét / rung" in burnt.weaknesses


def _with_cosine(base: np.ndarray, cos: float, seed: int) -> np.ndarray:
    other = np.random.default_rng(seed).normal(size=base.shape).astype(np.float32)
    other -= (other @ base) * base
    other /= np.linalg.norm(other)
    return (cos * base + (1 - cos**2) ** 0.5 * other).astype(np.float32)


def test_owner_case_a_better_different_pose_beats_a_mere_landscape_crop() -> None:
    """Owner's report (DSC_9928/9929/9939): 74-point landscape crop chosen over a 79-point new pose."""
    base = np.random.default_rng(3).normal(size=64).astype(np.float32)
    base /= np.linalg.norm(base)
    hands_on_head = _cand(9928, 80, base, 0)
    landscape = _cand(9929, 74, _with_cosine(base, 0.74, 1), 13)
    arms_crossed = _cand(9939, 79, _with_cosine(base, 0.79, 2), 120)
    picked = [c.asset_id for c, _ in choose([hands_on_head, landscape, arms_crossed], 2)]
    assert picked == [9928, 9939]
    burst_copy = _cand(9930, 85, _with_cosine(base, 0.99, 4), 1.0)  # better score but a near-copy of the first
    picked = [c.asset_id for c, _ in choose([hands_on_head, burst_copy, arms_crossed], 2)]
    assert picked == [9930, 9939]  # the best of the burst, then the other pose — not two copies


def test_aesthetic_hint_is_a_small_labelled_part() -> None:
    base = {"eye_sharp": 0.8, "face_quality": 0.8, "face_clip": 0.0, "face_luma": 55, "area": 0.4,
            "offcentre": 0.1, "blink": 0.05}
    high, low = score(base | {"aesthetic_mos": 5.4}), score(base | {"aesthetic_mos": 4.0})
    assert high.parts["aesthetic"] == 100 and low.parts["aesthetic"] == 0
    assert any("gợi ý thẩm mỹ cao" in s for s in high.strengths)
    assert any("gợi ý thẩm mỹ thấp" in w for w in low.weaknesses)
    assert high.total - low.total < 10  # a hint, it cannot decide alone
    assert not any("thẩm mỹ" in t for t in high.not_rated)


def test_close_up_is_judged_at_portrait_scale_and_framed_from_the_face() -> None:
    """Owner's report (SNO_1056): a very sharp frame-filling close-up was called "thiếu nét", and its
    framing was "chưa đánh giá" (no body box)."""
    import cv2

    from app.quality.measure import EYE_DIST_REF, at_portrait_scale, edge_sharpness, framing

    rng = np.random.default_rng(1)
    sharp = (rng.random((120, 160)) > 0.5).astype(np.uint8) * 200 + 20  # crisp edges at 100%
    sharp = cv2.resize(sharp, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    lens_close_up = cv2.GaussianBlur(  # same detail over 4x the pixels, edges ~3 px wide (lens limit)
        cv2.resize(sharp, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC), (0, 0), 1.5)
    blurred_close_up = cv2.GaussianBlur(lens_close_up, (0, 0), 10)
    eyes_apart = EYE_DIST_REF * 4
    assert edge_sharpness(lens_close_up) < 0.5  # what the old 100% measurement said
    focused = edge_sharpness(at_portrait_scale(lens_close_up, eyes_apart))
    assert focused > 0.6
    assert edge_sharpness(at_portrait_scale(blurred_close_up, eyes_apart)) < 0.7 * focused  # real blur still shows
    assert at_portrait_scale(sharp, EYE_DIST_REF * 0.8) is sharp  # normal portraits: 100% as before

    close_up = framing(None, (0.2, 0.0, 0.6, 0.7))  # face fills the frame, forehead cropped on purpose
    assert close_up["area"] == 1.0 and close_up["cut_head"] == 0.0
    wide = framing((0.3, 0.0, 0.3, 0.9), (0.4, 0.0, 0.1, 0.1))  # head cut in a wider shot: still a flaw
    assert wide["cut_head"] == 1.0


def test_aesthetic_part_averages_topiq_and_laion() -> None:
    from app.quality.score import AESTHETIC_HIGH, AESTHETIC_LOW, LAION_HIGH, LAION_LOW

    base = {"eye_sharp": 0.5, "face_quality": 0.6, "face_clip": 0.0, "face_luma": 50, "area": 0.3}
    topiq = (AESTHETIC_LOW + AESTHETIC_HIGH) / 2  # -> 50
    s = score(base | {"aesthetic_mos": topiq, "laion_mos": LAION_HIGH})  # -> 100
    assert s.parts["aesthetic"] == 75.0
    assert "TOPIQ" in s.aesthetic_detail and "LAION" in s.aesthetic_detail
    only_laion = score(base | {"laion_mos": LAION_LOW})
    assert only_laion.parts["aesthetic"] == 0.0 and "TOPIQ" not in only_laion.aesthetic_detail


def test_technical_and_face_iqa_blend_in() -> None:
    base = {"eye_sharp": 0.75, "face_quality": 0.75, "face_clip": 0.0, "face_luma": 50, "area": 0.3}
    plain = score(base)
    worse = score(base | {"tech_iqa": 0.3, "face_iqa": 0.3})
    assert plain.parts["focus"] == 100.0 and worse.parts["focus"] == 80.0
    assert plain.parts["face"] == 100.0 and worse.parts["face"] == 50.0
    only_face_iqa = score({"face_iqa": 0.8})
    assert only_face_iqa.parts["face"] == 100.0


def test_every_criterion_has_a_reason() -> None:
    from app.quality.score import WEIGHTS

    s = score({"eye_sharp": 0.5, "area": 0.3})
    assert set(s.reasons) == set(WEIGHTS)
    assert all(isinstance(t, str) and t for t in s.reasons.values())
    assert "chưa chấm" in s.reasons["eyes"]


def test_style_tags_are_kept_on_the_score() -> None:
    s = score({"eye_sharp": 0.5, "style_tags": [["low_key", 0.05], ["bokeh", 0.03]]})
    assert s.tags == ["low_key", "bokeh"]
