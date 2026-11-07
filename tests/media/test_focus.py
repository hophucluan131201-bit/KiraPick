"""M7: Out nét / Trật nét on SYNTHETIC full-resolution photos (FC-01…07, spec v6 §6).

What these show: the rule behaves as specified on constructed scenes (Gaussian blur, motion blur, a sharp backdrop, a
saturated and an unsaturated LED screen, a bright white costume with detail, sensor noise at high ISO).
What they do not show: accuracy on real event photos, where lenses, compression and real screens differ. That is
[Ảnh mẫu] and is scored by the sample-labelling scorer (M9) on the owner's photos.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.media import analysis
from app.media import cameras as cam
from app.media import event as ev
from app.media import labels as lb
from app.media.focus import FocusRules, directional_sharpness, judge, screens
from app.media.shot import Subject
from tests.media.fixtures import photo

FW, FH = 1600, 1200  # full-resolution size
SCALE = 2.0  # detection image is 800 x 600
FACE_FULL = (700, 300, 200, 240)  # x, y, w, h on the full photo
FACE = tuple(v / SCALE for v in FACE_FULL)
PERSON = (FACE[0] - 60, FACE[1] - 20, 220, 420)


def texture(h: int, w: int, seed: int, lo: int = 30, hi: int = 220, n: int | None = None) -> np.ndarray:
    """Hard-edged rectangles: detail in both directions, like fabric, print or a face at 100 %."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w), (lo + hi) // 2, np.uint8)
    for _ in range(n or (h * w) // 900):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        cv2.rectangle(img, (x, y), (x + int(rng.integers(3, 25)), y + int(rng.integers(3, 25))),
                      int(rng.integers(lo, hi)), -1)
    return img


def scene(*, face: str = "sharp", background: str = "blur", screen: str | None = None, seed: int = 1) -> np.ndarray:
    bg = texture(FH, FW, seed)
    if background == "blur":
        bg = cv2.GaussianBlur(bg, (0, 0), 4)
    elif background == "pan":
        bg = cv2.filter2D(bg, -1, np.full((1, 31), 1 / 31, np.float32))
    img = bg.copy()
    if screen is not None:  # an LED wall right behind the speaker, with sharp content
        x0, y0, x1, y1 = 300, 80, 1300, 560
        if screen == "saturated":
            content = texture(y1 - y0, x1 - x0, seed + 7, lo=235, hi=255)
        else:  # FC-06: bright but not clipped, text with detail
            content = texture(y1 - y0, x1 - x0, seed + 7, lo=150, hi=235)
        img[y0:y1, x0:x1] = content
    fx, fy, fw, fh = FACE_FULL
    patch = texture(fh, fw, seed + 3, lo=90, hi=200) if face != "white" else texture(fh, fw, seed + 3, lo=200, hi=246)
    if face == "blur":
        patch = cv2.GaussianBlur(patch, (0, 0), 3.5)
    img[fy:fy + fh, fx:fx + fw] = patch
    return img


SUBJECT = Subject(PERSON, FACE, 0.9)


def test_measure_reads_motion_blur_as_soft() -> None:
    sharp = texture(400, 400, 5)
    moved = cv2.filter2D(sharp, -1, np.full((1, 21), 1 / 21, np.float32))
    rules = FocusRules()
    assert directional_sharpness(sharp) > rules.sharp
    assert directional_sharpness(moved) < rules.soft
    assert directional_sharpness(np.full((100, 100), 128, np.uint8)) is None  # flat: cannot be measured


def test_fc01_panning_sharp_subject_streaked_background_no_warning() -> None:
    r = judge(scene(face="sharp", background="pan"), SUBJECT, SCALE)
    assert r.warnings == {} and not r.unmeasurable


def test_fc02a_soft_face_sharp_backdrop_is_trat_net() -> None:
    r = judge(scene(face="blur", background="sharp"), SUBJECT, SCALE)
    assert set(r.warnings) == {"trat_net"}, r.measures


def test_fc02b_soft_face_only_a_saturated_led_wall_sharp_is_out_net() -> None:
    img = scene(face="blur", background="blur", screen="saturated")
    r = judge(img, SUBJECT, SCALE)
    assert set(r.warnings) == {"out_net"}, r.measures
    assert r.measures["neighbours_excluded"] >= 1


def test_fc06_soft_face_unsaturated_sharp_led_wall_is_out_net() -> None:
    img = scene(face="blur", background="blur", screen="detail")
    assert float(np.mean(img[80:560, 300:1300] >= 250)) < 0.05  # really not saturated
    assert screens(img), "the screen must be found by its shape and even brightness"
    r = judge(img, SUBJECT, SCALE)
    assert set(r.warnings) == {"out_net"}, r.measures


