from __future__ import annotations

import os
import time
from pathlib import Path

from app.storage import decisions
from app.storage.sessions import SESSION_TTL_DAYS, delete_session, open_session, purge_old_sessions, session_dir


def test_same_folder_same_session_and_restore(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    photos = tmp_path / "Ảnh Aki"
    photos.mkdir()
    p, restored = open_session(root, photos)
    assert not restored and p.name == "Ảnh Aki"
    p.conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('x', 'n')")
    p.conn.execute("""INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size,
                      mtime_ns, quick_hash, added_at, updated_at) VALUES (1,'a.nef','.nef','raw','v',1,1,'h','n','n')""")
    decisions.set_flag(p.conn, 1, "keep")
    p.close()
    p2, restored = open_session(root, photos / ".." / "Ảnh Aki")  # same folder written differently
    assert restored and decisions.get(p2.conn, 1).flag == "keep"
    p2.close()
    other, restored = open_session(root, tmp_path)
    assert not restored and other.folder != p2.folder
    other.close()


def test_purge_only_old_sessions_and_never_foreign_folders(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    old_photos, new_photos = tmp_path / "old", tmp_path / "new"
    old_photos.mkdir()
    new_photos.mkdir()
    for folder in (old_photos, new_photos):
        open_session(root, folder)[0].close()
    stranger = root / "not-ours"
    stranger.mkdir()
    (stranger / "keep.txt").write_text("x")
    long_ago = time.time() - (SESSION_TTL_DAYS + 1) * 86400
    old_dir = session_dir(root, old_photos)
    os.utime(old_dir / "snorlu-session", (long_ago, long_ago))
    os.utime(stranger, (long_ago, long_ago))

    assert purge_old_sessions(root) == [old_dir]
    assert not old_dir.exists() and session_dir(root, new_photos).exists()
    assert (stranger / "keep.txt").exists(), "only directories created by the app may be removed"
    assert old_photos.exists()


def test_delete_session(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    photos = tmp_path / "p"
    photos.mkdir()
    (photos / "DSC_0001.NEF").write_bytes(b"raw")
    open_session(root, photos)[0].close()
    assert delete_session(root, photos)
    assert not session_dir(root, photos).exists() and (photos / "DSC_0001.NEF").read_bytes() == b"raw"
    assert not delete_session(root, photos)  # nothing left to delete
