"""🎓 So sánh ảnh: an answer stores one liked and one not-liked example (half weight)."""

from __future__ import annotations

import numpy as np

from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


def test_answering_a_pair_teaches_taste(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    conn = w.project.conn
    ids = [r[0] for r in conn.execute("SELECT id FROM assets WHERE status = 'ok' ORDER BY id")][:2]
    sid = conn.execute("INSERT INTO subjects (created_at) VALUES ('t')").lastrowid
    for a in ids:
        conn.execute("INSERT INTO occurrences (asset_id, prominence, is_main, analysis_version, created_at, subject_id)"
                     " VALUES (?, 1, 1, 1, 't', ?)", (a, sid))
    v = np.zeros(768, np.float32)
    v[0] = 1.0
    w.taste.clips = {ids[0]: v, ids[1]: v}
    for r in w.model.records():
        if r.id in ids:
            from app.quality.rank import Ranked

            r.ranked = Ranked(70.0, None, 70.0)
    dialog = w.open_compare()
    assert dialog is not None and dialog.pair == (ids[0], ids[1])
    dialog.choose(1)  # prefers the right photo
    rows = w.teacher.store.conn.execute(
        "SELECT source, label, weight FROM culling_feedback ORDER BY label").fetchall()
    assert rows == [("pair", -1, 0.5), ("pair", 1, 0.5)]
    assert dialog.pair is None and "hết cặp" in dialog.info.text()
