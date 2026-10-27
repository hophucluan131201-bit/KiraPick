"""Measure the app's person grouping against labelled looks (pairwise precision / recall).

    python scripts/calibration/evaluate_grouping.py snorlu_debug.zip            # or an extracted bundle folder
    python scripts/calibration/evaluate_grouping.py bundle --labels labels_aki_20261025

Works on a *copy* of the database: manual corrections are cleared so only the
automatic rules are measured. Outfit vectors from an older descriptor are
recomputed from the bundle's thumbnails, exactly as the app does. Each photo counts once, by its most prominent
main occurrence; photos missing from the labels are ignored.
Precision = of the photo pairs the app put together, how many really are one
look. Recall = of the real same-look pairs, how many the app put together.
"""

from __future__ import annotations

import argparse
import importlib
import itertools
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from app.identity.cluster import merge_suggestions, recluster  # noqa: E402
from app.storage.project import CACHE_DIR, DB_NAME, Project  # noqa: E402
from app.workers.analyze_job import refresh_outfits  # noqa: E402


def _number(relative_path: str) -> int | None:
    m = re.search(r"(\d+)\D*$", Path(relative_path).stem)
    return int(m.group(1)) if m else None


def evaluate(db_path: Path, looks: dict[str, list[int]]) -> dict:
    look_of = {n: look for look, numbers in looks.items() for n in numbers}
    project = Project.open(db_path.parent)
    try:
        conn = project.conn
        with project.transaction():
            conn.execute("UPDATE occurrences SET assignment = 'none', subject_id = NULL, excluded_subject_id = NULL")
            conn.execute("DELETE FROM subject_pairs")
            conn.execute("DELETE FROM subjects")
        refresh_outfits(project)
        recluster(project)
        best: dict[int, tuple[float, int | None, str]] = {}
        for r in conn.execute("""SELECT a.relative_path, o.prominence, o.subject_id, o.assignment
                                 FROM occurrences o JOIN assets a ON a.id = o.asset_id
                                 WHERE o.is_main = 1 AND a.status = 'ok'"""):
            n = _number(r["relative_path"])
            if n in look_of and (n not in best or r["prominence"] > best[n][0]):
                best[n] = (r["prominence"], r["subject_id"], r["assignment"])
        tp = fp = fn = 0
        wrong: list[tuple[int, int]] = []
        for x, y in itertools.combinations(sorted(best), 2):
            same = look_of[x] == look_of[y]
            together = best[x][1] is not None and best[x][1] == best[y][1]
            tp += same and together
            fp += (not same) and together
            fn += same and not together
            if together and not same:
                wrong.append((x, y))
        groups: dict[int | None, list[int]] = {}
        for n, (_, sid, _) in sorted(best.items()):
            groups.setdefault(sid, []).append(n)
        suggestions = merge_suggestions(conn)
        subject_look = {sid: {look_of[n] for n in ns} for sid, ns in groups.items() if sid is not None}
        useful = sum(1 for s in suggestions if subject_look.get(s.a, set()) & subject_look.get(s.b, set()))
        return {
            "photos": len(best), "looks": len({look_of[n] for n in best}),
            "precision": tp / (tp + fp) if tp + fp else 1.0, "recall": tp / (tp + fn) if tp + fn else 1.0,
            "wrong_pairs": wrong, "groups": groups,
            "suggested": sum(1 for v in best.values() if v[2] == "suggested"),
            "review": len(suggestions), "review_useful": useful,
        }
    finally:
        project.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="snorlu_debug.zip or the folder it was extracted to")
    parser.add_argument("--labels", default="labels_aki_20261025", help="module in scripts/calibration with LOOKS")
    args = parser.parse_args()
    looks = importlib.import_module(args.labels).LOOKS
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / DB_NAME
        thumbs = Path(tmp) / CACHE_DIR / "thumbs"
        thumbs.mkdir(parents=True)
        if args.source.suffix == ".zip":
            with zipfile.ZipFile(args.source) as zf:
                db.write_bytes(zf.read(DB_NAME))
                for name in zf.namelist():
                    if name.startswith("thumbs/") and name.endswith(".jpg"):
                        (thumbs / Path(name).name).write_bytes(zf.read(name))
        else:
            shutil.copyfile(args.source / DB_NAME, db)
            for f in (args.source / "thumbs").glob("*.jpg"):
                shutil.copyfile(f, thumbs / f.name)
        r = evaluate(db, looks)
    print(f"{r['photos']} labelled photos, {r['looks']} looks")
    print(f"precision {r['precision']:.3f}  recall {r['recall']:.3f}  "
          f"suggested(?) {r['suggested']}  review pairs {r['review']} ({r['review_useful']} really same look)")
    for x, y in r["wrong_pairs"]:
        print(f"  WRONG together: {x} + {y}")
    for sid, numbers in r["groups"].items():
        print(f"  {'(none)' if sid is None else sid:>6}: {numbers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
