"""One chronological undo history per open session (F3 Batch 1).

Two kinds of entries share one counter (``seq``) and one LIFO order:

- **subject** corrections (merge, assign / move, remove, create, rename, mark / unmark "different"): the exact rows
  the action changed (occurrences, subjects, subject_pairs) before and after, kept in the session database
  (``project.config_json["undo"]``) in the SAME transaction as the action — so they survive a restart and can never
  disagree with the data. Bounded: MAX_PERSISTED entries and MAX_BYTES of JSON (oldest dropped first).
- **decision** changes (Keep/Reject, stars, ❤, focus label): the photo-level decision rows before the change, in
  memory only (a key press must stay fast), lost when the session closes.

Undo restores the "before" rows in one transaction. It refuses (UndoRefused, nothing changed) when the data no longer
matches what the action left: a manual assignment changed since, a deleted subject id was reused, or re-analysis
removed a photo's people. Rows the action left non-manual (e.g. photos released by keep_one_per_photo) are restored
as they were whatever the regrouping did since.

Learning (people examples) of a subject correction: collected during the action and written AFTER the session
commit under an operation id reserved beforehand in learning.db (negative namespace, see LearningStore.OP_BASE), so
an undo removes exactly those examples. Crash recovery at open: a "reserved" entry is checked against learning.db;
an undo's learning cleanup is recorded in the session first and retried until learning.db confirms it.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

from app.storage.project import Project
from app.storage.project_config import picks_stale, read_config, set_picks_stale, write_config

log = logging.getLogger(__name__)

JOURNAL_KEY = "undo"
CLEANUP_KEY = "undo_cleanup"
JOURNAL_VERSION = 1
MAX_PERSISTED = 50
MAX_BYTES = 1_000_000
MAX_MEMORY_DECISIONS = 200


class UndoTooLarge(RuntimeError):
    """The correction is too large to keep an undo record for: it is refused (nothing changed)."""


class UndoRefused(RuntimeError):
    """The data changed since the action in a way that makes an exact undo impossible."""


@dataclass(slots=True)
class Entry:
    seq: int
    kind: str  # "subject" | "decision"
    label: str
    data: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UndoResult:
    kind: str
    label: str
    asset_ids: tuple[int, ...] = ()


def clear_subject_history(conn: sqlite3.Connection) -> None:
    """Subject ids changed wholesale (renumbering): the persisted subject history no longer applies."""
    cfg = read_config(conn)
    if cfg.pop(JOURNAL_KEY, None) is not None:
        write_config(conn, cfg)


# ------------------------------------------------------------------ identity state snapshots
def _state(conn: sqlite3.Connection) -> tuple[dict, dict, set]:
    occ = {r[0]: (r[1], r[2], r[3], r[4]) for r in conn.execute(
        "SELECT id, subject_id, assignment, confidence, excluded_subject_id FROM occurrences")}
    subj = {r[0]: (r[1], r[2], r[3], r[4]) for r in conn.execute(
        "SELECT id, display_name, user_locked, merged_into, created_at FROM subjects")}
    pairs = {tuple(r) for r in conn.execute("SELECT a, b, relation, created_at FROM subject_pairs")}
    return occ, subj, pairs


def _diff(before: tuple, after: tuple) -> dict:
    occ_b, subj_b, pairs_b = before
    occ_a, subj_a, pairs_a = after
    occ = [[i, *occ_b[i], *occ_a[i]] for i in occ_a if i in occ_b and occ_b[i] != occ_a[i]]
    return {
        "occ": occ,
        "subj_added": [[i, *subj_a[i]] for i in subj_a if i not in subj_b],
        "subj_deleted": [[i, *subj_b[i]] for i in subj_b if i not in subj_a],
        "subj_changed": [[i, list(subj_b[i]), list(subj_a[i])] for i in subj_a if i in subj_b and subj_b[i] != subj_a[i]],
        "pairs_added": [list(p) for p in pairs_a - pairs_b],
        "pairs_removed": [list(p) for p in pairs_b - pairs_a],
    }


def _empty(d: dict) -> bool:
    return not any(d.get(k) for k in ("occ", "subj_added", "subj_deleted", "subj_changed", "pairs_added",
                                      "pairs_removed")) and "picks_stale" not in d


class UndoManager:
    def __init__(self, project: Project, teacher=None) -> None:  # noqa: ANN001
        self.project = project
        self.teacher = teacher
        self._entries: list[Entry] = []
        cfg = read_config(project.conn)
        for raw in cfg.get(JOURNAL_KEY, []) or []:
            if isinstance(raw, dict) and raw.get("v") == JOURNAL_VERSION and isinstance(raw.get("seq"), int):
                self._entries.append(Entry(raw["seq"], "subject", str(raw.get("label", "")), raw))
        self._entries.sort(key=lambda e: e.seq)
        self._seq = (self._entries[-1].seq + 1) if self._entries else 1
        self.restored_subject_entries = len(self._entries)
        self.recover()

    # ------------------------------------------------------------ queries
    @property
    def store(self):  # noqa: ANN201
        return getattr(self.teacher, "store", None)

    def can_undo(self) -> bool:
        return bool(self._entries)

    def next_label(self) -> str | None:
        return self._entries[-1].label if self._entries else None

    def __len__(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------ recovery (learning cleanup across crashes)
    def recover(self) -> None:
        store = self.store
        if store is None:
            return
        cfg = read_config(self.project.conn)
        pending = [op for op in cfg.get(CLEANUP_KEY, []) if isinstance(op, int)]
        done = []
        for op in pending:
            try:
                store.delete_operation(op)
                done.append(op)
            except Exception:  # noqa: BLE001 - retried at the next opportunity
                log.exception("undo: learning cleanup failed; will retry")
        changed = False
        for e in self._entries:
            if e.data.get("learning") == "reserved" and e.data.get("op_id") is not None:
                try:
                    e.data["learning"] = "written" if store.operation_has_examples(e.data["op_id"]) else "none"
                    changed = True
                except Exception:  # noqa: BLE001
                    log.exception("undo: could not check an operation's learning examples")
        if done or changed:
            with self.project.transaction() as conn:
                cfg = read_config(conn)
                cfg[CLEANUP_KEY] = [op for op in cfg.get(CLEANUP_KEY, []) if op not in done]
                if not cfg[CLEANUP_KEY]:
                    cfg.pop(CLEANUP_KEY)
                self._write_journal(cfg)
                write_config(conn, cfg)

    # ------------------------------------------------------------ subject corrections
    def subject_action(self, label: str, fn: Callable[[sqlite3.Connection], None]) -> bool:
        """Run ``fn(conn)`` (a subject correction, teacher calls included) as one undoable operation.

        Returns True when an undo entry was recorded, False when nothing changed. Exceptions from ``fn`` propagate,
        and UndoTooLarge is raised when the undo record would exceed MAX_BYTES; nothing is changed in either case."""
        teacher = self.teacher
        collecting = teacher is not None and self.store is not None
        if collecting:
            teacher.start_collecting()
        op_id = None
        entry: Entry | None = None
        try:
            with self.project.transaction() as conn:
                before = _state(conn)
                stale_before = picks_stale(conn)
                fn(conn)
                diff = _diff(before, _state(conn))
                stale_after = picks_stale(conn)
                if stale_after != stale_before:
                    diff["picks_stale"] = [stale_before, stale_after]
                items = teacher.stop_collecting() if collecting else []
                collecting = False
                if _empty(diff):
                    return False
                # Fail closed: a correction whose undo record cannot be kept is not done at all (the transaction
                # rolls back, learning.db is not touched — nothing is reserved yet).
                data = {"v": JOURNAL_VERSION, "seq": self._seq, "label": label, "op_id": -(2 ** 62),
                        "learning": "reserved", **diff}  # the largest the record can be
                size = len(json.dumps(data))
                if size > MAX_BYTES:
                    log.info("undo: correction refused, its undo record would be %d bytes", size)
                    raise UndoTooLarge(size)
                if items:
                    try:
                        op_id = self.store.reserve_operation()  # before the session commit (crash-safe)
                    except Exception:  # noqa: BLE001 - learning is optional; the action goes ahead
                        log.exception("undo: could not reserve a learning operation id")
                data.update(op_id=op_id, learning="reserved" if op_id is not None else "none")
                entry = Entry(self._seq, "subject", label, data)
                cfg = read_config(conn)
                self._entries.append(entry)
                self._write_journal(cfg)
                write_config(conn, cfg)
        except BaseException:
            if collecting:
                teacher.stop_collecting()
            if entry is not None and entry in self._entries:
                self._entries.remove(entry)
            if op_id is not None:
                self._delete_operation(op_id)
            raise
        self._seq += 1
        if op_id is not None:
            written = teacher.write_collected(items, op_id)
            if entry is not None:
                entry.data["learning"] = "written" if written else "none"
                with self.project.transaction() as conn:
                    cfg = read_config(conn)
                    self._write_journal(cfg)
                    write_config(conn, cfg)
            elif not written:
                self._delete_operation(op_id)
        elif items and teacher is not None:  # no reservation possible: write as ordinary answers (not undoable)
            for kind, same, pairs in items:
                teacher._save(kind, same, pairs)  # noqa: SLF001
        return entry is not None

    def _write_journal(self, cfg: dict) -> None:
        """Persist the subject entries (oldest dropped beyond the bounds)."""
        subject = [e for e in self._entries if e.kind == "subject"]
        while len(subject) > 1 and (len(subject) > MAX_PERSISTED or
                                    len(json.dumps([e.data for e in subject])) > MAX_BYTES):
            dropped = subject.pop(0)
            self._entries.remove(dropped)
        if subject:
            cfg[JOURNAL_KEY] = [e.data for e in subject]
        else:
            cfg.pop(JOURNAL_KEY, None)

    def _delete_operation(self, op_id: int) -> None:
        try:
            if self.store is not None:
                self.store.delete_operation(op_id)
        except Exception:  # noqa: BLE001
            log.exception("undo: could not remove a learning operation")

    def clear_subject_history(self, conn: sqlite3.Connection) -> None:
        """Inside the caller's transaction (renumbering): forget the persisted subject entries."""
        self._entries = [e for e in self._entries if e.kind != "subject"]
        clear_subject_history(conn)

    # ------------------------------------------------------------ decisions (memory only)
    @staticmethod
    def capture_decisions(conn: sqlite3.Connection, asset_ids: list[int]) -> dict[int, tuple | None]:
        out: dict[int, tuple | None] = {}
        for asset_id in asset_ids:
            row = conn.execute("""SELECT flag, rating, favorite, focus, updated_at FROM decisions
                                  WHERE asset_id = ? AND subject_id IS NULL""", (asset_id,)).fetchone()
            out[asset_id] = tuple(row) if row is not None else None
        return out

    def push_decisions(self, label: str, before: dict[int, tuple | None]) -> None:
        self._entries.append(Entry(self._seq, "decision", label, {"rows": before}))
        self._seq += 1
        decisions = [e for e in self._entries if e.kind == "decision"]
        if len(decisions) > MAX_MEMORY_DECISIONS:
            self._entries.remove(decisions[0])

    # ------------------------------------------------------------ undo
    def undo(self) -> UndoResult | None:
        """Undo the newest entry. Raises UndoRefused (the entry is dropped, nothing changed) when impossible."""
        if not self._entries:
            return None
        entry = self._entries[-1]
        if entry.kind == "decision":
            rows: dict[int, tuple | None] = entry.data["rows"]
            with self.project.transaction() as conn:
                for asset_id, row in rows.items():
                    conn.execute("DELETE FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (asset_id,))
                    if row is not None:
                        conn.execute("""INSERT INTO decisions (asset_id, subject_id, flag, rating, favorite, focus,
                                        updated_at) VALUES (?, NULL, ?, ?, ?, ?, ?)""", (asset_id, *row))
            self._entries.pop()
            return UndoResult("decision", entry.label, tuple(rows))
        try:
            assets = self._undo_subject(entry)
        except UndoRefused:
            with self.project.transaction() as conn:  # the action stands; its entry can never be undone exactly
                self._entries.remove(entry)
                cfg = read_config(conn)
                self._write_journal(cfg)
                write_config(conn, cfg)
            raise
        op_id = entry.data.get("op_id")
        if op_id is not None:  # its examples (if any) and its reservation row
            self._cleanup(op_id)
        return UndoResult("subject", entry.label, assets)

    def _undo_subject(self, entry: Entry) -> tuple[int, ...]:
        d = entry.data
        with self.project.transaction() as conn:
            occ, subj, pairs = _state(conn)
            for row in d.get("occ", []):
                i, after = row[0], tuple(row[5:9])
                if i not in occ:
                    raise UndoRefused("ảnh của chủ thể đã được phân tích lại sau thao tác này")
                if after[1] == "manual" and occ[i] != after:
                    raise UndoRefused("ảnh đã được sửa tiếp sau thao tác này")
            for i, before, after in d.get("subj_changed", []):
                if i in subj and subj[i] != tuple(after):
                    raise UndoRefused("chủ thể đã được sửa tiếp sau thao tác này")
            for row in d.get("subj_deleted", []):
                if row[0] in subj:
                    raise UndoRefused("số chủ thể đã được dùng cho chủ thể khác")
            conn.execute("PRAGMA defer_foreign_keys = ON")
            for i, name, locked, merged, created in d.get("subj_deleted", []):
                conn.execute("""INSERT INTO subjects (id, display_name, user_locked, merged_into, created_at)
                                VALUES (?, ?, ?, ?, ?)""", (i, name, locked, merged, created))
            for i, before, _after in d.get("subj_changed", []):
                if i in subj:
                    conn.execute("""UPDATE subjects SET display_name = ?, user_locked = ?, merged_into = ?,
                                    created_at = ? WHERE id = ?""", (*before, i))
            for row in d.get("occ", []):
                conn.execute("""UPDATE occurrences SET subject_id = ?, assignment = ?, confidence = ?,
                                excluded_subject_id = ? WHERE id = ?""", (*row[1:5], row[0]))
            for a, b, rel, _c in d.get("pairs_added", []):
                conn.execute("DELETE FROM subject_pairs WHERE a = ? AND b = ? AND relation = ?", (a, b, rel))
            for a, b, rel, created in d.get("pairs_removed", []):
                conn.execute("INSERT OR IGNORE INTO subject_pairs (a, b, relation, created_at) VALUES (?, ?, ?, ?)",
                             (a, b, rel, created))
            for row in d.get("subj_added", []):
                conn.execute("DELETE FROM subjects WHERE id = ?", (row[0],))
            # As after every regrouping: automatic subjects left without photos disappear (named ones stay).
            conn.execute("""DELETE FROM subjects WHERE user_locked = 0 AND display_name IS NULL
                            AND id NOT IN (SELECT subject_id FROM occurrences WHERE subject_id IS NOT NULL)""")
            if "picks_stale" in d:
                set_picks_stale(conn, bool(d["picks_stale"][0]))
            cfg = read_config(conn)
            self._entries.remove(entry)
            op_id = d.get("op_id")
            if op_id is not None:
                cfg[CLEANUP_KEY] = sorted(set(cfg.get(CLEANUP_KEY, [])) | {op_id})
            self._write_journal(cfg)
            write_config(conn, cfg)
            assets = {r[0] for r in conn.execute(
                f"SELECT asset_id FROM occurrences WHERE id IN ({','.join('?' * len(d.get('occ', [])))})",
                [row[0] for row in d.get("occ", [])])} if d.get("occ") else set()
        return tuple(sorted(assets))

    def _cleanup(self, op_id: int) -> None:
        """After the undo committed: remove the operation's learning rows, then acknowledge (idempotent)."""
        store = self.store
        if store is None:
            return  # recorded in the session; retried at the next open with learning available
        try:
            store.delete_operation(op_id)
        except Exception:  # noqa: BLE001
            log.exception("undo: learning cleanup failed; will retry at next open")
            return
        with self.project.transaction() as conn:
            cfg = read_config(conn)
            left = [op for op in cfg.get(CLEANUP_KEY, []) if op != op_id]
            if left:
                cfg[CLEANUP_KEY] = left
            else:
                cfg.pop(CLEANUP_KEY, None)
            write_config(conn, cfg)
