"""Benchmark of the bottom-bar counts (app.storage.stats.counts) on synthetic sessions.

    python scripts/bench/stats_bench.py

Builds sessions of 1,000 / 5,000 / 10,000 photos in a temporary folder: half are RAW+JPEG pairs,
30 % kept, 10 % rejected, 1 % unreadable. Prints the median of 7 runs and SQLite's query plans.
"""

from __future__ import annotations

import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.storage.project import Project  # noqa: E402
from app.storage.stats import SHOWN_PHOTO_SQL, counts  # noqa: E402


def build(project: Project, photos: int) -> None:
    conn = project.conn
    conn.execute("BEGIN")
    src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')").lastrowid
    for i in range(photos):
        status = "error" if i % 100 == 0 else "ok"
        if i % 2:
            g = conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid
            files = [(f"{i}.NEF", "raw", 30_000_000), (f"{i}.JPG", "raster", 10_000_000)]
        else:
            g, files = None, [(f"{i}.JPG", "raster", 10_000_000)]
        first = None
        for name, kind, size in files:
            aid = conn.execute(
                "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
                "quick_hash, status, added_at, updated_at, pair_group_id) VALUES (?, ?, 'x', ?, 'full', ?, 1, ?, ?, "
                "'t', 't', ?)", (src, name, kind, size, name, status, g)).lastrowid
            first = first or aid
        flag = "keep" if i % 10 < 3 else "reject" if i % 10 == 3 else None
        if flag:
            conn.execute("INSERT INTO decisions (asset_id, subject_id, flag, updated_at) VALUES (?, NULL, ?, 't')",
                         (first, flag))
    conn.execute("COMMIT")


def main() -> None:
    for n in (1_000, 5_000, 10_000):
        with tempfile.TemporaryDirectory() as tmp, Project.create(Path(tmp) / "s", "bench") as project:
            build(project, n)
            times = []
            for _ in range(7):
                t = time.perf_counter()
                c = counts(project.conn, include_pairs=True)
                times.append(time.perf_counter() - t)
            print(f"{n:>6} photos: counts() median {statistics.median(times) * 1000:.1f} ms, "
                  f"max {max(times) * 1000:.1f} ms  ({c.total} shown, {c.keep} kept, {c.keep_bytes / 1e9:.1f} GB)")
            if n == 10_000:
                plan = project.conn.execute(
                    f"EXPLAIN QUERY PLAN SELECT COUNT(*) FROM assets a LEFT JOIN decisions d "
                    f"ON d.asset_id = a.id AND d.subject_id IS NULL WHERE {SHOWN_PHOTO_SQL}").fetchall()
                print("query plan (counts):", " | ".join(r[3] for r in plan))


if __name__ == "__main__":
    main()
