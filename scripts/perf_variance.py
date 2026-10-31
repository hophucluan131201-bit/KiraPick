"""Summarise repeated performance runs (beta readiness BR-02): for each measurement of each test, the median, p95 and
worst across the runs written to a KIRAPICK_PERF_OUT file, one GitHub notice per test. Development tool only.

    python scripts/perf_variance.py variance.jsonl
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

KEYS = {
    "compare_large_session": ["enter_ms", "px_median_ms", "px_p95_ms", "px_worst_ms", "hover_sweep_worst_block_ms"],
    "sustained_culling": ["median_ms", "p95_ms", "worst_ms", "gc_pause_worst_ms"],
    "long_session": ["gc_pause_median_ms", "gc_pause_worst_ms", "gc_runs", "seconds"],
}


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def summarise(lines: list[dict]) -> dict[str, dict[str, tuple[int, float, float, float]]]:
    runs: dict[str, list[dict]] = defaultdict(list)
    for line in lines:
        name = line.get("name")
        if name in KEYS and (name != "sustained_culling" or line.get("photos") == 10000):
            runs[name].append(line)
    out: dict[str, dict[str, tuple[int, float, float, float]]] = {}
    for name, rows in runs.items():
        out[name] = {}
        for key in KEYS[name]:
            values = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
            if values:
                out[name][key] = (len(values), statistics.median(values), _p95(values), max(values))
    return out


def main() -> int:
    path = Path(sys.argv[1])
    lines = [json.loads(t) for t in path.read_text(encoding="utf-8").splitlines() if t.strip()] if path.exists() else []
    for name, stats in summarise(lines).items():
        parts = [f"{key} n={n} median {med:.1f} p95 {p95:.1f} worst {worst:.1f}"
                 for key, (n, med, p95, worst) in stats.items()]
        print(f"::notice title=variance {name}::" + " | ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
