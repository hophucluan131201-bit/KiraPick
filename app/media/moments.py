"""Moments of an event (Media spec §8, plan Mốc 1 M4).

- AI split: by pauses in the corrected time only (CLIP is pending: fallback MT-F1). Photos without a time form the
  'Không rõ giờ' moment.
- 📌 pinned moments (any edit by the user: split here, merge, move photos, rename) keep their photo list: re-analysis
  and clock changes re-split only the photos outside pinned moments.
- ⚠ drift rule after a clock change of source S (spec §8, unchanged): only S's photos in pinned moments are checked,
  against ranges R(K) built from each moment's photos NOT from S (needs >= 2 of them), widened by TAU seconds.
  p in pinned M is warned iff R(M) exists, p is outside R(M) ± τ and inside R(N) ± τ of another moment N; the
  suggested moment is the N whose range centre is nearest. A new clock change of S replaces S's warnings.
- Every edit is one undoable action (app.media.journal).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from app.media import clock, journal
from app.media.journal import Scope
from app.storage.project import Project, utc_now

DEFAULT_GAP_S = 300.0  # a pause longer than this starts a new AI moment (tuned on sample photos later)
TAU_S = 30.0  # drift tolerance (spec §8)
NO_TIME_NAME = "Không rõ giờ"
ALL = [Scope("moments"), Scope("moment_assets"), Scope("drift_warnings")]


@dataclass(frozen=True, slots=True)
class Moment:
    id: int
    name: str
    pinned: bool
    no_time: bool
    assets: tuple[int, ...]  # in corrected time order
    start: float | None


def _name_for(start: float | None) -> str:
    return NO_TIME_NAME if start is None else "Khoảnh khắc " + datetime.fromtimestamp(start).strftime("%H:%M")


def _order(conn: sqlite3.Connection, ids: list[int], times: dict[int, float | None]) -> list[int]:
    paths = {r[0]: r[1] for r in conn.execute("SELECT id, relative_path FROM assets")}
    return sorted(ids, key=lambda a: (times.get(a) is None, times.get(a) or 0.0, paths.get(a, ""), a))


def moments(conn: sqlite3.Connection) -> list[Moment]:
    times = clock.corrected_times(conn)
    rows = conn.execute("SELECT id, name, pinned, no_time FROM moments").fetchall()
    members: dict[int, list[int]] = {}
    for asset_id, moment_id in conn.execute("SELECT asset_id, moment_id FROM moment_assets"):
        members.setdefault(moment_id, []).append(asset_id)
    out = []
    for r in rows:
        ordered = _order(conn, members.get(r["id"], []), times)
        start = next((times[a] for a in ordered if times.get(a) is not None), None)
        out.append(Moment(r["id"], r["name"], bool(r["pinned"]), bool(r["no_time"]), tuple(ordered), start))
    return sorted(out, key=lambda m: (m.start is None, m.start or 0.0, m.id))


def moment_of(conn: sqlite3.Connection, asset_id: int) -> int | None:
    row = conn.execute("SELECT moment_id FROM moment_assets WHERE asset_id = ?", (asset_id,)).fetchone()
    return None if row is None else int(row[0])


def _new(conn: sqlite3.Connection, name: str, assets: list[int], *, pinned: bool, no_time: bool = False) -> int:
    mid = int(conn.execute("INSERT INTO moments (name, pinned, no_time, created_at) VALUES (?, ?, ?, ?)",
                           (name, int(pinned), int(no_time), utc_now())).lastrowid)
    conn.executemany("""INSERT INTO moment_assets (asset_id, moment_id) VALUES (?, ?)
                        ON CONFLICT (asset_id) DO UPDATE SET moment_id = excluded.moment_id""",
                     [(a, mid) for a in assets])
    return mid


def _drop_empty(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM moments WHERE id NOT IN (SELECT moment_id FROM moment_assets)")


def resplit(conn: sqlite3.Connection, gap_s: float = DEFAULT_GAP_S) -> None:
    """Re-make the AI moments from the photos outside pinned moments (pinned ones and warnings untouched)."""
    times = clock.corrected_times(conn)
    pinned_assets = {r[0] for r in conn.execute(
        "SELECT ma.asset_id FROM moment_assets ma JOIN moments m ON m.id = ma.moment_id WHERE m.pinned = 1")}
    conn.execute("DELETE FROM moment_assets WHERE moment_id IN (SELECT id FROM moments WHERE pinned = 0)")
    # (a ⚠ whose suggested moment was an AI moment goes with it: that moment no longer exists)
    conn.execute("DELETE FROM moments WHERE pinned = 0")
    free = _order(conn, [a for a in times if a not in pinned_assets], times)
    timed = [a for a in free if times[a] is not None]
    untimed = [a for a in free if times[a] is None]
    group: list[int] = []
    for a in timed:
        if group and times[a] - times[group[-1]] > gap_s:
            _new(conn, _name_for(times[group[0]]), group, pinned=False)
            group = []
        group.append(a)
    if group:
        _new(conn, _name_for(times[group[0]]), group, pinned=False)
    if untimed:
        _new(conn, NO_TIME_NAME, untimed, pinned=False, no_time=True)
    _drop_empty(conn)


def analyse(event: Project, gap_s: float = DEFAULT_GAP_S) -> None:
    """Split (or re-split) the moments; part of 'Phân tích sự kiện'. Not undoable: it changes no user decision."""
    with event.transaction() as conn:
        resplit(conn, gap_s)


# ----------------------------------------------------------------------------------------------- user edits (📌)
def _pin(conn: sqlite3.Connection, *moment_ids: int) -> None:
    conn.executemany("UPDATE moments SET pinned = 1 WHERE id = ?", [(m,) for m in moment_ids])


def split_here(event: Project, asset_id: int) -> int:
    """'Tách tại đây': this photo and the later ones of its moment become a new moment; both are pinned."""

    def action(conn: sqlite3.Connection) -> int:
        mid = moment_of(conn, asset_id)
        if mid is None:
            raise ValueError("ảnh chưa thuộc khoảnh khắc nào")
        m = next(x for x in moments(conn) if x.id == mid)
        later = list(m.assets[m.assets.index(asset_id):])
        if len(later) == len(m.assets):
            raise ValueError("ảnh đầu tiên của khoảnh khắc: không có gì để tách")
        times = clock.corrected_times(conn)
        new_id = _new(conn, _name_for(times.get(later[0])), later, pinned=True)
        _pin(conn, mid)
        return new_id

    return journal.run(event, "tách khoảnh khắc", ALL, action)


def merge(event: Project, keep: int, other: int) -> None:
    def action(conn: sqlite3.Connection) -> None:
        conn.execute("UPDATE moment_assets SET moment_id = ? WHERE moment_id = ?", (keep, other))
        conn.execute("UPDATE drift_warnings SET suggested = ? WHERE suggested = ?", (keep, other))
        conn.execute("DELETE FROM moments WHERE id = ?", (other,))
        _pin(conn, keep)

    journal.run(event, "gộp khoảnh khắc", ALL, action)


def move_photos(event: Project, asset_ids: list[int], target: int, label: str = "chuyển ảnh") -> None:
    def action(conn: sqlite3.Connection) -> None:
        sources = {moment_of(conn, a) for a in asset_ids} - {None, target}
        conn.executemany("UPDATE moment_assets SET moment_id = ? WHERE asset_id = ?", [(target, a) for a in asset_ids])
        conn.executemany("DELETE FROM drift_warnings WHERE asset_id = ?", [(a,) for a in asset_ids])
        _pin(conn, target, *sources)
        _drop_empty(conn)

    journal.run(event, label, ALL, action)


def rename(event: Project, moment_id: int, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("tên khoảnh khắc trống")

    def action(conn: sqlite3.Connection) -> None:
        conn.execute("UPDATE moments SET name = ?, pinned = 1 WHERE id = ?", (name, moment_id))

    journal.run(event, "đổi tên khoảnh khắc", ALL, action)


# ------------------------------------------------------------------------------------------- clock + ⚠ drift
def _ranges(conn: sqlite3.Connection, camera_id: int, times: dict[int, float | None]) -> dict[int, tuple[float, float]]:
    """R(K) ± τ from each moment's photos not from ``camera_id`` (moments with fewer than 2 have none)."""
    cams = {r[0]: r[1] for r in conn.execute("SELECT asset_id, camera_id FROM asset_source")}
    by_moment: dict[int, list[float]] = {}
    for asset_id, moment_id in conn.execute("SELECT asset_id, moment_id FROM moment_assets"):
        t = times.get(asset_id)
        if t is not None and cams.get(asset_id) != camera_id:
            by_moment.setdefault(moment_id, []).append(t)
    return {m: (min(ts) - TAU_S, max(ts) + TAU_S) for m, ts in by_moment.items() if len(ts) >= 2}


