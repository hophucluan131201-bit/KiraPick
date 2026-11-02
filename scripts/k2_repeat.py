"""K2: run the P / X measurement tests N times each in fresh processes and summarise (numbers only).

    python scripts/k2_repeat.py [--runs 20] [--out k2]

Writes <out>/k2_raw.jsonl (one line per press), <out>/k2_summary.json, and prints one-line summaries. Measurement
only: nothing here changes the app or the perf thresholds.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ("tests/perf/test_k2_repeat.py::test_k2_compare_px", "tests/perf/test_k2_repeat.py::test_k2_grid_px")
LIMIT_MS = 100.0


def _pct(values: list[float], q: float) -> float:
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))] if v else float("nan")


def _stats(values: list[float]) -> dict:
    return {"n": len(values), "median": round(statistics.median(values), 2), "p95": round(_pct(values, 0.95), 2),
            "p99": round(_pct(values, 0.99), 2), "max": round(max(values), 2),
            "over_100": sum(1 for v in values if v > LIMIT_MS)}


def environment() -> dict:
    env = {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
           "processor": platform.processor(), "cpu_count": os.cpu_count(),
           "runner_image": os.environ.get("ImageVersion", ""), "runner_os": os.environ.get("RUNNER_OS", "")}
    try:
        import PySide6

        env["pyside6"] = PySide6.__version__
    except ImportError:
        pass
    return env


def summarise(rows: list[dict]) -> dict:
    out: dict = {}
    for test in sorted({r["test"] for r in rows}):
        rs = [r for r in rows if r["test"] == test]
        outliers = sorted((r for r in rs if r["total_ms"] > LIMIT_MS), key=lambda r: -r["total_ms"])
        dominant = Counter(max(r["parts"], key=r["parts"].get) for r in outliers)
        per_run = {}
        for run in sorted({r["run"] for r in rs}):
            totals = [r["total_ms"] for r in rs if r["run"] == run]
            per_run[str(run)] = {"median": round(statistics.median(totals), 2), "max": round(max(totals), 2),
                                 "over_100": sum(1 for v in totals if v > LIMIT_MS)}
        out[test] = {
            "runs": len(per_run), "presses": len(rs),
            "total_ms": _stats([r["total_ms"] for r in rs]),
            "handler_ms": _stats([r["handler_ms"] for r in rs]),
            "ui_ms": _stats([r["ui_ms"] for r in rs]),
            "gc_pause_ms": _stats([r["gc_ms"] for r in rs if r["gc_count"]] or [0.0]),
            "presses_with_gc": sum(1 for r in rs if r["gc_count"]),
            "presses_with_decode_callbacks": sum(1 for r in rs if r["decode_callbacks"]),
            "outliers_over_100": len(outliers),
            "outliers_with_gc": sum(1 for r in outliers if r["gc_count"]),
            "outliers_with_decode_callbacks": sum(1 for r in outliers if r["decode_callbacks"]),
            "outliers_first_press": sum(1 for r in outliers if r["press"] == 0),
            "outlier_dominant_part": dict(dominant),
            "worst_presses": [{k: r[k] for k in ("run", "press", "total_ms", "handler_ms", "ui_ms", "gc_ms",
                                                 "decode_callbacks", "parts")} for r in outliers[:5]],
            "per_run": per_run,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--out", default="k2")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "k2_raw.jsonl"
    raw.unlink(missing_ok=True)
    failures = 0
    for test in TESTS:
        for run in range(args.runs):
            env = {**os.environ, "KIRAPICK_K2_OUT": str(raw.resolve()), "KIRAPICK_K2_RUN": str(run),
                   "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "")}
            code = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "k2", test],
                                  cwd=ROOT, env=env, capture_output=True, text=True).returncode
            failures += code != 0
    rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = {"environment": environment(), "runs_per_test": args.runs, "process_failures": failures,
               "limit_ms": LIMIT_MS, "tests": summarise(rows)}
    (out / "k2_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for test, s in summary["tests"].items():
        print(f"K2 {test}: total {s['total_ms']} | handler {s['handler_ms']} | ui {s['ui_ms']} | "
              f"outliers {s['outliers_over_100']} (gc {s['outliers_with_gc']}, decode "
              f"{s['outliers_with_decode_callbacks']}, first {s['outliers_first_press']}, dominant "
              f"{s['outlier_dominant_part']})")
    print(f"K2 environment: {json.dumps(summary['environment'])} process_failures {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
