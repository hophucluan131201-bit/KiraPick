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


class LabelsError(ValueError):
    """labels.csv cannot be used (missing columns)."""


class SnapshotError(RuntimeError):
    """The session could not be read as a consistent snapshot."""


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
        for occ_id, asset_id, _prominence, _ in sorted(rows, key=lambda r: -r[2]):
            path = conn.execute("SELECT relative_path FROM assets WHERE id = ?", (asset_id,)).fetchone()[0]
            by_photo.setdefault(path.replace("\\", "/").casefold(), occ_id)
        given: dict[int, set[Label]] = defaultdict(set)
        with open(labels_csv, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            columns = {c.strip().casefold() for c in reader.fieldnames or []}
            if "person" not in columns or not columns & {"occurrence_id", "photo"}:
                raise LabelsError("labels.csv needs the columns person and occurrence_id or photo")
            for raw in reader:
                row = {(k or "").strip().casefold(): (v or "").strip() for k, v in raw.items()}
                ident, photo = row.get("occurrence_id", ""), row.get("photo", "")
                if ident and not ident.isdigit():
                    stats["csv_rows_invalid"] += 1
                    continue
                if not ident and not photo:
                    stats["csv_rows_invalid"] += 1
                    continue
                occ = int(ident) if ident else by_photo.get(photo.replace("\\", "/").casefold())
                if occ is None or occ not in labels:
                    stats["csv_rows_unknown"] += 1
                    continue
                label = _csv_label(row.get("person", ""), row.get("look", ""))
                if label in given[occ]:
                    stats["csv_rows_duplicate"] += 1
                given[occ].add(label)
                stats["csv_rows_applied"] += 1
        for occ, found in given.items():
            if len(found) == 1:
                labels[occ] = next(iter(found))
            else:  # contradicting rows: the occurrence becomes uncertain, never guessed
                labels[occ] = UNCERTAIN
                stats["csv_conflicting_occurrences"] += 1
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


LIMIT_CHANGED = ("the session or learning data changed during the run (KiraPick open?): the report used one "
                 "consistent snapshot; close KiraPick and run again")
LIMITS_ALWAYS = [
    ("reconstructed_baseline is rebuilt now from the current occurrences with this build's rules; the app does not "
     "store its original automatic grouping, so it is not verified historical output"),
    "if photos were re-analysed after the owner's corrections, occurrences may differ from the first run",
    "the learnt tuning at the time of the first grouping is unknown; both default and current tuning are reported",
    "occurrence-level truth comes from subject names unless labels.csv gives it per occurrence",
]
_LIMITATION_TEXTS = {LIMIT_CHANGED, *LIMITS_ALWAYS}


# ----------------------------------------------------------------- privacy
TEXT_KEYS = {"profile", "app_version", "error", "snapshot_method", "learning_snapshot_method", "reason_code"}  # fixed texts written by this module
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def check_numbers_only(report: dict) -> None:
    """Refuse a report that could carry a file name, a subject name, a label or a vector.

    Keys must be this module's snake_case vocabulary; values must be numbers, booleans or None, except
    TEXT_KEYS and the fixed ``limitations`` sentences; lists hold numbers only (no vectors: at most 16)."""
    def walk(value: object, key: str) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(k, str) or not KEY_RE.match(k):
                    raise ValueError(f"unexpected report key {k!r}")
                walk(v, k)
        elif isinstance(value, list):
            if key == "limitations":
                if not all(isinstance(x, str) and x in _LIMITATION_TEXTS for x in value):
                    raise ValueError("unexpected limitation text")
                return
            if len(value) > 16 or not all(isinstance(x, (int, float)) for x in value):
                raise ValueError(f"unexpected list under {key!r}")
        elif isinstance(value, str):
            if key not in TEXT_KEYS:
                raise ValueError(f"unexpected text under {key!r}")
        elif value is not None and not isinstance(value, (int, float, bool)):
            raise ValueError(f"unexpected value type under {key!r}")
    walk(report, "")


# ------------------------------------------------------------------ driver
def _hash_files(paths: list[Path]) -> dict[str, str]:
    """SHA-256 per existing file (read-only open). A file another process locks (e.g. a live -shm on Windows)
    is recorded as "locked" instead of failing."""
    out = {}
    for path in paths:
        if path.is_file():
            h = hashlib.sha256()
            try:
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                out[path.name] = h.hexdigest()
            except PermissionError:
                out[path.name] = "locked"
    return out


def _copy_read_only(src: Path, dst: Path) -> None:
    """Byte copy that asks only for read access on ``src`` (no attribute/metadata copy, unlike shutil.copy*)."""
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        shutil.copyfileobj(fin, fout, 1 << 20)


def _busy(folder: Path, name: str) -> bool:
    """A -shm or -journal file exists: the database is open (or was not closed cleanly). Checked by name only."""
    return any((folder / f"{name}{s}").exists() for s in ("-shm", "-journal"))


SETTLE_S = 0.5  # pause before the second check: a writer active during the copy shows up as a change


def _sqlite_state(src: Path) -> dict[str, str]:
    """SHA-256 of every SQLite file of ``src`` that exists (.db, -wal, -shm, -journal)."""
    return _hash_files([src.with_name(src.name + s) for s in ("", "-wal", "-shm", "-journal")])


def snapshot(src: Path, dest: Path) -> str:
    """A copy of the database ``src`` at ``dest`` taken without ever opening ``src`` with SQLite. Fail-closed.

    Refused when the database may be in use or changes while it is read:
    - a ``-shm`` or ``-journal`` file exists (KiraPick open, or it did not close cleanly — opening and closing
      KiraPick once clears it);
    - any SQLite file of ``src`` (.db, -wal, -shm, -journal) changes, appears or disappears between the check
      before the copy and two checks after it (the second after SETTLE_S).
    Otherwise .db (+ -wal) are copied byte for byte into a private folder and only that copy is opened; SQLite's
    recovery of the copy keeps exactly the committed transactions. The source folder is only read (works when it
    is read-only); no file there is created, changed or deleted."""
    import sqlite3
    import time
    from contextlib import closing

    if _busy(src.parent, src.name):
        raise SnapshotError("KiraPick seems to be open (or did not close cleanly): close it, or open and close it "
                            "once, then run again")
    before = _sqlite_state(src)
    private = dest.parent / "source-copy"
    private.mkdir()
    try:
        for name in before:
            _copy_read_only(src.with_name(name), private / name)
        copied = _hash_files([private / name for name in before])
        after = _sqlite_state(src)
        time.sleep(SETTLE_S)
        settled = _sqlite_state(src)
        if not (before == after == settled == copied):
            raise SnapshotError("the session changed while it was read: close KiraPick and run again")
        with closing(sqlite3.connect(private / src.name)) as source, closing(sqlite3.connect(dest)) as target:
            source.backup(target)
    except (sqlite3.Error, OSError) as exc:
        raise SnapshotError(f"could not read the session: close KiraPick and run again ({type(exc).__name__})") \
            from exc
    finally:
        shutil.rmtree(private, ignore_errors=True)
    return "file_copy_verified"


def _correction_counts(conn) -> dict[str, int]:  # noqa: ANN001
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {"manual_occurrences": q("SELECT COUNT(*) FROM occurrences WHERE assignment = 'manual'"),
            "excluded_marks": q("SELECT COUNT(*) FROM occurrences WHERE excluded_subject_id IS NOT NULL"),
            "different_marks": q("SELECT COUNT(*) FROM subject_pairs")}


def diagnose(session_folder: Path, learning_folder: Path | None, labels_csv: Path | None = None,
             cooccurrence_list: Path | None = None) -> dict:
    """Run the diagnostic on copies of the session (and learning) databases; returns the numeric report.

    ``cooccurrence_list``: also write the LOCAL list of photos where one person label appears twice (file names
    and subject names, for the owner only; never part of the returned report)."""
    from app.diagnostics import cooccurrence, learning_audit
    from app.identity.cluster import session_profile
    from app.learning.tuning import tune_from_store

    report: dict = {"report_version": REPORT_VERSION, "read_only": {}, "limitations": []}
    sources = [session_folder / (DB_NAME + s) for s in ("", "-wal", "-shm", "-journal")]
    if not (session_folder / DB_NAME).is_file():
        raise FileNotFoundError("no KiraPick session for this folder (open it in KiraPick first)")
    for folder, name in ((session_folder, DB_NAME), (learning_folder, "learning.db")):
        if folder is not None and _busy(folder, name):  # before reading anything: fail closed
            raise SnapshotError("KiraPick seems to be open (or did not close cleanly): close it, or open and close "
                                "it once, then run again")
    learning_sources = ([learning_folder / ("learning.db" + s) for s in ("", "-wal", "-shm", "-journal")]
                        if learning_folder else [])
    def listing() -> set[str]:  # every file next to the sources, so a newly created file also counts as a change
        folders = [session_folder] + ([learning_folder] if learning_folder and learning_folder.is_dir() else [])
        return {f"{i}/{f.name}" for i, d in enumerate(folders) for f in d.iterdir() if f.is_file()}

    files_before = listing()
    before = _hash_files(sources + learning_sources)
    report["read_only"]["wal_present"] = (session_folder / f"{DB_NAME}-wal").is_file()
    with tempfile.TemporaryDirectory(prefix="kirapick-diagnose-") as tmp:
        snap = Path(tmp) / "snapshot"
        snap.mkdir()
        report["read_only"]["snapshot_method"] = snapshot(session_folder / DB_NAME, snap / DB_NAME)  # one point in time
        learn = None
        if learning_folder and (learning_folder / "learning.db").is_file():
            learn = Path(tmp) / "learning"
            learn.mkdir()
            report["read_only"]["learning_snapshot_method"] = snapshot(learning_folder / "learning.db",
                                                                       learn / "learning.db")

        def fresh_copy(name: str, files: list[Path]) -> Path:
            folder = Path(tmp) / name
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir()
            for src in files:
                shutil.copyfile(src, folder / src.name)
            return folder

        sources_snap = [snap / DB_NAME]
        with Project.open(fresh_copy("current", sources_snap)) as project:
            conn = project.conn
            labels, report["labels"] = read_labels(conn, labels_csv)
            current = partition(conn)
            report["corrections_in_session"] = _correction_counts(conn)
            untouched = {r[0] for r in conn.execute(
                "SELECT id FROM occurrences WHERE assignment = 'auto' AND excluded_subject_id IS NULL")}
            profile = session_profile(conn)
            pairs = cooccurrence.find_pairs(conn, labels)
            report["cooccurrence"] = cooccurrence.summary(pairs)
            if cooccurrence_list is not None:
                cooccurrence.write_local_list(conn, pairs, cooccurrence_list)
            report["cooccurrence"]["local_list_written"] = cooccurrence_list is not None
        tuning = tune_from_store(learn, profile)
        report["learning_audit"], filtered = learning_audit.audit(learn, profile)
        runs: dict[str, dict[int, object]] = {}
        tunes = {"default": None, "default_repeat": None,
                 "tuned": tuning.apply if tuning.applied else None,
                 "filtered": filtered.apply if filtered is not None and filtered.applied else None}
        for name, tune in tunes.items():
            if name in ("tuned", "filtered") and tune is None:
                continue
            with Project.open(fresh_copy(name, sources_snap)) as project:
                runs[name] = rebuild(project, tune)
                if name == "default":
                    report["evidence"] = pair_evidence(project, labels, runs[name])
    after = _hash_files(sources + learning_sources)
    files_after = listing()
    default = runs["default"]
    report["current_state"] = level_metrics(labels, current)  # the owner-corrected state (sanity check)
    report["tuning"] = {"applied": tuning.applied, "face_shift": tuning.face, "look_shift": tuning.look}
    report["reconstructed_baseline"] = {
        "verified_historical_output": False,  # rebuilt now from the snapshot; the app keeps no original result
        "profile": profile.name,
        "deterministic": same_partition(default, runs["default_repeat"]),
        "agreement_with_untouched_auto_pairs": pair_agreement(default, current, untouched),
        "untouched_auto_occurrences": len(untouched),
        "default": level_metrics(labels, default),
    }
    if "tuned" in runs:
        report["reconstructed_baseline"]["tuned"] = level_metrics(labels, runs["tuned"])
        report["reconstructed_baseline"]["tuned_equals_default"] = same_partition(default, runs["tuned"])
    # Learnt tuning without the "possibly contaminated" answers (copy only; nothing is removed from learning).
    report["reconstructed_baseline"]["filtered_learning_applied"] = "filtered" in runs
    if "filtered" in runs:
        report["reconstructed_baseline"]["filtered_learning"] = level_metrics(labels, runs["filtered"])
    report["read_only"].update({"files_hashed": len(before), "no_new_files": files_before == files_after,
                                "unchanged": before == after and files_before == files_after})
    if not report["read_only"]["unchanged"]:
        report["limitations"].append(LIMIT_CHANGED)
    report["limitations"] += LIMITS_ALWAYS
    check_numbers_only(report)
    return report


def run_cli(args: list[str]) -> int:
    """``--diagnose-grouping <photo folder> <report.json> [labels.csv]``: writes the report, network blocked."""
    import json
    import traceback

    from app.branding import data_dir
    from app.selftest import _block_network
    from app.storage.sessions import session_dir

    args = list(args)
    listing = None
    if "--cooccurrence-list" in args:  # explicit opt-in: the only output with file and subject names (local only)
        i = args.index("--cooccurrence-list")
        if i + 1 >= len(args):
            print("--cooccurrence-list needs a file path")
            return 2
        listing = Path(args[i + 1].strip().strip('"'))
        del args[i:i + 2]
    if len(args) < 2:
        print("usage: KiraPick.exe --diagnose-grouping <photo folder> <report.json> [labels.csv] "
              "[--cooccurrence-list <local list.csv>]")
        return 2
    folder = Path(args[0].strip().strip('"'))
    report_path = Path(args[1].strip().strip('"'))
    labels = Path(args[2].strip().strip('"')) if len(args) > 2 else None
    if listing is not None and listing.resolve() == report_path.resolve():
        print("the co-occurrence list must be a different file from the report")
        return 2
    attempts: list[str] = []
    _block_network(attempts)
    try:
        report = diagnose(session_dir(data_dir() / "sessions", folder), data_dir() / "learning", labels, listing)
        report["ok"] = report["read_only"]["unchanged"] and not attempts
    except Exception as exc:  # noqa: BLE001 - the report must always be written
        # Own errors carry fixed texts; anything else: the type only (a message may hold a path or a name).
        # The full traceback goes to a separate local file the owner does not need to share.
        known = isinstance(exc, (LabelsError, SnapshotError)) or (
            isinstance(exc, FileNotFoundError) and str(exc).startswith("no KiraPick session"))
        report = {"report_version": REPORT_VERSION, "ok": False,
                  "error": f"{type(exc).__name__}: {exc}" if known else type(exc).__name__}
        try:
            report_path.with_name(report_path.name + ".traceback.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
    report["network_attempts"] = len(attempts)
    from app import __version__

    report["app_version"] = __version__
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if report.get("ok") else 1
