"""M9: 'Dán nhãn mẫu' + the offline scorer on a SYNTHETIC labelled set (known answers -> known numbers).

These tests prove the arithmetic and the rules (sets split by moment, < 15 samples = "chưa đủ mẫu", numbers only,
read-only, network blocked). The real rates come only from the owner's labelled event photos.
"""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from app.media import analysis
from app.media import cameras as cam
from app.media import event as ev
from app.media import moments as mo
from app.media import samples as sm
from tests.media.fixtures import photo

DAY = datetime(2026, 6, 19, 9, 0, 0)
N = 60  # photos, 6 moments of 10 (10-minute pauses)


def _event(tmp_path: Path):  # noqa: ANN202
    shoot = tmp_path / "S"
    for i in range(N):
        t = DAY + timedelta(seconds=(i // 10) * 600 + (i % 10) * 20)
        photo(shoot / f"DSC_{i:04d}.jpg", i, taken=t.strftime("%Y:%m:%d %H:%M:%S"), make="NIKON", model="Z 6",
              size=(120, 80))
    e = ev.create_event("score", tmp_path / "media")
    cam.import_folder(e, shoot)
    ids = [r[0] for r in e.conn.execute("SELECT id FROM assets ORDER BY relative_path")]
    return e, ids


TRUE_SHOT = ["can", "trung", "toan"]


def _analyse(e, ids) -> None:  # noqa: ANN001
    """AI answers: photo i's true size is TRUE_SHOT[i % 3]; the AI gets every 5th one wrong and says '?' on i % 7 == 0."""
    calls = []

    def detect(bgr):  # noqa: ANN001, ANN202
        i = len(calls)
        calls.append(i)
        h, w = bgr.shape[:2]
        if i % 7 == 0:
            return [((w * 0.2, 0, w * 0.6, h * 0.99), 0.9)], []  # big body, no face: '?'
        true = TRUE_SHOT[i % 3]
        guess = TRUE_SHOT[(i + 1) % 3] if i % 5 == 0 else true
        f = {"can": 0.3, "trung": 0.08, "toan": 0.02}[guess]
        return [((w * 0.3, h * 0.05, w * 0.4, h * 0.9), 0.9)], [((w * 0.45, h * 0.1, f * h * 0.8, f * h), 0.95)]

    def full(path):  # noqa: ANN001, ANN202 - photo i: soft on i % 4 == 0 (Out nét), sharp otherwise
        i = int(Path(path).stem.split("_")[1])
        rng = np.random.default_rng(i)
        img = (rng.random((160, 240)) * 255).astype(np.uint8)
        if i % 4 == 0:
            import cv2

            img = cv2.GaussianBlur(img, (0, 0), 5)
        return img

    analysis.analyse_event(e, detect=detect, load_full=full)


def test_scores_with_sample_sizes_and_split_by_moment(tmp_path: Path) -> None:
    e, ids = _event(tmp_path)
    _analyse(e, ids)
    for i, a in enumerate(ids):
        sm.set_sample(e.conn, [a], "shot", TRUE_SHOT[i % 3])
        sm.set_sample(e.conn, [a], "focus", "out_net" if i % 4 == 0 else "net")
        if i % 10 == 0 and i:
            sm.set_sample(e.conn, [a], "boundary", "start")
    sm.set_sample(e.conn, [ids[59]], "skip", "1")
    report = sm.score(e)

    tuning, scoring = sm.split_sets(e.conn)
    assert tuning and scoring and not tuning & scoring
    for m in mo.moments(e.conn):  # a moment is never on both sides
        assert set(m.assets) <= tuning or set(m.assets) <= scoring
    assert report["samples"]["photos_labelled"] == N and report["samples"]["skipped"] == 1

    # expected numbers, recomputed from the known answers on the scoring set
    pos = {a: i for i, a in enumerate(ids)}
    scored = [pos[a] for a in scoring if a != ids[59]]
    decided = [i for i in scored if i % 7]
    unknown = len(scored) - len(decided)
    correct = sum(1 for i in decided if i % 5)
    shot = report["shot"]
    assert (shot["accuracy"]["n"], shot["accuracy"]["of"]) == (correct, len(decided))
    assert (shot["unknown_rate"]["n"], shot["unknown_rate"]["of"]) == (unknown, len(scored))
    assert shot["accuracy"]["text"].startswith(f"{correct}/{len(decided)}")
    assert sum(shot["confusion"].values()) == len(scored)

    out = report["out_net"]
    assert out["catch"]["of"] == sum(1 for i in scored if i % 4 == 0)
    assert out["catch"]["n"] == out["catch"]["of"]  # synthetic blur is caught
    assert out["false_alarm"]["n"] == 0
    assert report["moments"]["true_boundaries"] == 5 and report["moments"]["missing"] == 0
    assert report["moments"]["extra"] == 0 and report["moments"]["correct"] == 5
    assert report["content"]["applies"] is False and "không áp dụng" in report["content"]["text"]

    text = json.dumps(report, ensure_ascii=False)
    assert "DSC_" not in text and str(tmp_path) not in text and ".jpg" not in text  # numbers only
    e.close()


def test_fewer_than_15_samples_is_not_enough(tmp_path: Path) -> None:
    e, ids = _event(tmp_path)
    _analyse(e, ids)
    for i, a in enumerate(ids[:12]):
        sm.set_sample(e.conn, [a], "shot", TRUE_SHOT[i % 3])
    report = sm.score(e)
    assert report["shot"]["accuracy"]["rate"] is None and "chưa đủ mẫu" in report["shot"]["accuracy"]["text"]
    assert report["shot"]["accuracy_verdict"] == "chưa đủ mẫu"
    assert report["trat_net"]["catch"]["text"].endswith("chưa đủ mẫu")
    assert "chưa đủ mẫu" in report["suggested_thresholds"]["shot"]["text"]
    e.close()


def test_labels_toggle_and_one_value_per_photo(tmp_path: Path) -> None:
    e, ids = _event(tmp_path)
    sm.set_sample(e.conn, [ids[0]], "shot", "can")
    sm.set_sample(e.conn, [ids[0]], "shot", "toan")
    assert sm.samples_of(e.conn, ids[0]) == {"shot": ["toan"]}
    assert sm.toggle_sample(e.conn, [ids[0], ids[1]], "content", "booth") is True
    assert sm.toggle_sample(e.conn, [ids[0], ids[1]], "content", "booth") is False
    assert "content" not in sm.samples_of(e.conn, ids[0])
    assert e.conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0] == 0  # never touches the working labels
    with pytest.raises(ValueError):
        sm.set_sample(e.conn, [ids[0]], "shot", "rat_gan")
    e.close()


def test_cli_is_read_only_and_blocks_the_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # noqa: ANN001
    for name in ("connect", "connect_ex"):  # restored after the test (the CLI blocks them for good)
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    root = tmp_path / "media"
    monkeypatch.setattr(ev, "media_root", lambda: root)
    e, ids = _event(tmp_path)
    _analyse(e, ids)
    sm.set_sample(e.conn, [ids[1]], "shot", "trung")
    event_id = e.event_id
    db = e.folder / "project.snorlu.db"
    e.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    out = tmp_path / "kq.json"
    assert sm.run_cli([event_id, "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["kind"] == "kirapick-media-score" and report["network_attempts"] == 0
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 80), timeout=1)
    assert sm.run_cli(["không có sự kiện này"]) == 2
