"""🧪 Thử nghiệm (REG-2, off by default, switched on per event): near-duplicate groups inside a moment, one suggested
photo per group. A rule on the photos already imported and analysed, no model:

- two photos taken one after the other are in the same group when they are in the same moment, from the same camera
  source, at most ``max_gap_s`` apart (corrected time), with the same shot size (Toàn / Trung / Cận / not known), and
  their thumbnails look alike (difference hash, at most ``max_distance`` of 64 bits differ);
- the suggested photo of a group: no focus warning first, then the sharpest subject (Media focus measure on the
  original), then the earliest. A group of one photo is always suggested, focus warning or not;
- the user's fixes win: "Tách khỏi nhóm" (the photo starts its own group) and "Gộp với nhóm trước" (no break before
  this photo, same moment and camera only), kept in the event (media_meta 'near_dup_fixes'), counted as group fixes,
  undone by Ctrl+Z like the other Media actions (journal).

Nothing is hidden or removed: "chỉ ảnh đại diện" is a view filter; P / X stay the user's.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.media import clock

META_ON = "near_dup_experiment"
META_FIXES = "near_dup_fixes"
SHOT_UNKNOWN = "?"


@dataclass(frozen=True, slots=True)
class Rules:
    max_gap_s: float = 10.0
    max_distance: int = 12  # of 64 bits


@dataclass(slots=True)
class Group:
    moment_id: int | None
    members: list[int]  # in time order
    representative: int
    warned_single: bool = False  # one photo, with a focus warning: suggested anyway, said so on the card

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(slots=True)
class Grouping:
    groups: list[Group] = field(default_factory=list)
    group_of: dict[int, int] = field(default_factory=dict)  # asset id -> index in groups

    def representatives(self) -> set[int]:
        return {g.representative for g in self.groups}

    def group(self, asset_id: int) -> Group | None:
        i = self.group_of.get(asset_id)
        return self.groups[i] if i is not None else None


# ------------------------------------------------------------------------------------------------ settings
def is_on(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT value FROM media_meta WHERE key = ?", (META_ON,)).fetchone()
    return row is not None and row[0] == "1"


def set_on(conn: sqlite3.Connection, on: bool) -> None:
    conn.execute("INSERT INTO media_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (META_ON, "1" if on else "0"))


def fixes(conn: sqlite3.Connection) -> dict[int, str]:
    """asset id -> 'break' (starts its own group) | 'join' (never a break before it)."""
    row = conn.execute("SELECT value FROM media_meta WHERE key = ?", (META_FIXES,)).fetchone()
    return {int(k): v for k, v in json.loads(row[0]).items()} if row else {}


def set_fix(conn: sqlite3.Connection, asset_id: int, fix: str | None) -> None:
    current = fixes(conn)
    if fix is None:
        current.pop(asset_id, None)
    else:
        current[asset_id] = fix
    conn.execute("INSERT INTO media_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (META_FIXES, json.dumps({str(k): v for k, v in sorted(current.items())})))


def fix_group(event, asset_id: int, fix: str | None) -> None:  # noqa: ANN001 - a MediaEvent / Project
    """The user's group fix as a journaled Media action: one Ctrl+Z undoes it, like ✂ / gộp khoảnh khắc."""
    from app.media import journal

    label = {"break": "tách khỏi nhóm gần trùng", "join": "gộp nhóm gần trùng"}.get(fix or "", "bỏ sửa nhóm")
    journal.run(event, label, [journal.Scope("media_meta", "key = ?", (META_FIXES,))],
                lambda conn: set_fix(conn, asset_id, fix))


