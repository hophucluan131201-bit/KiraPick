"""Labels of an event and their states (Media spec §2-§6, §3; plan Mốc 1 M5).

Groups in Mốc 1: shot size (Toàn / Trung / Cận, one per photo), content (several per photo), focus warnings
(Out nét / Trật nét). People & roles are Mốc 2.

States: no row = Đang phân tích (⏳); 'unknown' = Chưa xác định; 'suggested' = AI gợi ý (shown "(thử nghiệm)" until
scored on real photos); 'confirmed' = the user's; 'removed' = the user took an AI label away.
Rules: nothing automatic overwrites 'confirmed' or 'removed' (analysis, re-analysis, clock changes, suggestions);
every user edit is one Ctrl+Z.

Content suggestions need CLIP, which is pending (MED-CLIP): content is set by hand only (fallback CT-F1/CT-F2) and
'Gợi ý lại' for content is off (CT-F3). Booth names are suggested by moment only (BT-F1).
"""

from __future__ import annotations

import sqlite3
from collections import Counter

from app.media import journal
from app.media.journal import Scope
from app.storage.project import Project, utc_now

SHOT = {"toan": "Toàn", "trung": "Trung", "can": "Cận"}
SHOT_KEYS = {"T": "toan", "U": "trung", "C": "can"}
CONTENT = {"san_khau": "Sân khấu", "booth": "Booth / Gian hàng", "decor": "Decor", "san_pham": "Sản phẩm",
           "merch": "Merch"}
CONTENT_KEYS = {str(i): v for i, v in enumerate(CONTENT, start=1)}  # 1-5
FOCUS = {"out_net": "Out nét", "trat_net": "Trật nét"}
UNKNOWN = "?"
GROUPS = {"shot": SHOT, "content": CONTENT, "focus": FOCUS}
EXPERIMENTAL = "(thử nghiệm)"  # every AI label until it is scored on real photos (spec §11)


def content_suggestions_available(registry=None) -> bool:  # noqa: ANN001
    """AI content labels need CLIP verified for Media (pending: MED-CLIP)."""
    from app.media.models import MediaRegistry

    return (registry or MediaRegistry()).available("clip_l14_image")


def _scope(asset_ids: list[int], grp: str | None = None) -> list[Scope]:
    marks = ",".join("?" * len(asset_ids)) or "NULL"
    where = f"asset_id IN ({marks})" + (" AND grp = ?" if grp else "")
    return [Scope("labels", where, tuple(asset_ids) + ((grp,) if grp else ()))]


def _check(grp: str, value: str) -> None:
    if grp not in GROUPS or (value != UNKNOWN and value not in GROUPS[grp]):
        raise ValueError(f"nhãn không hợp lệ: {grp}/{value}")


