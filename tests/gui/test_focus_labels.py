"""Q / W / R: the user's sharpness label is saved with the photo and teaches the per-camera focus model."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt

from app.learning import focus
from app.storage import decisions
from tests.gui.test_main_window import _import, _key, _window, env  # noqa: F401 - fixture


def _measure(conn, asset_id: int, eye: float) -> None:  # noqa: ANN001
    occ = conn.execute("INSERT INTO occurrences (asset_id, prominence, is_main, analysis_version, created_at)"
                       " VALUES (?, 1, 1, 1, 't')", (asset_id,)).lastrowid
    conn.execute("INSERT INTO measurements (asset_id, occurrence_id, extractor, extractor_version, input_source,"
                 " values_json, computed_at) VALUES (?, ?, 'quality', '5', 'full', ?, 't')",
                 (asset_id, occ, json.dumps({"eye_sharp": eye, "tech_iqa": 0.6})))


def test_q_w_r_label_the_photo_and_feed_the_focus_model(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    conn = w.project.conn
    w.act_auto_advance.setChecked(False)
    w.select_row(0)
    first = w.current_record()
    _measure(conn, first.id, 0.4)
    conn.commit()

    _key(qtbot, w, Qt.Key.Key_Q)
    assert decisions.get(conn, first.id).focus == "sharp" and w.current_record().focus == "sharp"
    assert "nét căng (Q)" in w.inspector.fields["Bạn chấm nét"].text()
    assert [(e.label, e.features["eye_sharp"]) for e in w.teacher.store.focus_examples()] == [(0, 0.4)]

    _key(qtbot, w, Qt.Key.Key_R)  # changes the label: the example is replaced
    assert [e.label for e in w.teacher.store.focus_examples()] == [2]
    _key(qtbot, w, Qt.Key.Key_R)  # same key again clears it
    assert decisions.get(conn, first.id).focus is None and w.teacher.store.focus_examples() == []

    w.select_row(1)  # not analysed: the label is kept, nothing to learn from
    _key(qtbot, w, Qt.Key.Key_W)
    assert decisions.get(conn, w.current_record().id).focus == "soft"
    assert w.teacher.store.focus_examples() == [] and "chưa được 📊 Phân tích" in w.status.text()

    w.retrain_focus(wait=True)
    assert "Chưa có ảnh nào được chấm nét" in " ".join(w.focus_text())
    focus.use_models({})