# ------------------------------------------------------------------------------------------------ hashing
def dhash(gray: np.ndarray) -> int:
    """64-bit difference hash of a grey image (any size)."""
    from PIL import Image

    small = np.asarray(Image.fromarray(gray).resize((9, 8), Image.Resampling.BILINEAR), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def thumbnail_hashes(conn: sqlite3.Connection, cache_dir: Path, known: dict[int, int] | None = None) -> dict[int, int]:
    """asset id -> dhash of its thumbnail (assets without a thumbnail are left out). Runs off the Qt thread."""
    from PIL import Image

    out = dict(known or {})
    for asset_id, name in conn.execute("SELECT asset_id, file_name FROM previews WHERE kind = 'thumb'"):
        if asset_id in out:
            continue
        try:
            with Image.open(cache_dir / name) as im:
                out[asset_id] = dhash(np.asarray(im.convert("L")))
        except OSError:
            continue
    return out


# ------------------------------------------------------------------------------------------------ grouping
def _sharpness(measures_json: str | None) -> float:
    try:
        focus = (json.loads(measures_json) or {}).get("focus") or {}
    except (TypeError, ValueError):
        return 0.0
    value = focus.get("subject") if focus.get("subject") is not None else focus.get("tiles_max")
    return float(value) if isinstance(value, (int, float)) else 0.0


def build(conn: sqlite3.Connection, hashes: dict[int, int], rules: Rules = Rules()) -> Grouping:  # noqa: B008
    times = clock.corrected_times(conn)
    names = {r[0]: r[1] for r in conn.execute("SELECT id, relative_path FROM assets WHERE status = 'ok'")}
    moment = {a: m for a, m in conn.execute("SELECT asset_id, moment_id FROM moment_assets")}
    source = {a: c for a, c in conn.execute("SELECT asset_id, camera_id FROM asset_source")}
    shot = {a: v for a, v in conn.execute("SELECT asset_id, value FROM labels WHERE grp = 'shot' AND state != 'removed'")}
    warned = {a for (a,) in conn.execute(
        "SELECT DISTINCT asset_id FROM labels WHERE grp = 'focus' AND state != 'removed' AND value != '?'")}
    sharp = {a: _sharpness(m) for a, m in conn.execute("SELECT asset_id, measures_json FROM media_analysis")}
    fix = fixes(conn)
    # one stream per camera inside each moment: two cameras shooting the same moment interleave in time
    order = sorted(names, key=lambda a: (moment.get(a) is None, moment.get(a) or 0, source.get(a) or 0,
                                         times.get(a) is None, times.get(a) or 0.0, names[a]))
    out = Grouping()
    current: list[int] = []

    def close() -> None:
        if not current:
            return
        rep = min(current, key=lambda a: (a in warned, -sharp.get(a, 0.0), current.index(a)))
        out.groups.append(Group(moment.get(current[0]), list(current), rep,
                                warned_single=len(current) == 1 and rep in warned))
        for a in current:
            out.group_of[a] = len(out.groups) - 1
        current.clear()

    for a in order:
        if current and not _same_group(current[-1], a, fix, moment, source, shot, times, hashes, rules):
            close()
        current.append(a)
    close()
    return out


def _same_group(prev: int, a: int, fix: dict[int, str], moment: dict, source: dict, shot: dict, times: dict,
                hashes: dict[int, int], rules: Rules) -> bool:
    if fix.get(a) == "break":
        return False
    if moment.get(prev) != moment.get(a):
        return False  # a moment boundary is never crossed, even by a 'join'
    if source.get(prev) != source.get(a):
        return False  # another camera: never the same burst, even by a 'join'
    if fix.get(a) == "join":
        return True
    if shot.get(prev, SHOT_UNKNOWN) != shot.get(a, SHOT_UNKNOWN):
        return False
    tp, ta = times.get(prev), times.get(a)
    if tp is None or ta is None or abs(ta - tp) > rules.max_gap_s:
        return False
    hp, ha = hashes.get(prev), hashes.get(a)
    return hp is not None and ha is not None and distance(hp, ha) <= rules.max_distance


def moments_without_pick(conn: sqlite3.Connection) -> list[int]:
    """Moments where no photo is P yet (shown as '⚠ chưa có ảnh giao' while the experiment is on)."""
    return [m for (m,) in conn.execute(
        """SELECT m.id FROM moments m WHERE NOT EXISTS (
               SELECT 1 FROM moment_assets ma JOIN decisions d ON d.asset_id = ma.asset_id AND d.subject_id IS NULL
               WHERE ma.moment_id = m.id AND d.flag = 'keep') ORDER BY m.id""")]


HashFn = Callable[[sqlite3.Connection, Path, dict[int, int] | None], dict[int, int]]
