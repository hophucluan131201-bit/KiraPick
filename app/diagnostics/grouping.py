"""Grouping diagnostic (F3 Batch 0): how well automatic grouping matches the owner's labels.

    KiraPick.exe --diagnose-grouping "<photo folder>" report.json [labels.csv]

Read-only and offline:
- the session database (and the learning data) are COPIED byte for byte into a temporary folder; every
  computation runs on the copy. The originals are hashed before and after; the report states both.
- photo files are never opened. Network access is blocked for the whole run.
- the report holds numbers only: no file names, subject names, label texts, vectors or times of day.

Ground truth, per main occurrence (the people grouping considers):
- a subject named ``K<person>-<look>`` (e.g. ``K1-A``) labels its occurrences with that person and look;
  ``K<person>`` alone labels the person only (look unknown). Any other name — composite (``K1-A+K2-A``),
  ``?`` or a free name — is UNCERTAIN: never split into identities, excluded from accuracy metrics.
- optional ``labels.csv`` (columns ``occurrence_id`` or ``photo``, then ``person``, ``look``) gives
  occurrence-level labels and overrides the subject names; ``photo`` = relative path of the photo,
  meaning its most prominent main occurrence; ``?`` or empty person = uncertain.

Baseline: the automatic grouping before the owner's corrections, rebuilt on the copy by clearing every
correction (manual assignments, exclusions, "different" marks) and regrouping, once with the default
thresholds and once with the owner's current learnt tuning. The app keeps no record of the original
automatic result, so the rebuild is checked indirectly (determinism; agreement with occurrences the
owner never touched) and its limits are listed in the report.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.storage.project import DB_NAME, Project

REPORT_VERSION = 1
LABEL_RE = re.compile(r"^\s*K\s*(\d+)\s*(?:-\s*([A-Za-z]))?\s*$", re.IGNORECASE)
MAX_PER_CLUSTER = 300  # occurrences per cluster used for pair evidence (bounded time and memory)
TOP_M = 3


# ------------------------------------------------------------------ labels
@dataclass(frozen=True, slots=True)
class Label:
    person: str | None  # None = uncertain
    look: str | None  # None = look unknown (person may still be known)


UNCERTAIN = Label(None, None)


def parse_subject_label(name: str | None) -> Label:
    """``K1-A`` -> person 1, look 1-A; ``K1`` -> person 1; anything else (composite, ?, names) -> uncertain."""
    m = LABEL_RE.match(name or "")
    if not m:
        return UNCERTAIN
    person = str(int(m.group(1)))
    return Label(person, f"{person}-{m.group(2).upper()}" if m.group(2) else None)


def _csv_label(person: str, look: str) -> Label:
    person, look = (person or "").strip(), (look or "").strip()
    if not person or person == "?" or "+" in person or "+" in look:
        return UNCERTAIN
    return Label(person, f"{person}-{look.upper()}" if look and look != "?" else None)


def read_labels(conn, labels_csv: Path | None) -> tuple[dict[int, Label], dict[str, int]]:  # noqa: ANN001
    """Occurrence id -> label for the main occurrences grouping considers. Also returns counts."""
    rows = conn.execute(
        """SELECT o.id, o.asset_id, o.prominence, s.display_name FROM occurrences o
           JOIN assets a ON a.id = o.asset_id LEFT JOIN subjects s ON s.id = o.subject_id
           WHERE a.status = 'ok' AND (o.is_main = 1 OR o.assignment = 'manual')""").fetchall()
    labels = {r[0]: parse_subject_label(r[3]) for r in rows}
    stats = Counter(from_subject_names=sum(1 for v in labels.values() if v.person is not None),
                    no_subject=sum(1 for r in rows if r[3] is None and not conn.execute(
                        "SELECT subject_id FROM occurrences WHERE id = ?", (r[0],)).fetchone()[0]))
    if labels_csv is not None:
        by_photo: dict[str, int] = {}
        for occ_id, asset_id, prominence, _ in sorted(rows, key=lambda r: -r[2]):
            path = conn.execute("SELECT relative_path FROM assets WHERE id = ?", (asset_id,)).fetchone()[0]
            by_photo.setdefault(path.replace("\\", "/").casefold(), occ_id)
        with open(labels_csv, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                occ = None
                if (row.get("occurrence_id") or "").strip().isdigit():
                    occ = int(row["occurrence_id"])
                elif row.get("photo"):
                    occ = by_photo.get(row["photo"].strip().replace("\\", "/").casefold())
                if occ is None or occ not in labels:
                    stats["csv_rows_unmatched"] += 1
                    continue
                labels[occ] = _csv_label(row.get("person", ""), row.get("look", ""))
                stats["csv_rows_applied"] += 1
    stats["occurrences"] = len(labels)
    stats["person_labelled"] = sum(1 for v in labels.values() if v.person is not None)
    stats["look_labelled"] = sum(1 for v in labels.values() if v.look is not None)
    stats["uncertain"] = stats["occurrences"] - stats["person_labelled"]
    return labels, dict(stats)


# ----------------------------------------------------------------- metrics
def grouping_metrics(truth: dict[int, str], pred: dict[int, object]) -> dict:
    """Accuracy of a predicted partition against true labels, over the items present in ``truth``.

    ``pred`` maps each item to its cluster; items missing from ``pred`` count as clusters of their own.
    """
    items = sorted(truth)
    if not items:
        return {"items": 0}
    cluster = {i: pred.get(i, ("alone", i)) for i in items}
    n = Counter((truth[i], cluster[i]) for i in items)
    size_c = Counter(cluster.values())
    size_t = Counter(truth.values())
    pairs = lambda k: k * (k - 1) // 2  # noqa: E731
    tp = sum(pairs(v) for v in n.values())
    pp = sum(pairs(v) for v in size_c.values())
    tt = sum(pairs(v) for v in size_t.values())
    bp = sum(n[(truth[i], cluster[i])] / size_c[cluster[i]] for i in items) / len(items)
    br = sum(n[(truth[i], cluster[i])] / size_t[truth[i]] for i in items) / len(items)
    labels_in = defaultdict(set)
    for (t, c) in n:
        labels_in[c].add(t)
    clusters_of = defaultdict(set)
    for (t, c) in n:
        clusters_of[t].add(c)
    majority = {c: max((cnt, t) for (t, cc), cnt in n.items() if cc == c)[1] for c in size_c}
    moves = sum(size_c[c] - n[(majority[c], c)] for c in size_c)  # photos to move out of impure clusters
    merges = sum(max(0, k - 1) for k in Counter(majority.values()).values())  # clusters to merge after that
    return {
        "items": len(items),
        "true_groups": len(size_t),
        "clusters": len(size_c),
        "pairwise_precision": round(tp / pp, 4) if pp else None,
        "pairwise_recall": round(tp / tt, 4) if tt else None,
        "bcubed_precision": round(bp, 4),
        "bcubed_recall": round(br, 4),
        "bcubed_f1": round(2 * bp * br / (bp + br), 4) if bp + br else 0.0,
        "false_merge_clusters": sum(1 for c in labels_in if len(labels_in[c]) > 1),
        "false_merge_items": moves,
        "false_split_groups": sum(1 for t in clusters_of if len(clusters_of[t]) > 1),
        "false_split_extra_clusters": sum(len(v) - 1 for v in clusters_of.values()),
        "manual_corrections": {"photo_moves": moves, "merges": merges, "total": moves + merges},
    }


def level_metrics(labels: dict[int, Label], pred: dict[int, object]) -> dict:
    person = {i: v.person for i, v in labels.items() if v.person is not None}
    look = {i: v.look for i, v in labels.items() if v.look is not None}
    return {"person": grouping_metrics(person, pred), "look": grouping_metrics(look, pred)}


# ---------------------------------------------------------------- baseline
def partition(conn) -> dict[int, object]:  # noqa: ANN001
    """Occurrence id -> subject id (grouped, auto or suggested); unassigned occurrences are left out."""
    return {r[0]: r[1] for r in conn.execute("SELECT id, subject_id FROM occurrences WHERE subject_id IS NOT NULL")}


def clear_corrections(conn) -> dict[str, int]:  # noqa: ANN001
    """On the COPY only: forget every correction so regrouping gives the automatic result."""
    counts = {
        "manual_occurrences": conn.execute("SELECT COUNT(*) FROM occurrences WHERE assignment = 'manual'").fetchone()[0],
        "excluded_marks": conn.execute("SELECT COUNT(*) FROM occurrences WHERE excluded_subject_id IS NOT NULL").fetchone()[0],
        "different_marks": conn.execute("SELECT COUNT(*) FROM subject_pairs").fetchone()[0],
    }
    conn.execute("""UPDATE occurrences SET subject_id = NULL, assignment = 'none', confidence = NULL,
                    excluded_subject_id = NULL""")
    conn.execute("DELETE FROM subject_pairs")
    return counts


def rebuild(project: Project, tune) -> dict[int, object]:  # noqa: ANN001
    from app.identity.cluster import recluster

    with project.transaction() as conn:
        clear_corrections(conn)
    recluster(project, tune)
    return partition(project.conn)


def same_partition(a: dict[int, object], b: dict[int, object]) -> bool:
    def canon(p: dict[int, object]) -> set[frozenset[int]]:
        groups: dict[object, set[int]] = defaultdict(set)
        for i, c in p.items():
            groups[c].add(i)
        return {frozenset(g) for g in groups.values()}
    return canon(a) == canon(b)


def pair_agreement(a: dict[int, object], b: dict[int, object], items: set[int]) -> float | None:
    """Share of item pairs on which two partitions agree (together / apart)."""
    ids = sorted(i for i in items)
    agree = total = 0
    for x, y in itertools.combinations(ids, 2):
        sa = x in a and y in a and a[x] == a[y]
        sb = x in b and y in b and b[x] == b[y]
        agree += sa == sb
        total += 1
    return round(agree / total, 4) if total else None


# ---------------------------------------------------------- pair evidence
def _summary(values: list[float]) -> dict | None:
    if not values:
        return None
    v = np.array(values, dtype=float)
    return {"n": len(v), "min": round(float(v.min()), 3), "p25": round(float(np.percentile(v, 25)), 3),
            "median": round(float(np.median(v)), 3), "p75": round(float(np.percentile(v, 75)), 3),
            "max": round(float(v.max()), 3)}


def pair_evidence(project: Project, labels: dict[int, Label], pred: dict[int, object]) -> dict:
    """Evidence between predicted clusters, by what the labels say they are (hypotheses H1–H5)."""
    from app.identity.cluster import (
        load_occurrences,
        look_similarity,
        merge_suggestions,
        session_profile,
    )

    conn = project.conn
    p = session_profile(conn)
    occs = {o.id: o for o in load_occurrences(conn, p)}
    members: dict[object, list[int]] = defaultdict(list)
    for i, c in pred.items():
        if i in occs:
            members[c].append(i)

    def majority(c: object, attr: str) -> str | None:
        votes = Counter(getattr(labels[i], attr) for i in members[c] if i in labels and getattr(labels[i], attr))
        if not votes:
            return None
        top, cnt = votes.most_common(1)[0]
        return top if cnt * 2 > sum(votes.values()) else None  # a clear majority only

    feats: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    category: dict[frozenset, str] = {}
    clusters = [c for c in members if majority(c, "person")]
    for a, b in itertools.combinations(clusters, 2):
        pa, pb = majority(a, "person"), majority(b, "person")
        la, lb = majority(a, "look"), majority(b, "look")
        if pa != pb:
            cat = "different_person"
        elif la and lb and la == lb:
            cat = "same_look_split"  # H2–H4
        elif la and lb:
            cat = "same_person_other_look"  # H1
        else:
            cat = "same_person_look_unknown"
        category[frozenset((a, b))] = cat
        A, B = members[a][:MAX_PER_CLUSTER], members[b][:MAX_PER_CLUSTER]
        fa = [occs[i].face for i in A if occs[i].face is not None]
        fb = [occs[i].face for i in B if occs[i].face is not None]
        f = feats[cat]
        if fa and fb:
            sims = (np.stack(fa) @ np.stack(fb).T).ravel()
            f["face_top3_mean"].append(float(np.sort(sims)[-TOP_M:].mean()))
            f["face_max"].append(float(sims.max()))
        else:
            f["no_face_side"].append(1.0)
        looks = [s for x in A for y in B if (s := look_similarity(occs[x], occs[y], p)) is not None]
        if looks:
            f["look_median"].append(float(np.median(looks)))
        ta = sorted(occs[i].time for i in A if occs[i].time is not None)
        tb = sorted(occs[i].time for i in B if occs[i].time is not None)
        if ta and tb:
            tb_arr = np.array(tb)
            pos = np.searchsorted(tb_arr, ta)
            gaps = [abs(tb_arr[min(q, len(tb_arr) - 1)] - t) for q, t in zip(pos, ta)]
            gaps += [abs(tb_arr[q - 1] - t) for q, t in zip(pos, ta) if q > 0]
            f["min_gap_s"].append(float(min(gaps)))
            seq = [c for _, c in sorted([(t, 0) for t in ta] + [(t, 1) for t in tb])]
            f["interleave_switches"].append(float(sum(1 for x, y in itertools.pairwise(seq) if x != y) - 1))
            f["beyond_window"].append(float(min(gaps) > p.window_s))
        assets_a = {occs[i].asset_id for i in members[a]}
        f["co_occurrence_photos"].append(float(len(assets_a & {occs[i].asset_id for i in members[b]})))
    out = {cat: {k: _summary(v) for k, v in d.items()} for cat, d in feats.items()}
    counts = Counter(category.values())
    # H5: what the review queue would ask about on the rebuilt automatic grouping
    asked = Counter()
    for s in merge_suggestions(conn, limit=10_000):
        asked[category.get(frozenset((s.a, s.b)), "unlabelled")] += 1
    return {"profile": p.name, "window_s": p.window_s, "cluster_pairs": dict(counts), "features": out,
            "review_queue_asks": dict(asked)}


# ------------------------------------------------------------------ driver
def _hash_files(paths: list[Path]) -> dict[str, str]:
    out = {}
    for path in paths:
        if path.is_file():
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[path.name] = h.hexdigest()
    return out


def _db_files(folder: Path, name: str) -> list[Path]:
    return [folder / name, folder / f"{name}-wal"]  # -shm is rebuilt by SQLite; never copied


def _correction_counts(conn) -> dict[str, int]:  # noqa: ANN001
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {"manual_occurrences": q("SELECT COUNT(*) FROM occurrences WHERE assignment = 'manual'"),
            "excluded_marks": q("SELECT COUNT(*) FROM occurrences WHERE excluded_subject_id IS NOT NULL"),
            "different_marks": q("SELECT COUNT(*) FROM subject_pairs")}


def diagnose(session_folder: Path, learning_folder: Path | None, labels_csv: Path | None = None) -> dict:
    """Run the diagnostic on copies of the session (and learning) databases; returns the numeric report."""
    from app.identity.cluster import session_profile
    from app.learning.tuning import tune_from_store

    report: dict = {"report_version": REPORT_VERSION, "read_only": {}, "limitations": []}
    sources = [f for f in _db_files(session_folder, DB_NAME) if f.is_file()]
    if not (session_folder / DB_NAME).is_file():
        raise FileNotFoundError("no KiraPick session for this folder (open it in KiraPick first)")
    learning_sources = [f for f in _db_files(learning_folder, "learning.db") if f.is_file()] if learning_folder else []
    before = _hash_files(sources + learning_sources)
    report["read_only"]["wal_present"] = (session_folder / f"{DB_NAME}-wal").is_file()
    if report["read_only"]["wal_present"]:
        report["limitations"].append("the session has a write-ahead log: close KiraPick before running, "
                                     "or the copy may miss the newest changes")
    with tempfile.TemporaryDirectory(prefix="kirapick-diagnose-") as tmp:
        def fresh_copy(name: str, files: list[Path]) -> Path:
            folder = Path(tmp) / name
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir()
            for src in files:  # byte copies; the originals are only read
                shutil.copyfile(src, folder / src.name)
            return folder

        learn = fresh_copy("learning", learning_sources) if learning_sources else None
        with Project.open(fresh_copy("current", sources)) as project:
            conn = project.conn
            labels, report["labels"] = read_labels(conn, labels_csv)
            current = partition(conn)
            report["corrections_in_session"] = _correction_counts(conn)
            untouched = {r[0] for r in conn.execute(
                "SELECT id FROM occurrences WHERE assignment = 'auto' AND excluded_subject_id IS NULL")}
            profile = session_profile(conn)
        tuning = tune_from_store(learn, profile)
        runs: dict[str, dict[int, object]] = {}
        for name in ("default", "default_repeat", "tuned"):
            if name == "tuned" and not tuning.applied:
                continue
            with Project.open(fresh_copy(name, sources)) as project:
                runs[name] = rebuild(project, tuning.apply if name == "tuned" else None)
                if name == "default":
                    report["evidence"] = pair_evidence(project, labels, runs[name])
    after = _hash_files(sources + learning_sources)
    default = runs["default"]
    report["current_state"] = level_metrics(labels, current)  # the owner-corrected state (sanity check)
    report["tuning"] = {"applied": tuning.applied, "face_shift": tuning.face, "look_shift": tuning.look}
    report["baseline"] = {
        "profile": profile.name,
        "deterministic": same_partition(default, runs["default_repeat"]),
        "agreement_with_untouched_auto_pairs": pair_agreement(default, current, untouched),
        "untouched_auto_occurrences": len(untouched),
        "default": level_metrics(labels, default),
    }
    if "tuned" in runs:
        report["baseline"]["tuned"] = level_metrics(labels, runs["tuned"])
        report["baseline"]["tuned_equals_default"] = same_partition(default, runs["tuned"])
    report["read_only"].update({"files_hashed": len(before), "unchanged": before == after})
    report["limitations"] += [
        ("the original automatic grouping is not stored by the app; the baseline is rebuilt from the current "
         "occurrences with this build's rules"),
        "if photos were re-analysed after the owner's corrections, occurrences may differ from the first run",
        "the learnt tuning at the time of the first grouping is unknown; both default and current tuning are reported",
        "occurrence-level truth comes from subject names unless labels.csv gives it per occurrence",
    ]
    return report


def run_cli(args: list[str]) -> int:
    """``--diagnose-grouping <photo folder> <report.json> [labels.csv]``: writes the report, network blocked."""
    import json
    import traceback

    from app.branding import data_dir
    from app.selftest import _block_network
    from app.storage.sessions import session_dir

    if len(args) < 2:
        print("usage: KiraPick.exe --diagnose-grouping <photo folder> <report.json> [labels.csv]")
        return 2
    folder = Path(args[0].strip().strip('"'))
    report_path = Path(args[1].strip().strip('"'))
    labels = Path(args[2].strip().strip('"')) if len(args) > 2 else None
    attempts: list[str] = []
    _block_network(attempts)
    try:
        report = diagnose(session_dir(data_dir() / "sessions", folder), data_dir() / "learning", labels)
        report["ok"] = report["read_only"]["unchanged"] and not attempts
    except Exception as exc:  # noqa: BLE001 - the report must always be written
        report = {"report_version": REPORT_VERSION, "ok": False, "error": f"{type(exc).__name__}: {exc}",
                  "traceback": traceback.format_exc()[-2000:]}
    report["network_attempts"] = len(attempts)
    from app import __version__

    report["app_version"] = __version__
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if report.get("ok") else 1
