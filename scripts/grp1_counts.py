"""GRP-1 trial numbers (LIC-1 plan §11.5): how much manual grouping one real shoot needed. Read-only, no network.

    python scripts/grp1_counts.py "<photo folder>" [--since "2026-11-07 09:00"]

Reads the session of that folder (%LOCALAPPDATA%\\KiraPick\\sessions\\…, opened read-only) and the local log
(%LOCALAPPDATA%\\KiraPick\\logs\\kirapick.log*). Prints numbers only: photos, photos where a person was found,
photos that could not be grouped by hand because no person was found, people, photos grouped by hand, and the
grouping actions counted from the log lines 'people action: kind=…' (written since --since, if given). The time
spent is measured by the owner (stopwatch). Never prints a name, a file name or a path of a photo.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.branding import data_dir  # noqa: E402
from app.storage.sessions import session_dir  # noqa: E402

LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*people action: kind=(\w+)")


def counts(db: Path, logs: list[Path], since: str | None) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        out = {
            "photos": q("SELECT COUNT(*) FROM assets WHERE status = 'ok'"),
            "photos_with_a_person": q("SELECT COUNT(DISTINCT asset_id) FROM occurrences"),
            "people": q("SELECT COUNT(DISTINCT subject_id) FROM occurrences WHERE subject_id IS NOT NULL"),
            "photos_grouped_by_hand": q("SELECT COUNT(DISTINCT asset_id) FROM occurrences WHERE assignment = 'manual'"),
        }
    finally:
        conn.close()
    out["photos_blocked_no_person"] = out["photos"] - out["photos_with_a_person"]
    kinds: Counter[str] = Counter()
    for log in logs:
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE.match(line)
            if m and (since is None or m.group(1) >= since):
                kinds[m.group(2)] += 1
    out["grouping_actions"] = sum(kinds.values())
    out["grouping_actions_by_kind"] = dict(sorted(kinds.items()))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--since", help="count log lines from this local time on, e.g. '2026-11-07 09:00'")
    args = ap.parse_args(argv)
    db = next(session_dir(data_dir() / "sessions", args.folder.resolve()).glob("*.db"), None)
    if db is None:
        print("Chưa có phiên cho thư mục này (mở thư mục trong KiraPick trước).")
        return 1
    logs = sorted((data_dir() / "logs").glob("kirapick.log*"))
    for key, value in counts(db, logs, args.since).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
