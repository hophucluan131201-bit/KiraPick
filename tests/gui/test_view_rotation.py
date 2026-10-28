"""Xoay xem: turns the photo on screen only — never the file, the AI or the exported copy."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from app.storage import view
from app.storage.view import rotate_point
from tests.gui.test_main_window import _import, _key, _photo, _window, env  # noqa: F401 - fixture


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rotate_point_turns_normalised_coordinates_clockwise() -> None:
    assert rotate_point(0.1, 0.2, 0) == (0.1, 0.2)
    assert rotate_point(0.1, 0.2, 1) == pytest.approx((0.8, 0.1))  # top-left -> top-right
    assert rotate_point(0.1, 0.2, 2) == pytest.approx((0.9, 0.8))
    assert rotate_point(0.1, 0.2, 3) == pytest.approx((0.2, 0.9))
    assert rotate_point(0.1, 0.2, 5) == rotate_point(0.1, 0.2, 1)


def test_rotation_changes_display_not_file(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    rec = w.current_record()
    before = _sha(rec.path)
    w.model.wait_for_thumbnails()
    qtbot.wait(50)
    pm = w.model.pixmap(rec)
    assert pm.width() > pm.height()  # synthetic photos are landscape
    w.rotate_view()
    assert view.rotation(w.project.conn, rec.id) == 1 and w.current_record().rotation == 1
    turned = w.model.pixmap(w.current_record())
    assert (turned.width(), turned.height()) == (pm.height(), pm.width())
    w.show_loupe(True)
    w.viewer.wait_idle()
    qtbot.wait(50)
    vw, vh = w.viewer.pixmap_size()
    assert vh > vw  # the loupe shows it turned too
    assert _sha(rec.path) == before  # the file is untouched
    other = tmp_path / "Buổi khác"
    _photo(other / "IMG_0001.jpg", 77)
    _import(qtbot, w, other)
    _import(qtbot, w, env["photos"])  # reopen the session
    again = next(r for r in w.model.records() if r.id == rec.id)
    assert again.rotation == 1


def test_eye_zoom_follows_rotation(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    rec = w.current_record()
    with w.project.transaction() as conn:
        conn.execute("""INSERT INTO occurrences (asset_id, person_box, face_box, prominence, is_main, analysis_version,
                        created_at) VALUES (?, '[0.05,0.05,0.3,0.8]', '[0.1,0.1,0.1,0.15]', 1, 1, 1, 'n')""", (rec.id,))
    w.rotate_view()  # face at the top-left of the file -> top-right on screen
    _key(qtbot, w, Qt.Key.Key_E)
    w.viewer.wait_idle()
    qtbot.wait(50)
    centre = w.viewer.mapToScene(w.viewer.viewport().rect().center())
    width, height = w.viewer.pixmap_size()
    assert centre.x() / width > 0.6 and centre.y() / height < 0.4


def test_export_ignores_rotation(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    rec = w.current_record()
    w.rotate_view()
    _key(qtbot, w, Qt.Key.Key_K)
    dialog = w.open_export_dialog()
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(tmp_path / "out"))
    dialog.refresh()
    dialog.hide()
    thread = dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    thread.wait()
    assert (tmp_path / "out" / rec.name).read_bytes() == rec.path.read_bytes()


def test_rotation_applies_to_marked_photos(qtbot, env: dict) -> None:  # noqa: F811
    from PySide6.QtCore import QItemSelectionModel

    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    sel = w.grid.selectionModel()
    sel.select(w.model.index(1), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sel.select(w.model.index(2), QItemSelectionModel.SelectionFlag.Select)
    w.rotate_view()
    assert sorted(view.rotations(w.project.conn).values()) == [1, 1]


def test_eye_zoom_from_the_grid_keeps_the_eyes_when_the_real_image_arrives(qtbot, env: dict) -> None:  # noqa: F811
    """Pre-existing bug found here: E pressed in the grid zoomed on the thumbnail, then lost the point."""
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    w.select_row(0)
    rec = w.current_record()
    with w.project.transaction() as conn:
        conn.execute("""INSERT INTO occurrences (asset_id, person_box, face_box, prominence, is_main, analysis_version,
                        created_at) VALUES (?, '[0.05,0.05,0.3,0.8]', '[0.1,0.1,0.1,0.15]', 1, 1, 1, 'n')""", (rec.id,))
    _key(qtbot, w, Qt.Key.Key_E)
    w.viewer.wait_idle()
    qtbot.wait(50)
    centre = w.viewer.mapToScene(w.viewer.viewport().rect().center())
    width, height = w.viewer.pixmap_size()
    assert centre.x() / width < 0.3 and centre.y() / height < 0.3
