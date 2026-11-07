"""Camera sources of an event (Media spec §9, plan Mốc 1 M2).

Default source of a photo: the imported folder + its sub-folder + camera make / model (the app never reads serial
numbers, UX-3). Two bodies of the same model in two folders are two sources; in one folder they are one source and
the user splits them by assigning photos by hand. A hand assignment (``manual``) is never changed by a refresh.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path, PurePosixPath

from app.storage.project import Project, utc_now

UNKNOWN_CAMERA = "Máy không rõ"


def _auto_key(source_id: int, relative_path: str, make: str | None, model: str | None) -> str:
    folder = str(PurePosixPath(relative_path.replace("\\", "/")).parent)
    return f"{source_id}|{'' if folder == '.' else folder}|{(make or '').strip()}|{(model or '').strip()}"


def _display_name(conn: sqlite3.Connection, source_id: int, relative_path: str, make: str | None,
                  model: str | None) -> str:
    camera = " ".join(p for p in ((make or "").strip(), (model or "").strip()) if p) or UNKNOWN_CAMERA
    root = conn.execute("SELECT root_path FROM sources WHERE id = ?", (source_id,)).fetchone()[0]
    folder = PurePosixPath(relative_path.replace("\\", "/")).parent
    where = Path(root).name if str(folder) == "." else f"{Path(root).name}/{folder}"
    return f"{camera} — {where}"


def refresh_sources(event: Project) -> int:
    """Give every readable photo without a hand assignment its automatic source. Returns the photos (re)assigned."""
    changed = 0
    with event.transaction() as conn:
        rows = conn.execute(
            """SELECT a.id, a.source_id, a.relative_path, a.make, a.model, s.camera_id, s.manual
               FROM assets a LEFT JOIN asset_source s ON s.asset_id = a.id
               WHERE a.status IN ('ok', 'pending')""").fetchall()
        for r in rows:
            if r["manual"]:
                continue
            key = _auto_key(r["source_id"], r["relative_path"], r["make"], r["model"])
            cam = conn.execute("SELECT id FROM camera_sources WHERE auto_key = ?", (key,)).fetchone()
            if cam is None:
                cam_id = int(conn.execute(
                    """INSERT INTO camera_sources (auto_key, make, model, display_name, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (key, r["make"], r["model"],
                     _display_name(conn, r["source_id"], r["relative_path"], r["make"], r["model"]), utc_now()),
                ).lastrowid)
            else:
                cam_id = int(cam[0])
            if r["camera_id"] != cam_id:
                conn.execute("""INSERT INTO asset_source (asset_id, camera_id, manual) VALUES (?, ?, 0)
                                ON CONFLICT (asset_id) DO UPDATE SET camera_id = excluded.camera_id""",
                             (r["id"], cam_id))
                changed += 1
        _drop_empty(conn)
    return changed


def import_folder(event: Project, folder: Path, **kwargs):  # noqa: ANN003, ANN201
    """Import one more folder into the event (the existing import job), then assign sources."""
    from app.workers.import_job import ImportJob

    summary = ImportJob(event, folder).run(**kwargs)
    refresh_sources(event)
    return summary


def cameras(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT c.id, c.display_name, c.make, c.model, COUNT(s.asset_id) AS photos
           FROM camera_sources c LEFT JOIN asset_source s ON s.camera_id = c.id
           GROUP BY c.id ORDER BY c.id""")]


def camera_of(conn: sqlite3.Connection, asset_id: int) -> int | None:
    row = conn.execute("SELECT camera_id FROM asset_source WHERE asset_id = ?", (asset_id,)).fetchone()
    return None if row is None else int(row[0])


def rename_camera(conn: sqlite3.Connection, camera_id: int, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("tên nguồn máy trống")
    conn.execute("UPDATE camera_sources SET display_name = ? WHERE id = ?", (name, camera_id))


def new_camera(conn: sqlite3.Connection, name: str) -> int:
    """A source made by hand (e.g. the second body of the same model in one folder)."""
    name = name.strip()
    if not name:
        raise ValueError("tên nguồn máy trống")
    return int(conn.execute("INSERT INTO camera_sources (auto_key, display_name, created_at) VALUES (NULL, ?, ?)",
                            (name, utc_now())).lastrowid)


def assign_photos(conn: sqlite3.Connection, asset_ids: list[int], camera_id: int) -> None:
    """'Thuộc máy: …' by hand; works without EXIF. Kept through every refresh."""
    for asset_id in asset_ids:
        conn.execute("""INSERT INTO asset_source (asset_id, camera_id, manual) VALUES (?, ?, 1)
                        ON CONFLICT (asset_id) DO UPDATE SET camera_id = excluded.camera_id, manual = 1""",
                     (asset_id, camera_id))
    _drop_empty(conn)


def merge_cameras(conn: sqlite3.Connection, keep: int, drop: int) -> None:
    """Two sources are one camera: every photo of ``drop`` joins ``keep`` (as a hand assignment)."""
    if keep == drop:
        return
    conn.execute("UPDATE asset_source SET camera_id = ?, manual = 1 WHERE camera_id = ?", (keep, drop))
    _drop_empty(conn)


def _drop_empty(conn: sqlite3.Connection) -> None:
    """Sources without photos go, unless something else refers to them (clock offsets keep their history)."""
    has_offsets = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'clock_offsets'").fetchone() is not None
    keep_ref = " AND id NOT IN (SELECT camera_id FROM clock_offsets)" if has_offsets else ""
    conn.execute(f"""DELETE FROM camera_sources WHERE id NOT IN (SELECT camera_id FROM asset_source){keep_ref}""")  # noqa: S608