def test_fc07_bright_white_costume_with_detail_no_warning() -> None:
    r = judge(scene(face="white", background="blur"), SUBJECT, SCALE)
    assert r.warnings == {} and r.measures["subject"] >= 0.25, r.measures


@pytest.mark.parametrize("blurred, expected", [(False, {}), (True, {"out_net"})])
def test_fc03_wide_shot_face_too_small_judged_on_the_whole_photo(blurred: bool, expected) -> None:  # noqa: ANN001
    img = texture(FH, FW, 9)
    if blurred:
        img = cv2.GaussianBlur(img, (0, 0), 4)
    tiny = Subject((400, 300, 20, 50), (405, 302, 10, 12), 0.8)
    r = judge(img, tiny, SCALE)
    assert set(r.warnings) == set(expected) and r.measures["region"] == "face_too_small"
    assert "trat_net" not in r.warnings


def test_fc04_camera_shake_is_out_net() -> None:
    img = cv2.filter2D(scene(face="sharp", background="sharp"), -1, np.full((1, 25), 1 / 25, np.float32))
    r = judge(img, SUBJECT, SCALE)
    assert set(r.warnings) == {"out_net"}, r.measures  # UX-4: shake / motion blur = Out nét


def test_fc05_high_iso_but_sharp_no_warning() -> None:
    rng = np.random.default_rng(3)
    img = scene(face="sharp", background="blur").astype(np.float32) + rng.normal(0, 10, (FH, FW))
    r = judge(np.clip(img, 0, 255).astype(np.uint8), SUBJECT, SCALE, iso=6400)
    assert r.warnings == {}, r.measures


def test_high_iso_noise_does_not_hide_a_soft_face() -> None:
    rng = np.random.default_rng(4)
    img = scene(face="blur", background="blur").astype(np.float32) + rng.normal(0, 10, (FH, FW))
    r = judge(np.clip(img, 0, 255).astype(np.uint8), SUBJECT, SCALE, iso=6400)
    assert "out_net" in r.warnings, r.measures


def test_flat_photo_is_unmeasurable_and_no_subject_uses_the_whole_photo() -> None:
    flat = np.full((FH, FW), 120, np.uint8)
    assert judge(flat, None).unmeasurable
    assert judge(texture(FH, FW, 2), None).warnings == {}


# ------------------------------------------------------------------------------------------- in the job
def test_analysis_writes_focus_warnings_and_keeps_a_removed_one(tmp_path: Path) -> None:
    shoot = tmp_path / "S"
    for i in range(2):
        photo(shoot / f"P{i}.jpg", i, taken=f"2026:06:19 09:0{i}:00", make="NIKON", model="Z 6", size=(800, 600))
    e = ev.create_event("M7", tmp_path / "media")
    cam.import_folder(e, shoot)
    ids = sorted(r[0] for r in e.conn.execute("SELECT id FROM assets"))
    fulls = {ids[0]: scene(face="blur", background="sharp"), ids[1]: scene(face="sharp", background="blur")}
    by_path = {e.asset_path(a): img for a, img in fulls.items()}

    def detect(bgr):  # noqa: ANN001, ANN202
        return [(PERSON, 0.9)], [(FACE, 0.95)]

    s = analysis.analyse_event(e, detect=detect, load_full=lambda p: by_path[p])
    assert s.analysed == 2
    assert [v for v, st, _ in lb.labels_of(e.conn, ids[0])["focus"]] == ["trat_net"]
    assert "focus" not in lb.labels_of(e.conn, ids[1])  # analysed, no warning (not ⏳: media_analysis has it)
    assert analysis.progress_of(e.conn)["done"] == 2
    from app.media.browse import MediaFilter, matching_ids

    assert matching_ids(e.conn, MediaFilter(focus="none")) == [ids[1]]
    assert matching_ids(e.conn, MediaFilter(focus="trat_net")) == [ids[0]]
    lb.remove(e, [ids[0]], "focus", "trat_net")  # the user says the focus is fine
    e.conn.execute("DELETE FROM media_analysis")  # re-analysis
    analysis.analyse_event(e, detect=detect, load_full=lambda p: by_path[p])
    assert lb.labels_of(e.conn, ids[0]).get("focus", []) == []
    e.close()


@pytest.mark.parametrize("screen", ["saturated", "detail"])
def test_control_without_the_screen_exclusion_the_led_wall_would_read_as_trat_net(screen: str) -> None:
    """FC-02b / FC-06 pass because the wall is left out of the comparison, not because the neighbours are soft."""
    off = FocusRules(light_clip=1.1, screen_lift=999.0)
    r = judge(scene(face="blur", background="blur", screen=screen), SUBJECT, SCALE, rules=off)
    assert set(r.warnings) == {"trat_net"}, r.measures
