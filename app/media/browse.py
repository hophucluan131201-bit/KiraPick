"""What the Media grid shows (plan Mốc 1 M8): the three Mốc 1 filter groups (shot size, content, focus warnings), plus
camera source, moment, label state and P / X; photos in corrected-time order (capture time + the source's offset).

SQL fragments for app.ui.asset_model (they start with " AND " and use named parameters; ``a`` = assets, ``d`` =
decisions). Pure SQL over the event database: no model, no photo read.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.media import clock
from app.media import labels as lb

ANY = None


@dataclass(frozen=True, slots=True)
class MediaFilter:
    shot: str | None = ANY  # 'toan' | 'trung' | 'can' | '?' (Chưa xác định)
    content: str | None = ANY  # a CONTENT key, or 'none' (no content label)
    focus: str | None = ANY  # 'out_net' | 'trat_net' | 'none' (analysed, no warning) | '?' (could not be measured)
    camera_id: int | None = ANY
    moment_id: int | None = ANY
    state: str | None = ANY  # 'waiting' (⏳) | 'suggested' (AI, thử nghiệm) | 'confirmed'
    flag: str | None = ANY  # 'keep' | 'reject' | 'unflagged'

    @property
    def active(self) -> bool:
        return any(v is not None for v in (self.shot, self.content, self.focus, self.camera_id, self.moment_id,
                                          self.state, self.flag))


_SHOWN = "('suggested', 'confirmed')"


def filter_sql(f: MediaFilter) -> tuple[str, dict]:
    parts: list[str] = [" AND a.status = 'ok'"]
    params: dict = {}
    if f.shot is not None:
        if f.shot == lb.UNKNOWN:
            parts.append(" AND a.id IN (SELECT asset_id FROM labels WHERE grp = 'shot' AND value = '?')")
        else:
            parts.append(f" AND a.id IN (SELECT asset_id FROM labels WHERE grp = 'shot' AND value = :shot "
                         f"AND state IN {_SHOWN})")
            params["shot"] = f.shot
    if f.content is not None:
        if f.content == "none":
            parts.append(f" AND a.id NOT IN (SELECT asset_id FROM labels WHERE grp = 'content' AND state IN {_SHOWN})")
        else:
            parts.append(f" AND a.id IN (SELECT asset_id FROM labels WHERE grp = 'content' AND value = :content "
                         f"AND state IN {_SHOWN})")
            params["content"] = f.content
    if f.focus is not None:
        if f.focus == "none":  # analysed, measured, no warning shown ('?' = could not be measured is not "none")
            parts.append(" AND a.id IN (SELECT asset_id FROM media_analysis WHERE status = 'done')"
                         " AND a.id NOT IN (SELECT asset_id FROM labels WHERE grp = 'focus' AND state != 'removed')")
        elif f.focus == lb.UNKNOWN:
            parts.append(" AND a.id IN (SELECT asset_id FROM labels WHERE grp = 'focus' AND value = '?')")
        else:
            parts.append(f" AND a.id IN (SELECT asset_id FROM labels WHERE grp = 'focus' AND value = :focus "
                         f"AND state IN {_SHOWN})")
            params["focus"] = f.focus
    if f.camera_id is not None:
        parts.append(" AND a.id IN (SELECT asset_id FROM asset_source WHERE camera_id = :camera_id)")
        params["camera_id"] = f.camera_id
    if f.moment_id is not None:
        parts.append(" AND a.id IN (SELECT asset_id FROM moment_assets WHERE moment_id = :moment_id)")
        params["moment_id"] = f.moment_id
    if f.state == "waiting":
        parts.append(" AND a.id NOT IN (SELECT asset_id FROM media_analysis)")
    elif f.state in ("suggested", "confirmed"):
        parts.append(" AND a.id IN (SELECT asset_id FROM labels WHERE state = :state)")
        params["state"] = f.state
    if f.flag in ("keep", "reject"):
        parts.append(" AND d.flag = :flag")
        params["flag"] = f.flag
    elif f.flag == "unflagged":
        parts.append(" AND d.flag IS NULL")
    return "".join(parts), params


def matching_ids(conn: sqlite3.Connection, f: MediaFilter) -> list[int]:
    """The photos a filter shows, in corrected-time order (tests and export use this without the GUI)."""
    sql, params = filter_sql(f)
    rows = [r[0] for r in conn.execute(
        "SELECT a.id FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL WHERE 1" + sql,
        params)]
    order = time_order(conn)
    return sorted(rows, key=lambda a: order.get(a, len(order)))


def time_order(conn: sqlite3.Connection) -> dict[int, int]:
    """asset id -> position by corrected time (photos without a time last, by file name)."""
    times = clock.corrected_times(conn)
    names = {r[0]: r[1] for r in conn.execute("SELECT id, relative_path FROM assets")}
    ordered = sorted(times, key=lambda a: (times[a] is None, times[a] or 0.0, names.get(a, "")))
    return {a: i for i, a in enumerate(ordered)}


@dataclass(frozen=True, slots=True)
class CardInfo:
    """What a Media card shows besides the photo: shot size, focus warnings, ⏳, '(thử nghiệm)' on AI labels."""
    waiting: bool
    shot: tuple[str, str] | None  # (value, state)
    focus: tuple[tuple[str, str], ...]
    content: tuple[str, ...]  # confirmed content keys
    warning: bool  # ⚠ lệch giờ

    def lines(self) -> list[str]:
        out = []
        if self.waiting:
            out.append("⏳")
        if self.shot is not None:
            value, state = self.shot
            text = "Chưa xác định" if value == lb.UNKNOWN else lb.SHOT[value]
            out.append(text + (f" {lb.EXPERIMENTAL}" if state == "suggested" else ""))
        for value, state in self.focus:
            if value != lb.UNKNOWN:
                out.append(f"⚠ {lb.FOCUS[value]}" + (f" {lb.EXPERIMENTAL}" if state == "suggested" else ""))
        if self.warning:
            out.append("⚠ lệch giờ")
        return out


def card_info(conn: sqlite3.Connection) -> dict[int, CardInfo]:
    analysed = {r[0] for r in conn.execute("SELECT asset_id FROM media_analysis")}
    warned = {r[0] for r in conn.execute("SELECT asset_id FROM drift_warnings")}
    shot: dict[int, tuple[str, str]] = {}
    focus: dict[int, list[tuple[str, str]]] = {}
    content: dict[int, list[str]] = {}
    for a, grp, value, state in conn.execute(
            "SELECT asset_id, grp, value, state FROM labels WHERE state != 'removed' ORDER BY asset_id, grp, value"):
        if grp == "shot":
            shot[a] = (value, state)
        elif grp == "focus":
            focus.setdefault(a, []).append((value, state))
        elif state == "confirmed":
            content.setdefault(a, []).append(value)
    return {a: CardInfo(a not in analysed, shot.get(a), tuple(focus.get(a, ())), tuple(content.get(a, ())),
                        a in warned)
            for (a,) in conn.execute("SELECT id FROM assets WHERE status = 'ok'")}
