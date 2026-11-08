"""REG-2 🧪 near-duplicate groups (experiment, off by default): the four cases the reviewer named, plus fixes."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

from app.media import cameras as cam
from app.media import event as ev
from app.media import labels as lb
from app.media import moments as mo
from app.media import similar as sim
from app.storage import decisions

DAY = datetime(2026, 6, 19, 9, 0, 0)


def _scene(path: Path, scene: int, jitter: int, *, taken: int, make: str = "NIKON", model: str = "Z 6") -> None:
    """A photo of 'scene' (a fixed pattern) with a little noise: same scene = near-duplicates."""
    path.parent.mkdir(parents=True, exist_ok=True)
    base = np.random.default_rng(scene).integers(0, 255, (24, 32, 3), dtype=np.uint8)
    img = np.kron(base, np.ones((10, 10, 1), dtype=np.uint8)).astype(np.int16)
    img += np.random.default_rng(1000 + jitter).integers(-6, 7, img.shape, dtype=np.int16)
    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = make, model
    exif.get_ifd(0x8769)[0x9003] = (DAY + timedelta(seconds=taken)).strftime("%Y:%m:%d %H:%M:%S")
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path, "JPEG", quality=90, exif=exif.tobytes())


def _event(tmp_path: Path, shots: list[tuple[str, int, int, str | None]], cam_b: list[tuple[str, int, int]] = ()):  # noqa: ANN202
    """shots: (name, scene, seconds, shot label or None) for camera A; cam_b: (name, scene, seconds)."""
    for i, (name, scene, t, _) in enumerate(shots):
        _scene(tmp_path / "A" / f"{name}.jpg", scene, i, taken=t)
    for i, (name, scene, t) in enumerate(cam_b):
        _scene(tmp_path / "B" / f"{name}.jpg", scene, 100 + i, taken=t, make="Canon", model="R6")
    e = ev.create_event("similar", tmp_path / "media")
    cam.import_folder(e, tmp_path / "A")
    if cam_b:
        cam.import_folder(e, tmp_path / "B")
    mo.analyse(e)
    ids = {Path(r[1]).stem: r[0] for r in e.conn.execute("SELECT id, relative_path FROM assets")}
    for name, _, _, shot in shots:
        if shot:
            lb.confirm(e, [ids[name]], "shot", shot)
    return e, ids


def _groups(e, ids) -> list[list[str]]:  # noqa: ANN001
    names = {v: k for k, v in ids.items()}
    g = sim.build(e.conn, sim.thumbnail_hashes(e.conn, e.cache_dir))
    return [[names[a] for a in grp.members] for grp in g.groups]


def test_off_by_default_and_switched_on_per_event(tmp_path: Path) -> None:
    e, _ = _event(tmp_path, [("a", 1, 0, None)])
    assert not sim.is_on(e.conn)
    with e.transaction() as conn:
        sim.set_on(conn, True)
    assert sim.is_on(e.conn)


def test_same_scene_bursts_group_and_shot_sizes_never_mix(tmp_path: Path) -> None:
    """Toàn / Trung / Cận of the same stage, taken seconds apart, stay apart; a burst of one shot size groups."""
    e, ids = _event(tmp_path, [("t1", 1, 0, "toan"), ("t2", 1, 2, "toan"), ("t3", 1, 4, "toan"),
                               ("c1", 1, 6, "can"), ("c2", 1, 8, "can"), ("u1", 1, 10, "trung")])
    assert _groups(e, ids) == [["t1", "t2", "t3"], ["c1", "c2"], ["u1"]]


def test_two_cameras_at_the_same_moment_stay_separate_groups(tmp_path: Path) -> None:
    e, ids = _event(tmp_path, [("a1", 1, 0, None), ("a2", 1, 3, None)], cam_b=[("b1", 1, 1), ("b2", 1, 4)])
    groups = _groups(e, ids)
    assert ["a1", "a2"] in groups and ["b1", "b2"] in groups
    assert mo.moment_of(e.conn, ids["a1"]) == mo.moment_of(e.conn, ids["b1"])  # still one moment


def test_two_adjacent_activities_split_where_the_scene_changes(tmp_path: Path) -> None:
    """No 5-minute gap (one moment), but the scene changes: two groups; the moment itself is left to the user (✂)."""
    e, ids = _event(tmp_path, [("x1", 1, 0, None), ("x2", 1, 3, None), ("y1", 2, 6, None), ("y2", 2, 9, None)])
    assert _groups(e, ids) == [["x1", "x2"], ["y1", "y2"]]
    assert mo.moment_of(e.conn, ids["x1"]) == mo.moment_of(e.conn, ids["y1"])


def test_a_lone_photo_with_a_focus_warning_is_still_suggested(tmp_path: Path) -> None:
    e, ids = _event(tmp_path, [("x1", 1, 0, None), ("x2", 1, 3, None), ("solo", 3, 400, None)])
    lb.confirm(e, [ids["solo"]], "focus", "out_net")
    lb.confirm(e, [ids["x1"]], "focus", "out_net")
    g = sim.build(e.conn, sim.thumbnail_hashes(e.conn, e.cache_dir))
    solo = g.group(ids["solo"])
    assert solo.members == [ids["solo"]] and solo.representative == ids["solo"] and solo.warned_single
    assert g.group(ids["x1"]).representative == ids["x2"]  # the photo without a warning is suggested
    assert g.representatives() == {ids["x2"], ids["solo"]}


def test_user_fixes_win_and_are_kept_in_the_event(tmp_path: Path) -> None:
    e, ids = _event(tmp_path, [("x1", 1, 0, None), ("x2", 1, 3, None), ("y1", 2, 6, None)])
    with e.transaction() as conn:
        sim.set_fix(conn, ids["x2"], "break")  # Tách khỏi nhóm
        sim.set_fix(conn, ids["y1"], "join")  # Gộp với nhóm trước
    assert _groups(e, ids) == [["x1"], ["x2", "y1"]]
    with e.transaction() as conn:
        sim.set_fix(conn, ids["x2"], None)
    assert _groups(e, ids) == [["x1", "x2", "y1"]]


def test_moments_without_a_pick_are_listed(tmp_path: Path) -> None:
    e, ids = _event(tmp_path, [("x1", 1, 0, None), ("later", 2, 1200, None)])
    assert len(sim.moments_without_pick(e.conn)) == 2
    decisions.set_flag(e.conn, ids["x1"], "keep")
    assert sim.moments_without_pick(e.conn) == [mo.moment_of(e.conn, ids["later"])]


def test_media_counts_cli_prints_numbers_only(tmp_path: Path, monkeypatch, capsys) -> None:  # noqa: ANN001
    import json

    import app.branding as branding
    from app.main import main

    e, ids = _event(tmp_path, [("x1", 1, 0, None), ("x2", 1, 3, None)])
    (tmp_path / "data" / "logs").mkdir(parents=True)
    (tmp_path / "data" / "logs" / "kirapick.log").write_text(
        f"2026-11-08 10:00:00,000 INFO app.media.trial: media action: event={e.event_id} kind=keep n=1\n"
        f"2026-11-08 10:12:30,000 INFO app.media.trial: media action: event={e.event_id} kind=export n=1\n"
        "2026-11-08 10:13:00,000 INFO app.media.trial: media action: event=other kind=keep n=4\n", encoding="utf-8")
    monkeypatch.setattr(ev, "media_root", lambda: tmp_path / "media")
    monkeypatch.setattr(branding, "data_dir", lambda: tmp_path / "data")
    e.close()
    assert main(["KiraPick", "--media-counts", "similar", "--out", str(tmp_path / "kq.json")]) == 0
    out = json.loads((tmp_path / "kq.json").read_text(encoding="utf-8"))
    assert out["photos"] == 2 and out["actions"] == 2 and out["minutes_first_to_last"] == 12.5
    assert "x1" not in capsys.readouterr().out