# ------------------------------------------------------------------------------------------------ AI side
def write_ai(conn: sqlite3.Connection, asset_id: int, grp: str, values: dict[str, float | None],
             run_id: int | None, *, unmeasurable: bool = False) -> None:
    """The analysis' result for one photo and group: ``values`` value -> confidence.

    Empty ``values``: shot size / content = Chưa xác định ('?'); focus = no warning (no row), or '?' when the photo
    could not be measured (``unmeasurable``: flat, too dark). Whether a photo was analysed at all is in
    ``media_analysis`` (no row there = ⏳).
    Replaces earlier AI rows of that group, never a 'confirmed' or 'removed' one. For shot size, a confirmed value
    means the AI result is not stored at all (one value per photo)."""
    for v in values:
        _check(grp, v)
    now = utc_now()
    kept = {r[0]: r[1] for r in conn.execute(
        "SELECT value, state FROM labels WHERE asset_id = ? AND grp = ? AND state IN ('confirmed', 'removed')",
        (asset_id, grp))}
    conn.execute("DELETE FROM labels WHERE asset_id = ? AND grp = ? AND state IN ('unknown', 'suggested')",
                 (asset_id, grp))
    if grp == "shot" and "confirmed" in kept.values():
        return
    rows = [(v, "suggested", c) for v, c in values.items() if v not in kept]
    if not values and (grp != "focus" or unmeasurable) and not any(s == "confirmed" for s in kept.values()):
        rows = [(UNKNOWN, "unknown", None)]
    conn.executemany("""INSERT INTO labels (asset_id, grp, value, state, confidence, run_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     [(asset_id, grp, v, st, c, run_id, now) for v, st, c in rows])


# ---------------------------------------------------------------------------------------------- user side
def confirm(event: Project, asset_ids: list[int], grp: str, value: str) -> None:
    """The user sets a label (T / U / C, 1-5, or confirms an AI suggestion) on one or more photos."""
    _check(grp, value)
    if value == UNKNOWN:
        raise ValueError("không gán 'Chưa xác định' bằng tay")

    def action(conn: sqlite3.Connection) -> None:
        now = utc_now()
        for a in asset_ids:
            if grp == "shot":  # one value: an AI suggestion the user replaced is 'removed', an old choice goes
                conn.execute("""UPDATE labels SET state = 'removed', updated_at = ?
                                WHERE asset_id = ? AND grp = 'shot' AND state = 'suggested' AND value != ?""",
                             (now, a, value))
                conn.execute("""DELETE FROM labels WHERE asset_id = ? AND grp = 'shot'
                                AND (value = ? OR state IN ('unknown', 'confirmed'))""", (a, UNKNOWN))
            else:
                conn.execute("DELETE FROM labels WHERE asset_id = ? AND grp = ? AND value = ?", (a, grp, UNKNOWN))
            conn.execute("""INSERT INTO labels (asset_id, grp, value, state, confidence, run_id, updated_at)
                            VALUES (?, ?, ?, 'confirmed', NULL, NULL, ?)
                            ON CONFLICT (asset_id, grp, value) DO UPDATE SET state = 'confirmed',
                            updated_at = excluded.updated_at""", (a, grp, value, now))

    journal.run(event, f"gán {GROUPS[grp][value]}", _scope(asset_ids, grp), action)


def remove(event: Project, asset_ids: list[int], grp: str, value: str) -> None:
    """The user takes a label away: an AI one becomes 'removed' (never suggested again), a confirmed one goes."""
    _check(grp, value)

    def action(conn: sqlite3.Connection) -> None:
        now = utc_now()
        for a in asset_ids:
            conn.execute("""UPDATE labels SET state = 'removed', updated_at = ?
                            WHERE asset_id = ? AND grp = ? AND value = ? AND state = 'suggested'""", (now, a, grp, value))
            conn.execute("DELETE FROM labels WHERE asset_id = ? AND grp = ? AND value = ? AND state = 'confirmed'",
                         (a, grp, value))

    journal.run(event, f"bỏ {GROUPS[grp].get(value, value)}", _scope(asset_ids, grp), action)


def toggle_content(event: Project, asset_ids: list[int], key: str) -> None:
    """Key 1-5: set the content label on the photos; if all of them already have it, take it away."""
    value = CONTENT_KEYS[key]
    have = {r[0] for r in event.conn.execute(
        f"SELECT asset_id FROM labels WHERE grp = 'content' AND value = ? AND state = 'confirmed' "  # noqa: S608
        f"AND asset_id IN ({','.join('?' * len(asset_ids))})", (value, *asset_ids))}
    if asset_ids and have == set(asset_ids):
        remove(event, asset_ids, "content", value)
    else:
        confirm(event, asset_ids, "content", value)


def labels_of(conn: sqlite3.Connection, asset_id: int) -> dict[str, list[tuple[str, str, float | None]]]:
    """Group -> [(value, state, confidence)] shown for a photo ('removed' ones are hidden); missing group = ⏳."""
    out: dict[str, list] = {}
    for grp, value, state, conf in conn.execute(
            "SELECT grp, value, state, confidence FROM labels WHERE asset_id = ? ORDER BY grp, value", (asset_id,)):
        out.setdefault(grp, [])
        if state != "removed":
            out[grp].append((value, state, conf))
    return out


def shot_coverage(conn: sqlite3.Connection, moment_id: int) -> dict[str, bool]:
    """'Toàn ✓ Trung ✓ Cận ✗' of a moment, over its photos marked P (spec §8; confirmed or AI-suggested sizes)."""
    rows = {r[0] for r in conn.execute(
        """SELECT l.value FROM labels l JOIN moment_assets ma ON ma.asset_id = l.asset_id
           JOIN decisions d ON d.asset_id = l.asset_id AND d.subject_id IS NULL
           WHERE ma.moment_id = ? AND l.grp = 'shot' AND l.state IN ('suggested', 'confirmed') AND d.flag = 'keep'""",
        (moment_id,))}
    return {v: v in rows for v in SHOT}


# --------------------------------------------------------------------------------------------- booth names
def assign_booth(event: Project, asset_ids: list[int], name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("tên booth trống")
    marks = ",".join("?" * len(asset_ids))

    def action(conn: sqlite3.Connection) -> int:
        conn.execute("INSERT OR IGNORE INTO booth_names (name) VALUES (?)", (name,))
        booth = int(conn.execute("SELECT id FROM booth_names WHERE name = ?", (name,)).fetchone()[0])
        conn.executemany("""INSERT INTO asset_booth (asset_id, booth_id, state) VALUES (?, ?, 'confirmed')
                            ON CONFLICT (asset_id) DO UPDATE SET booth_id = excluded.booth_id, state = 'confirmed'""",
                         [(a, booth) for a in asset_ids])
        return booth

    return journal.run(event, f"tên booth {name}",
                       [Scope("asset_booth", f"asset_id IN ({marks})", tuple(asset_ids)), Scope("booth_names")],
                       action)


def suggest_booths(event: Project) -> int:
    """BT-F1 (no CLIP): photos without a booth name get the most used confirmed name of THEIR moment; never across
    moments, never over a confirmed name. Returns the photos suggested. One Ctrl+Z."""

    def action(conn: sqlite3.Connection) -> int:
        conn.execute("DELETE FROM asset_booth WHERE state = 'suggested'")
        by_moment: dict[int, Counter] = {}
        for moment_id, booth in conn.execute(
                """SELECT ma.moment_id, b.booth_id FROM asset_booth b JOIN moment_assets ma ON ma.asset_id = b.asset_id
                   WHERE b.state = 'confirmed'"""):
            by_moment.setdefault(moment_id, Counter())[booth] += 1
        n = 0
        for moment_id, counts in by_moment.items():
            booth = counts.most_common(1)[0][0]
            free = [r[0] for r in conn.execute(
                """SELECT asset_id FROM moment_assets WHERE moment_id = ?
                   AND asset_id NOT IN (SELECT asset_id FROM asset_booth)""", (moment_id,))]
            conn.executemany("INSERT INTO asset_booth (asset_id, booth_id, state) VALUES (?, ?, 'suggested')",
                             [(a, booth) for a in free])
            n += len(free)
        return n

    return journal.run(event, "gợi ý tên booth", [Scope("asset_booth")], action)


def booth_of(conn: sqlite3.Connection, asset_id: int) -> tuple[str, str] | None:
    row = conn.execute("""SELECT n.name, b.state FROM asset_booth b JOIN booth_names n ON n.id = b.booth_id
                          WHERE b.asset_id = ?""", (asset_id,)).fetchone()
    return None if row is None else (row[0], row[1])