def check_drift(conn: sqlite3.Connection, camera_id: int) -> list[int]:
    """Replace the ⚠ of ``camera_id``'s photos by the result of the spec §8 rule; returns the warned photos."""
    conn.execute("DELETE FROM drift_warnings WHERE camera_id = ?", (camera_id,))
    times = clock.corrected_times(conn)
    ranges = _ranges(conn, camera_id, times)
    rows = conn.execute(
        """SELECT ma.asset_id, ma.moment_id FROM moment_assets ma JOIN moments m ON m.id = ma.moment_id
           JOIN asset_source s ON s.asset_id = ma.asset_id WHERE m.pinned = 1 AND s.camera_id = ?""",
        (camera_id,)).fetchall()
    warned = []
    for asset_id, mid in rows:
        t = times.get(asset_id)
        if t is None or mid not in ranges:
            continue
        lo, hi = ranges[mid]
        if lo <= t <= hi:
            continue
        others = [(abs(t - (r[0] + r[1]) / 2), n) for n, r in ranges.items() if n != mid and r[0] <= t <= r[1]]
        if not others:
            continue  # in a gap: no warning
        conn.execute("INSERT INTO drift_warnings (asset_id, suggested, camera_id) VALUES (?, ?, ?)",
                     (asset_id, min(others)[1], camera_id))
        warned.append(asset_id)
    return warned


