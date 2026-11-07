"""M1: an event has its own folder and database, apart from Chụp cá nhân; deleting it never touches a photo."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media import event as ev
from app.media.schema import is_media_db
from app.storage import decisions
from app.storage.sessions import open_session
from app.workers.import_job import ImportJob
from tests.media.fixtures import hashes, photo


@pytest.fixture
def shoot(tmp_path: Path) -> Path:
    root = tmp_path / "Hội nghị"
    for i in range(4):
        photo(root / f"DSC_{i:04d}.jpg", i, taken=f"2026:06:19 09:00:{i:02d}", make="NIKON", model="Z 6")
    return root


def test_create_list_open_rename_delete(tmp_path: Path, shoot: Path) -> None:
    root = tmp_path / "media"
    before = hashes(shoot)
    e = ev.create_event("VNNIC 2026", root)
    ImportJob(e, shoot).run()
    event_id = e.event_id
    e.close()
    assert [(i.id, i.name) for i in ev.list_events(root)] == [(event_id, "VNNIC 2026")]
    with ev.open_event(event_id, root) as e2:
        assert e2.event_name == "VNNIC 2026"
        assert e2.conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'ok'").fetchone()[0] == 4
        e2.rename("VNNIC Internet Conference 2026")
    ev.delete_event(event_id, root)
    assert ev.list_events(root) == [] and not (root / event_id).exists()
    assert hashes(shoot) == before  # import, open and delete never change a photo


def test_two_modes_on_the_same_folder_keep_their_own_marks(tmp_path: Path, shoot: Path) -> None:
    """The same photo folder in a Chụp cá nhân session and in an event: two databases, P/X kept apart."""
    personal, _ = open_session(tmp_path / "sessions", shoot)
    ImportJob(personal, shoot).run()
    event = ev.create_event("Sự kiện", tmp_path / "media")
    ImportJob(event, shoot).run()
    p_ids = {r[0]: r[1] for r in personal.conn.execute("SELECT relative_path, id FROM assets")}
    e_ids = {r[0]: r[1] for r in event.conn.execute("SELECT relative_path, id FROM assets")}
    decisions.set_flag(personal.conn, p_ids["DSC_0000.jpg"], "keep")
    decisions.set_flag(event.conn, e_ids["DSC_0000.jpg"], "reject")
    decisions.set_flag(event.conn, e_ids["DSC_0001.jpg"], "keep")
    assert decisions.get(personal.conn, p_ids["DSC_0000.jpg"]).flag == "keep"
    assert decisions.get(personal.conn, p_ids["DSC_0001.jpg"]).flag is None
    assert decisions.get(event.conn, e_ids["DSC_0000.jpg"]).flag == "reject"
    assert not is_media_db(personal.conn)  # the personal session never gets the Media tables
    assert personal.conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'media_%' OR name = 'media_meta'").fetchone()[0] == 0
    assert personal.folder != event.folder
    personal.close()
    event.close()


def test_delete_refuses_anything_that_is_not_an_event(tmp_path: Path, shoot: Path) -> None:
    root = tmp_path / "media"
    # a personal session database placed under the media root by mistake
    session, _ = open_session(root, shoot)
    bogus = session.folder.name
    session.close()
    with pytest.raises(ev.EventError, match="không phải sự kiện"):
        ev.delete_event(bogus, root)
    assert (root / bogus).exists()
    for bad in ("..", "../x", "a/b", "", "C:\\x"):
        with pytest.raises(ev.EventError):
            ev.delete_event(bad, root)
    with pytest.raises(ev.EventError, match="không phải sự kiện"):
        ev.open_event(bogus, root)
