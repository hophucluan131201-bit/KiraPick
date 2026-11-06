"""Report B (design §12): which model weights an installation / build folder contains, and what Media may do with
each. Also the build gate: a weight Media needs at this milestone without a fallback, and not cleared, blocks it.

    python scripts/media_model_report.py [--models-dir DIR] [--milestone N] [--json report.json]

Exit 0: fine; 1: a file in the folder is not in the manifest; 2: the milestone is blocked by an uncleared weight.
Numbers and names only; never reads photos, never uses the network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.models import ModelRegistry, default_models_dir, load_manifest, sha256_of  # noqa: E402
from app.media.models import load_policy  # noqa: E402


def build_report(models_dir: Path, milestone: int) -> dict:
    specs = load_manifest()
    policy = load_policy()
    registry = ModelRegistry(models_dir, specs)
    by_file = {s.file: s for s in specs.values()}
    rows, unknown = [], []
    for path in sorted(p for p in models_dir.glob("*") if p.is_file()):
        if path.name.endswith(".sha256"):
            continue
        spec = by_file.get(path.name)
        if spec is None:
            unknown.append(path.name)
            continue
        media = policy.models.get(spec.id)
        role = ("never in Media" if spec.id in policy.never
                else f"Media: {media.status}" if media is not None else "outside Media")
        rows.append({"id": spec.id, "file": path.name, "bytes": path.stat().st_size, "sha256": sha256_of(path),
                     "verified": registry.status(spec.id).state.value, "license": spec.license, "media": role})
    blocking = policy.blocking(milestone)
    return {"models_dir": str(models_dir), "milestone": milestone, "files": rows, "not_in_manifest": unknown,
            "media_loadable": policy.loadable_ids(), "blocking": blocking}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", type=Path, default=None)
    ap.add_argument("--milestone", type=int, default=0)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    report = build_report(args.models_dir or default_models_dir(), args.milestone)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in report["files"]:
        print(f"{r['id']:<24} {r['verified']:<8} {r['media']:<32} {r['license']}")
    if report["not_in_manifest"]:
        print("NOT IN MANIFEST: " + ", ".join(report["not_in_manifest"]))
        return 1
    if report["blocking"]:
        print(f"BLOCKED at milestone {args.milestone} by uncleared weights: " + ", ".join(report["blocking"]))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