def set_clock(event: Project, camera_id: int, seconds: float, gap_s: float = DEFAULT_GAP_S) -> None:
    """Change one source's clock: re-split the AI part, check ⚠ for that source; one Ctrl+Z undoes all of it."""

    def after(conn: sqlite3.Connection) -> None:
        resplit(conn, gap_s)
        check_drift(conn, camera_id)

    clock.set_offset(event, camera_id, seconds, extra_scopes=ALL, after=after)


def warnings(conn: sqlite3.Connection) -> dict[int, int]:
    """Photo -> suggested moment, for the ⚠ shown in the moment strip."""
    return {r[0]: r[1] for r in conn.execute("SELECT asset_id, suggested FROM drift_warnings")}


def accept_warning(event: Project, asset_id: int) -> None:
    """'Chuyển': move the photo to the suggested moment (clears its ⚠)."""
    target = warnings(event.conn).get(asset_id)
    if target is None:
        raise ValueError("ảnh không có cảnh báo lệch giờ")
    move_photos(event, [asset_id], target, label="chuyển ảnh lệch giờ")


def keep_warning(event: Project, asset_id: int) -> None:
    """'Giữ': the photo stays; its ⚠ goes."""
    journal.run(event, "giữ ảnh lệch giờ", ALL,
                lambda conn: conn.execute("DELETE FROM drift_warnings WHERE asset_id = ?", (asset_id,)))
