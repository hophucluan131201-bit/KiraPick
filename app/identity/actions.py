"""User corrections. All of them are 'manual' and survive re-analysis and re-grouping."""

from __future__ import annotations

import sqlite3

from app.storage.project import utc_now

# Photos with people in them but no subject at all ("Chưa xác định"). A photo whose main
# subject is known but has a second, unknown person is NOT in this list.
UNIDENTIFIED_ASSETS = """SELECT asset_id FROM occurrences WHERE is_main = 1
                         GROUP BY asset_id HAVING COUNT(subject_id) = 0"""


def subject_label(conn: sqlite3.Connection, subject_id: int) -> str:
    row = conn.execute("SELECT display_name FROM subjects WHERE id = ?", (subject_id,)).fetchone()
    if row is None:
        return "?"
    return row["display_name"] or f"Chủ thể {subject_id}"


def create_subject(conn: sqlite3.Connection, asset_ids: list[int], name: str | None = None,
                   from_subject: int | None = None) -> int:
    """'This is someone else, not any subject so far': a new subject holding these photos (manually).

    ``from_subject``: the subject the photos are taken out of (the one being viewed), if any.
    """
    if from_subject is not None:
        remove_photos_from_subject(conn, from_subject, asset_ids)
    subject_id = int(conn.execute("INSERT INTO subjects (created_at) VALUES (?)", (utc_now(),)).lastrowid)
    if name and name.strip():
        rename_subject(conn, subject_id, name.strip())
    assign_photos_to_subject(conn, subject_id, asset_ids)
    return subject_id


def rename_subject(conn: sqlite3.Connection, subject_id: int, name: str) -> None:
    name = name.strip()
    conn.execute("UPDATE subjects SET display_name = ?, user_locked = ? WHERE id = ?",
                 (name or None, int(bool(name)), subject_id))


def merge_subjects(conn: sqlite3.Connection, keep: int, drop: int) -> None:
    """'These are the same person': everything of ``drop`` moves to ``keep`` (manually)."""
    if keep == drop:
        return
    conn.execute("UPDATE occurrences SET subject_id = ?, assignment = 'manual', confidence = NULL WHERE subject_id = ?",
                 (keep, drop))
    conn.execute("UPDATE occurrences SET excluded_subject_id = ? WHERE excluded_subject_id = ?", (keep, drop))
    keep_one_per_photo(conn, keep)
    row = conn.execute("SELECT display_name FROM subjects WHERE id = ?", (keep,)).fetchone()
    other = conn.execute("SELECT display_name FROM subjects WHERE id = ?", (drop,)).fetchone()
    if row is not None and row["display_name"] is None and other is not None and other["display_name"]:
        rename_subject(conn, keep, other["display_name"])  # keep a name the user gave
    conn.execute("DELETE FROM subjects WHERE id = ?", (drop,))


def keep_one_per_photo(conn: sqlite3.Connection, subject_id: int | None = None) -> int:
    """A person appears once per photo: where a subject has several people in one photo (after a
    merge, or an older version's mistake), the most prominent stays and the others (usually someone
    in the background) are released. ``None`` = every subject. Returns occurrences released."""
    where = "subject_id IS NOT NULL" if subject_id is None else "subject_id = :sid"
    cur = conn.execute(
        f"""UPDATE occurrences AS o SET excluded_subject_id = o.subject_id, subject_id = NULL,
                assignment = 'none', confidence = NULL
            WHERE o.{where} AND o.id != (
                SELECT o2.id FROM occurrences o2 WHERE o2.asset_id = o.asset_id AND o2.subject_id = o.subject_id
                ORDER BY o2.is_main DESC, o2.prominence DESC, o2.id LIMIT 1)""", {"sid": subject_id})
    return cur.rowcount


def mark_different(conn: sqlite3.Connection, a: int, b: int) -> None:
    """'These are different people': they will never be merged or suggested again."""
    if a == b:
        return
    conn.execute("INSERT OR IGNORE INTO subject_pairs (a, b, relation, created_at) VALUES (?, ?, 'different', ?)",
                 (min(a, b), max(a, b), utc_now()))


def remove_photos_from_subject(conn: sqlite3.Connection, subject_id: int, asset_ids: list[int]) -> int:
    """'This person is not in these photos' (or it is someone else). Returns occurrences changed."""
    marks = ",".join("?" * len(asset_ids))
    cur = conn.execute(
        f"""UPDATE occurrences SET subject_id = NULL, assignment = 'manual', confidence = NULL,
            excluded_subject_id = ? WHERE subject_id = ? AND asset_id IN ({marks})""",
        (subject_id, subject_id, *asset_ids),
    )
    return cur.rowcount


def confirm_suggested(conn: sqlite3.Connection, subject_id: int, asset_ids: list[int]) -> int:
    """'Yes, this is them': a suggested (face-less) match becomes manual."""
    marks = ",".join("?" * len(asset_ids))
    cur = conn.execute(
        f"""UPDATE occurrences SET assignment = 'manual' WHERE subject_id = ? AND assignment = 'suggested'
            AND asset_id IN ({marks})""",
        (subject_id, *asset_ids),
    )
    return cur.rowcount


def assign_photos_to_subject(conn: sqlite3.Connection, subject_id: int, asset_ids: list[int]) -> int:
    """Put photos into a person: uses each photo's most prominent unassigned main occurrence."""
    changed = 0
    for asset_id in asset_ids:
        if conn.execute("SELECT 1 FROM occurrences WHERE asset_id = ? AND subject_id = ?", (asset_id, subject_id)).fetchone():
            conn.execute("UPDATE occurrences SET assignment = 'manual' WHERE asset_id = ? AND subject_id = ?",
                         (asset_id, subject_id))
            changed += 1
            continue
        row = conn.execute(
            """SELECT id FROM occurrences WHERE asset_id = ? AND (subject_id IS NULL OR assignment != 'manual')
               ORDER BY is_main DESC, prominence DESC LIMIT 1""", (asset_id,)
        ).fetchone()
        if row is not None:
            conn.execute("""UPDATE occurrences SET subject_id = ?, assignment = 'manual', excluded_subject_id = NULL
                            WHERE id = ?""", (subject_id, row["id"]))
            changed += 1
    return changed


def subjects_summary(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Subjects with photo counts, uncertain counts and an avatar crop, biggest first."""
    return conn.execute(
        """SELECT s.id, s.display_name, COUNT(DISTINCT o.asset_id) AS photos,
                  SUM(o.assignment = 'suggested') AS suggested,
                  (SELECT o2.crop_file FROM occurrences o2 JOIN occurrence_vectors v
                     ON v.occurrence_id = o2.id AND v.kind = 'face'
                   WHERE o2.subject_id = s.id ORDER BY o2.face_score DESC LIMIT 1) AS avatar
           FROM subjects s JOIN occurrences o ON o.subject_id = s.id
           GROUP BY s.id ORDER BY photos DESC, s.id"""
    ).fetchall()
