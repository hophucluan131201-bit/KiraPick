"""One Ctrl+Z history for the Media window: Media actions (clock, moments, labels, booth names: app.media.journal,
kept across restarts) and photo decisions (P / X, stars, ❤: in memory, as in Chụp cá nhân), newest first.

Undo of a moment edit made before a 'Phân tích lại' restores the moments as they were saved, so the AI split made
after it comes back too (R1-UNDO-AI, kept for Mốc 1): ``Undone.notice`` says so, and the window shows it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.media import journal
from app.storage import decisions
from app.storage.project import Project

MAX_DECISIONS = 200


@dataclass(frozen=True, slots=True)
class Undone:
    kind: str  # 'media' | 'decision'
    label: str
    notice: str | None
    assets: tuple[int, ...] = ()


class EventUndo:
    def __init__(self, event: Project) -> None:
        self.event = event
        self._stack: list[tuple[str, object]] = [("media", i) for i in journal.ids(event.conn)]  # journal survives

    def __len__(self) -> int:
        return len(self._stack)

    def can_undo(self) -> bool:
        return bool(self._stack)

    def next_label(self) -> str | None:
        if not self._stack:
            return None
        kind, data = self._stack[-1]
        return journal.last_label(self.event.conn) if kind == "media" else data[0]  # type: ignore[index]

    # ------------------------------------------------------------------------------------------- record
    def media(self, fn: Callable[..., object], *args, **kwargs) -> object:  # noqa: ANN002, ANN003
        """Run a journaled Media action (labels.confirm, moments.split_here, clock.set_offset…) and record it."""
        before = journal.newest_id(self.event.conn)
        result = fn(self.event, *args, **kwargs)
        after = journal.newest_id(self.event.conn)
        if after is not None and after != before:
            self._stack.append(("media", after))
        self._trim()
        return result

    def decision(self, label: str, asset_ids: list[int], fn: Callable[[], None]) -> None:
        """A P / X / star / ❤ change on these photos: their decision rows are saved first."""
        conn = self.event.conn
        before = {}
        for a in asset_ids:
            row = conn.execute("""SELECT flag, rating, favorite, focus, updated_at FROM decisions
                                  WHERE asset_id = ? AND subject_id IS NULL""", (a,)).fetchone()
            before[a] = tuple(row) if row is not None else None
        fn()
        self._stack.append(("decision", (label, before)))
        self._trim()

    def set_flag(self, asset_ids: list[int], flag: str | None) -> None:
        label = {"keep": "chọn P", "reject": "loại X", None: "bỏ P/X"}[flag]
        self.decision(label, asset_ids, lambda: [decisions.set_flag(self.event.conn, a, flag) for a in asset_ids])

    def set_rating(self, asset_ids: list[int], rating: int) -> None:
        self.decision(f"{rating} sao", asset_ids,
                      lambda: [decisions.set_rating(self.event.conn, a, rating) for a in asset_ids])

    def set_favorite(self, asset_ids: list[int], favorite: bool) -> None:
        self.decision("❤", asset_ids, lambda: [decisions.set_favorite(self.event.conn, a, favorite) for a in asset_ids])

    def _trim(self) -> None:
        decision_entries = [e for e in self._stack if e[0] == "decision"]
        while len(decision_entries) > MAX_DECISIONS:
            self._stack.remove(decision_entries.pop(0))
        alive = set(journal.ids(self.event.conn))  # the journal keeps its newest MAX_ENTRIES
        self._stack = [e for e in self._stack if e[0] != "media" or e[1] in alive]

    # --------------------------------------------------------------------------------------------- undo
    def notice(self) -> str | None:
        """What the next Ctrl+Z will also bring back (shown before / after undoing)."""
        if self._stack and self._stack[-1][0] == "media":
            return journal.undo_notice(self.event.conn)
        return None

    def undo(self) -> Undone | None:
        if not self._stack:
            return None
        kind, data = self._stack.pop()
        if kind == "media":
            notice = journal.undo_notice(self.event.conn)
            label = journal.undo(self.event)
            return Undone("media", label or "", notice)
        label, rows = data  # type: ignore[misc]
        with self.event.transaction() as conn:
            for asset_id, row in rows.items():
                conn.execute("DELETE FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (asset_id,))
                if row is not None:
                    conn.execute("""INSERT INTO decisions (asset_id, subject_id, flag, rating, favorite, focus,
                                    updated_at) VALUES (?, NULL, ?, ?, ?, ?, ?)""", (asset_id, *row))
        return Undone("decision", label, None, tuple(rows))
