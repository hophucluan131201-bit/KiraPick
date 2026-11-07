"""Undo for Media actions (Ctrl+Z): clock changes, moment edits, labels (plan Mốc 1 M3-M5).

An action declares which rows it may change (table + WHERE). Before it runs, those rows are saved in
``media_journal`` in the same transaction; undo deletes the rows that WHERE now matches and puts the saved ones
back. Newest MAX_ENTRIES entries are kept, across restarts. P / X / stars are not in here: they keep the app's own
decision history.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

from app.storage.project import Project, utc_now

MAX_ENTRIES = 50


@dataclass(frozen=True, slots=True)
class Scope:
    table: str
    where: str = "1"
    params: tuple = field(default_factory=tuple)


def _rows(conn: sqlite3.Connection, scope: Scope) -> list[dict]:
    cur = conn.execute(f"SELECT * FROM {scope.table} WHERE {scope.where}", scope.params)  # noqa: S608
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def run(event: Project, label: str, scopes: list[Scope], action: Callable[[sqlite3.Connection], object]) -> object:
    """Run ``action`` in one transaction and record how to undo it."""
    with event.transaction() as conn:
        before = {f"{i}:{s.table}": {"table": s.table, "where": s.where, "params": list(s.params),
                                     "rows": _rows(conn, s)} for i, s in enumerate(scopes)}
        result = action(conn)
        conn.execute("INSERT INTO media_journal (label, before_json, created_at) VALUES (?, ?, ?)",
                     (label, json.dumps(before, ensure_ascii=False), utc_now()))
        conn.execute("""DELETE FROM media_journal WHERE id NOT IN
                        (SELECT id FROM media_journal ORDER BY id DESC LIMIT ?)""", (MAX_ENTRIES,))
    return result


def last_label(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT label FROM media_journal ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else str(row[0])


def undo(event: Project) -> str | None:
    """Undo the newest Media action; returns its label (None: nothing to undo)."""
    with event.transaction() as conn:
        row = conn.execute("SELECT id, label, before_json FROM media_journal ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        saved = json.loads(row["before_json"])
        for entry in saved.values():  # delete first (all scopes), then restore: scopes may share a table
            conn.execute(f"DELETE FROM {entry['table']} WHERE {entry['where']}", entry["params"])  # noqa: S608
        for entry in saved.values():
            for r in entry["rows"]:
                cols = ", ".join(r)
                marks = ", ".join("?" * len(r))
                conn.execute(f"INSERT OR REPLACE INTO {entry['table']} ({cols}) VALUES ({marks})",  # noqa: S608
                             list(r.values()))
        conn.execute("DELETE FROM media_journal WHERE id = ?", (row["id"],))
    return str(row["label"])
