"""C8 (LIC-1 S3): without a verified face recogniser the analysis still finds people, grouping is by hand, and a
photo without a found person cannot be grouped (the menu says why instead of making an empty person).

U9: detection without recognition, manual grouping on found people. U12: photos without occurrences (case A:
never analysed; C: added after the analysis; D: no person found) keep import / browse / P/X / export, and the
grouping actions are locked with the reason. U16: the local log line of a grouping action names no person or path.
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QAction

from app.ui import main_window as mw
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture


def _actions(menu_texts: dict):  # noqa: ANN202
    def run(menu, _pos):  # noqa: ANN001, ANN202
        for a in menu.findChildren(QAction):
            menu_texts[a.text()] = (a.isEnabled(), a.toolTip())
        return None  # close without choosing
    return run


def _pick(text: str):  # noqa: ANN202
    def run(menu, _pos):  # noqa: ANN001, ANN202
        return next(a for a in menu.findChildren(QAction) if a.text().startswith(text))
    return run


def _person(w: mw.MainWindow, asset_id: int) -> None:
    with w.project.transaction() as conn:
        conn.execute("""INSERT INTO occurrences (asset_id, person_box, prominence, is_main, analysis_version,
                        created_at, run_id) VALUES (?, '[0.1,0.1,0.5,0.8]', 1, 1, 2, 'n',
                        (SELECT id FROM analysis_runs WHERE stage = 'test'))""", (asset_id,))


def test_photos_without_a_found_person_cannot_be_grouped_and_say_why(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """U12 (cases A, C, D: no occurrence for the photo)."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    ids = [r.id for r in w.model.records() if r.status == "ok"]
    seen: dict = {}
    monkeypatch.setattr(w, "_run_menu", _actions(seen))
    w._people_menu_at(None, ids[:2])
    create = next(v for k, v in seen.items() if k.startswith("➕ Tạo chủ thể mới"))
    assert create == (False, mw.NO_PEOPLE_FOUND)
    assert seen["Gán cho chủ thể…"][0] is False
    assert w.project.conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0  # no empty person made
    # the rest still works on those photos: mark, and they stay importable / exportable (export tests cover it)
    w.grid.setCurrentIndex(w.model.index(0, 0))
    w.set_flag("keep")
    assert w.project.conn.execute("SELECT flag FROM decisions WHERE asset_id = ?", (ids[0],)).fetchone()[0] == "keep"


def test_found_people_are_grouped_by_hand_and_the_status_is_honest(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """U9: a person found by detection joins a new subject; a photo without one in the same selection is skipped and
    the status says so (it used to say 'with N photos' and make the subject anyway)."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    ids = [r.id for r in w.model.records() if r.status == "ok"]
    _person(w, ids[0])
    monkeypatch.setattr(mw.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Aki", True)))
    monkeypatch.setattr(w, "_run_menu", _pick("➕ Tạo chủ thể mới"))
    w._people_menu_at(None, ids[:2])
    rows = w.project.conn.execute("SELECT asset_id, assignment FROM occurrences WHERE subject_id IS NOT NULL").fetchall()
    assert [tuple(r) for r in rows] == [(ids[0], "manual")]
    assert "với 1 ảnh" in w.status.text() and "1 ảnh chưa có người được dò" in w.status.text()


def test_grouping_action_log_line_names_no_person(qtbot, env: dict, monkeypatch, caplog) -> None:  # noqa: F811
    """U16."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    ids = [r.id for r in w.model.records() if r.status == "ok"]
    _person(w, ids[0])
    monkeypatch.setattr(mw.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Nguyễn Thị Khách", True)))
    monkeypatch.setattr(w, "_run_menu", _pick("➕ Tạo chủ thể mới"))
    caplog.set_level(logging.INFO, logger=mw.__name__)
    w._people_menu_at(None, ids[:1])
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("people action")]
    assert lines == ["people action: kind=create"]
    assert "Nguyễn" not in caplog.text and str(env["photos"]) not in caplog.text


def test_a_new_subject_is_never_made_from_photos_without_a_found_person(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    """REG-1: the direct path (not only the locked menu item) refuses, asks nothing and makes no empty subject; the
    rule also holds in app.identity.actions."""
    import pytest

    from app.identity import actions

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    ids = [r.id for r in w.model.records() if r.status == "ok"]
    asked: list = []
    monkeypatch.setattr(mw.QInputDialog, "getText", staticmethod(lambda *a, **k: asked.append(1) or ("X", True)))
    assert w.create_subject_from(ids[:2]) is None
    assert asked == [] and w.status.text() == mw.NO_PEOPLE_FOUND
    with pytest.raises(actions.NoPeopleFound), w.project.transaction() as conn:
        actions.create_subject(conn, ids[:2], "X")
    assert w.project.conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0
