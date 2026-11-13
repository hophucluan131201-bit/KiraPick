"""Small settings kept in the session database (``project.config_json``), written inside the caller's transaction."""

from __future__ import annotations

import json
import sqlite3

STALE_KEY = "picks_stale"  # the last selection was made before subjects changed (merge): ask to select again


def read_config(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT config_json FROM project WHERE id = 1").fetchone()
    try:
        cfg = json.loads(row[0]) if row and row[0] else {}
    except ValueError:
        cfg = {}
    return cfg if isinstance(cfg, dict) else {}


def write_config(conn: sqlite3.Connection, cfg: dict) -> None:
    conn.execute("UPDATE project SET config_json = ? WHERE id = 1", (json.dumps(cfg, separators=(",", ":")),))


def picks_stale(conn: sqlite3.Connection) -> bool:
    return bool(read_config(conn).get(STALE_KEY))


def set_picks_stale(conn: sqlite3.Connection, value: bool) -> None:
    cfg = read_config(conn)
    if bool(cfg.get(STALE_KEY)) == value:
        return
    if value:
        cfg[STALE_KEY] = True
    else:
        cfg.pop(STALE_KEY, None)
    write_config(conn, cfg)
