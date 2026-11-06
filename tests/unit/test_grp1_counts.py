"""GRP-1 trial counter: numbers only, read-only, actions counted from the local log."""

from __future__ import annotations

from pathlib import Path

from app.storage.project import Project
from scripts import grp1_counts


def test_counts_photos_people_blocked_photos_and_actions(tmp_path: Path) -> None:
    with Project.create(tmp_path / "s", "x") as project:
        conn = project.conn
        conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/p', 'n')")
        for i in range(3):
            conn.execute("""INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size,
                            mtime_ns, quick_hash, added_at, updated_at, status)
                            VALUES (1, ?, '.jpg', 'raster', 'verified', 1, 1, ?, 'n', 'n', 'ok')""", (f"{i}.jpg", str(i)))
        conn.execute("INSERT INTO subjects (id, display_name, user_locked, created_at) VALUES (1, 'Khách A', 1, 'n')")
        conn.execute("""INSERT INTO occurrences (asset_id, prominence, is_main, subject_id, assignment, analysis_version,
                        created_at) VALUES (1, 1, 1, 1, 'manual', 2, 'n')""")
        conn.execute("""INSERT INTO occurrences (asset_id, prominence, is_main, analysis_version, created_at)
                        VALUES (2, 1, 1, 2, 'n')""")
        db = next((tmp_path / "s").glob("*.db"))
    log = tmp_path / "kirapick.log"
    log.write_text("2026-11-07 08:59:00 INFO app.ui.main_window: people action: kind=create\n"
                   "2026-11-07 09:01:00 INFO app.ui.main_window: people action: kind=create\n"
                   "2026-11-07 09:02:00 INFO app.ui.main_window: people action: kind=assign\n"
                   "2026-11-07 09:03:00 INFO app.ui.main_window: something else\n", encoding="utf-8")
    out = grp1_counts.counts(db, [log], "2026-11-07 09:00")
    assert out == {"photos": 3, "photos_with_a_person": 2, "people": 1, "photos_grouped_by_hand": 1,
                   "photos_blocked_no_person": 1, "grouping_actions": 2,
                   "grouping_actions_by_kind": {"assign": 1, "create": 1}}
    assert "Khách" not in str(out)
