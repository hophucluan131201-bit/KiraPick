"""``kirapick-raw-probe``: read-only compatibility report for a photo folder.

    python -m app.ingest.cli D:\\Photos\\Event --verify --json report.json

Never writes next to the photos; ``--json`` writes only where you point it.
Source files are hashed before and after to prove they were not modified
(``--verify-untouched``).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.errors import ImageReadError
from app.ingest.fingerprint import full_sha256
from app.ingest.formats import MediaKind
from app.ingest.preview import load_full_resolution, load_image
from app.ingest.scanner import scan_folder
from app.ingest.validation import check_embedded_orientation


@dataclass(slots=True)
class FileResult:
    path: str
    extension: str
    support: str
    camera: str | None = None
    grid: str | None = None
    analysis: str | None = None
    full_res: str | None = None
    metadata_complete: bool | None = None
    orientation_check: str | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    error: str | None = None


def _timed(result: FileResult, key: str, fn: Any) -> Any:
    start = time.perf_counter()
    value = fn()
    result.timings_ms[key] = round((time.perf_counter() - start) * 1000, 1)
    return value


def probe_file(path: Path, rel: str, ext: str, support: str, *, full: bool, verify: bool) -> FileResult:
    result = FileResult(rel, ext, support)
    try:
        grid = _timed(result, "grid", lambda: load_image(path, max_long_side=320, min_long_side=320, with_metadata=True))
        result.grid = f"{grid.source.value} {grid.native_size[0]}x{grid.native_size[1]}"
        meta = grid.metadata
        if meta is not None:
            result.camera = " ".join(filter(None, [meta.make, meta.model])) or None
            result.metadata_complete = meta.is_complete()
        analysis = _timed(result, "analysis", lambda: load_image(path, max_long_side=1600, min_long_side=1600))
        result.analysis = f"{analysis.source.value} {analysis.image.width}x{analysis.image.height}"
        if full:
            loaded = _timed(result, "full_res", lambda: load_full_resolution(path))
            result.full_res = f"{loaded.source.value} {loaded.native_size[0]}x{loaded.native_size[1]}"
        if verify and support != "raster":
            check = _timed(result, "orientation_check", lambda: check_embedded_orientation(path))
            result.orientation_check = "no preview" if check is None else ("pass" if check.passed else f"FAIL {check.correlations}")
    except ImageReadError as exc:
        result.error = str(exc)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kirapick-raw-probe", description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--full", action="store_true", help="also load full resolution (demosaics when needed; slow)")
    parser.add_argument("--verify", action="store_true", help="cross-check embedded preview orientation against LibRaw")
    parser.add_argument("--verify-untouched", action="store_true", help="SHA-256 every file before/after (reads files twice)")
    parser.add_argument("--limit", type=int, default=0, help="probe at most N files")
    parser.add_argument("--json", type=Path, help="write the full report to this JSON file")
    args = parser.parse_args(argv)

    report = scan_folder(args.folder)
    entries = report.entries[: args.limit or None]
    print(f"Scanned {len(report.entries)} supported files; skipped {report.skipped_links} links; "
          f"unsupported extensions: {dict(report.unsupported_extensions) or '-'}")

    before = {e.relative_path: full_sha256(e.path) for e in entries} if args.verify_untouched else {}
    results = []
    for i, entry in enumerate(entries, 1):
        support = "raster" if entry.format.kind is MediaKind.RASTER else entry.format.level.value
        r = probe_file(entry.path, entry.relative_path, entry.format.extension, support, full=args.full, verify=args.verify)
        results.append(r)
        status = r.error or f"{r.camera or '?'} | grid {r.grid} | {r.timings_ms.get('grid')} ms" + (
            f" | orient {r.orientation_check}" if r.orientation_check else "")
        print(f"[{i}/{len(entries)}] {r.path}: {status}")

    untouched = None
    if args.verify_untouched:
        changed = [e.relative_path for e in entries if full_sha256(e.path) != before[e.relative_path]]
        untouched = not changed
        print("Source files unchanged (SHA-256):", "YES" if untouched else f"NO -> {changed}")

    by_ext: dict[str, Counter[str]] = {}
    for r in results:
        by_ext.setdefault(r.extension, Counter())["error" if r.error else "ok"] += 1
    grid_ms = [r.timings_ms["grid"] for r in results if "grid" in r.timings_ms and not r.error]
    print("\nPer extension:", {k: dict(v) for k, v in sorted(by_ext.items())})
    if grid_ms:
        print(f"Grid thumbnail time: median {statistics.median(grid_ms):.0f} ms, max {max(grid_ms):.0f} ms "
              f"(includes metadata; measured on this machine)")

    if args.json:
        payload = {
            "folder": str(report.root),
            "unsupported_extensions": dict(report.unsupported_extensions),
            "skipped_links": report.skipped_links,
            "sources_unchanged": untouched,
            "files": [asdict(r) for r in results],
        }
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Report written to", args.json)
    return 1 if any(r.error for r in results) or untouched is False else 0


if __name__ == "__main__":
    sys.exit(main())
