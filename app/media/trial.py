"""Numbers for the Media classification trial (REG-2): every user action in an event window is one local log line
``media action: event=<event id> kind=<kind> n=<photos>`` (no photo name, path or metadata), and

    KiraPick.exe --media-counts "<tên sự kiện>" [--ranh-gioi "<sự kiện ranh giới>"] [--out ket-qua.json]
    python -m app --media-counts "<tên sự kiện>" [...]          (from the source)

prints, read-only: photos, moments, moments without a P photo, P / X counts, the 🧪 near-duplicate groups (when the
experiment is on: groups, groups of one, suggested photos, the user's group fixes), the actions by kind and the
time between the first and the last action. The time to the delivery folder is also measured by the owner
(stopwatch); this is the cross-check.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

log = logging.getLogger("app.media.trial")

KINDS = ("keep", "reject", "unflag", "rating", "favorite", "shot", "content", "focus", "booth", "split", "merge",
         "rename", "move", "drift", "clock", "undo", "compare", "client_list", "export", "experiment_on",
         "experiment_off", "group_open", "group_close", "group_break", "group_join")
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*media action: event=(\S+) kind=(\w+) n=(\d+)")


def record(event_id: str, kind: str, n: int = 1) -> None:
    if kind not in KINDS:
        raise ValueError(kind)
    log.info("media action: event=%s kind=%s n=%d", event_id, kind, max(0, int(n)))


def decision_kind(label: str) -> str:
    """The kind of a 3.0.0 decision from its undo label (Chọn / Loại / bỏ Chọn / N sao / yêu thích)."""
    if label.startswith("Chọn"):
        return "keep"
    if label.startswith("Loại"):
        return "reject"
    if "sao" in label:
        return "rating"
    if "yêu thích" in label:
        return "favorite"
    return "unflag"


def _open_ro(event_folder: Path) -> sqlite3.Connection:
    from app.storage.project import DB_NAME

    conn = sqlite3.connect(f"file:{event_folder / DB_NAME}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _keys(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    """asset id -> (photo folder, file inside it): the same photo in two events of the same folder."""
    return {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT a.id, s.root_path, a.relative_path FROM assets a JOIN sources s ON s.id = a.source_id "
        "WHERE a.status = 'ok'")}


def owner_boundaries(reference_folder: Path) -> set[tuple[str, str]]:
    """The photos the owner marked 'B: starts a new activity' (🏷 sample mode) in the reference event."""
    conn = _open_ro(reference_folder)
    try:
        keys = _keys(conn)
        return {keys[a] for (a,) in conn.execute(
            "SELECT asset_id FROM sample_labels WHERE grp = 'boundary' AND value = 'start'") if a in keys}
    finally:
        conn.close()


def against_boundaries(conn: sqlite3.Connection, boundaries: set[tuple[str, str]], grouping=None) -> dict:  # noqa: ANN001
    """Moments (and 🧪 groups) of this event against the owner's activity boundaries.

    activities: the owner's activities (a new one at each marked photo, in corrected-time order).
    moment_merges_wrong: owner boundaries inside a moment (two activities in one moment).
    moment_splits_wrong: moment starts that are not owner boundaries (one activity cut in two).
    activities_without_P: activities with no P photo (missed at delivery).
    groups_mixing_activities: 🧪 groups whose photos belong to two activities (should be 0).
    """
    from app.media import browse

    keys = _keys(conn)
    order = browse.time_order(conn)
    photos = sorted((a for a in keys if a in order), key=order.__getitem__)
    marked = {a for a in photos if keys[a] in boundaries}
    moment = {a: m for a, m in conn.execute("SELECT asset_id, moment_id FROM moment_assets")}
    picked = {a for (a,) in conn.execute("SELECT asset_id FROM decisions WHERE subject_id IS NULL AND flag = 'keep'")}
    activity: dict[int, int] = {}
    n = 0
    merges = splits = 0
    for i, a in enumerate(photos):
        if i and a in marked:
            n += 1
        activity[a] = n
        if i:
            same_moment = moment.get(a) == moment.get(photos[i - 1])
            merges += a in marked and same_moment
            splits += a not in marked and not same_moment
    out = {"activities": n + 1 if photos else 0, "boundaries_found": len(marked),
           "boundaries_not_in_this_event": len(boundaries) - len(marked),
           "moment_merges_wrong": merges, "moment_splits_wrong": splits,
           "activities_without_P": len({activity[a] for a in photos} - {activity[a] for a in picked if a in activity})}
    if grouping is not None:
        out["groups_mixing_activities"] = sum(1 for g in grouping.groups
                                              if len({activity.get(a) for a in g.members}) > 1)
    return out


def counts(event_folder: Path, logs: list[Path], reference: Path | None = None) -> dict:
    """``reference``: the event where the owner marked the activity boundaries (B) before any manual edit."""
    from app.media import similar
    from app.storage.project import CACHE_DIR

    conn = _open_ro(event_folder)
    try:
        q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        out: dict = {
            "photos": q("SELECT COUNT(*) FROM assets WHERE status = 'ok'"),
            "moments": q("SELECT COUNT(*) FROM moments"),
            "moments_without_P": len(similar.moments_without_pick(conn)),
            "P": q("SELECT COUNT(*) FROM decisions WHERE subject_id IS NULL AND flag = 'keep'"),
            "X": q("SELECT COUNT(*) FROM decisions WHERE subject_id IS NULL AND flag = 'reject'"),
            "experiment_on": similar.is_on(conn),
        }
        if out["experiment_on"]:
            grouping = similar.build(conn, similar.thumbnail_hashes(conn, event_folder / CACHE_DIR))
            fixes = similar.fixes(conn)
            out["groups"] = {
                "groups": len(grouping.groups),
                "groups_of_one": sum(1 for g in grouping.groups if g.size == 1),
                "lone_with_focus_warning": sum(1 for g in grouping.groups if g.warned_single),
                "suggested_photos": len(grouping.representatives()),
                "fixes_break": sum(1 for v in fixes.values() if v == "break"),
                "fixes_join": sum(1 for v in fixes.values() if v == "join"),
            }
        else:
            grouping = None
        if reference is not None:
            boundaries = owner_boundaries(reference)
            out["vs_owner_boundaries"] = against_boundaries(conn, boundaries, grouping)
            ref = _open_ro(reference)
            try:  # the reference event is never edited by hand: its moments are the app's own split
                out["app_split_vs_owner_boundaries"] = against_boundaries(ref, boundaries)
            finally:
                ref.close()
    finally:
        conn.close()
    kinds: Counter[str] = Counter()
    photos: Counter[str] = Counter()
    stamps: list[str] = []
    event_id = event_folder.name
    for path in logs:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE.match(line)
            if m and m.group(2) == event_id:
                kinds[m.group(3)] += 1
                photos[m.group(3)] += int(m.group(4))
                stamps.append(m.group(1))
    out["actions"] = sum(kinds.values())
    out["actions_by_kind"] = dict(sorted(kinds.items()))
    out["photos_by_kind"] = dict(sorted(photos.items()))
    out["manual_edits"] = {  # reported apart: moment edits and 🧪 group fixes (Ctrl+Z counted under 'undo')
        "moment_split": kinds["split"], "moment_merge": kinds["merge"], "moment_move": kinds["move"],
        "group_break": kinds["group_break"], "group_join": kinds["group_join"], "undo": kinds["undo"]}
    if stamps:
        first, last = min(stamps), max(stamps)
        fmt = "%Y-%m-%d %H:%M:%S"
        out["first_action"], out["last_action"] = first, last
        out["minutes_first_to_last"] = round((datetime.strptime(last, fmt) - datetime.strptime(first, fmt))
                                             .total_seconds() / 60, 1)
    return out


def run_cli(argv: list[str]) -> int:
    from app.branding import data_dir
    from app.media import event as ev

    ap = argparse.ArgumentParser(prog="KiraPick --media-counts")
    ap.add_argument("name", help="tên sự kiện, đúng như trong danh sách sự kiện")
    ap.add_argument("--out", help="ghi kết quả ra file JSON")
    ap.add_argument("--ranh-gioi", help="tên sự kiện nơi bạn đã đánh dấu ranh giới hoạt động (🏷, phím B)")
    args = ap.parse_args(argv)
    found = [e for e in ev.list_events() if e.name == args.name]
    if len(found) != 1:
        print(f"Không tìm thấy đúng một sự kiện tên \"{args.name}\" (tìm thấy {len(found)}).")
        return 2
    logs = sorted((data_dir() / "logs").glob("kirapick.log*"))
    reference = None
    if args.ranh_gioi:
        ref = [e for e in ev.list_events() if e.name == args.ranh_gioi]
        if len(ref) != 1:
            print(f"Không tìm thấy đúng một sự kiện tên \"{args.ranh_gioi}\" (tìm thấy {len(ref)}).")
            return 2
        reference = ref[0].folder
    result = counts(found[0].folder, logs, reference)
    text = json.dumps(result, ensure_ascii=False, indent=1)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0
