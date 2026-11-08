"""Numbers for the Media classification trial (REG-2): every user action in an event window is one local log line
``media action: event=<event id> kind=<kind> n=<photos>`` (no photo name, path or metadata), and

    KiraPick.exe --media-counts "<tên sự kiện>" [--out ket-qua.json]
    python -m app --media-counts "<tên sự kiện>" [--out ket-qua.json]          (from the source)

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


def counts(event_folder: Path, logs: list[Path]) -> dict:
    from app.media import similar
    from app.storage.project import CACHE_DIR, DB_NAME

    conn = sqlite3.connect(f"file:{event_folder / DB_NAME}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
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
    args = ap.parse_args(argv)
    found = [e for e in ev.list_events() if e.name == args.name]
    if len(found) != 1:
        print(f"Không tìm thấy đúng một sự kiện tên \"{args.name}\" (tìm thấy {len(found)}).")
        return 2
    logs = sorted((data_dir() / "logs").glob("kirapick.log*"))
    result = counts(found[0].folder, logs)
    text = json.dumps(result, ensure_ascii=False, indent=1)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0
