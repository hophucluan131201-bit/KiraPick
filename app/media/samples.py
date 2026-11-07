"""'Dán nhãn mẫu' and the offline scorer (Media spec v6 §11, plan Mốc 1 M9).

The owner labels 100-150 real event photos in the app (``sample_labels``, apart from the working labels). The scorer
compares them with what the analysis answered (``media_analysis.measures_json``: the AI's own shot size and focus
warnings, kept even when the user later changed a label) and reports numbers only: no file name, no path, no person.

- Two sets split BY MOMENT (near-identical photos never land in both): ~40 % tuning set (only used to suggest
  thresholds, never scored), ~60 % scoring set. The split is fixed by the moment's first photo id.
- Every rate carries its sample size ("41/47 (87 %)"); below 15 samples: "chưa đủ mẫu", no pass / fail.
- Mốc 1 scores shot size, Out nét, Trật nét and moment boundaries; content is "không áp dụng" (no AI content labels
  while CLIP is pending).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter

from app.media import labels as lb
from app.media import moments as mo
from app.media.browse import time_order
from app.storage.project import Project, utc_now

MIN_SAMPLES = 15
TUNING_SHARE = 40  # percent of moments
GROUPS = {"shot": set(lb.SHOT), "content": set(lb.CONTENT), "focus": {"net", "out_net", "trat_net"},
          "boundary": {"start"}, "skip": {"1"}}
FOCUS_NAMES = {"net": "Nét", "out_net": "Out nét", "trat_net": "Trật nét"}
TARGETS = {"shot_accuracy": 0.85, "shot_unknown_max": 0.20, "out_net_catch": 0.90, "out_net_false_max": 0.10,
           "trat_net_catch": 0.60, "trat_net_false_max": 0.10}


# ------------------------------------------------------------------------------------------------ labelling
def set_sample(conn: sqlite3.Connection, asset_ids: list[int], grp: str, value: str) -> None:
    """One reference answer on these photos. Shot size and focus hold one value per photo; content several."""
    if value not in GROUPS.get(grp, ()):
        raise ValueError(f"nhãn mẫu không hợp lệ: {grp}/{value}")
    now = utc_now()
    with conn:
        for a in asset_ids:
            if grp in ("shot", "focus"):
                conn.execute("DELETE FROM sample_labels WHERE asset_id = ? AND grp = ?", (a, grp))
            conn.execute("INSERT OR REPLACE INTO sample_labels (asset_id, grp, value, labelled_at) VALUES (?, ?, ?, ?)",
                         (a, grp, value, now))


def toggle_sample(conn: sqlite3.Connection, asset_ids: list[int], grp: str, value: str) -> bool:
    """Set the answer, or take it away when every photo already has it. Returns True when set."""
    marks = ",".join("?" * len(asset_ids))
    have = {r[0] for r in conn.execute(f"SELECT asset_id FROM sample_labels WHERE grp = ? AND value = ? "  # noqa: S608
                                       f"AND asset_id IN ({marks})", (grp, value, *asset_ids))}
    if asset_ids and have == set(asset_ids):
        with conn:
            conn.execute(f"DELETE FROM sample_labels WHERE grp = ? AND value = ? AND asset_id IN ({marks})",  # noqa: S608
                         (grp, value, *asset_ids))
        return False
    set_sample(conn, asset_ids, grp, value)
    return True


def samples_of(conn: sqlite3.Connection, asset_id: int) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for grp, value in conn.execute("SELECT grp, value FROM sample_labels WHERE asset_id = ? ORDER BY grp, value",
                                   (asset_id,)):
        out.setdefault(grp, []).append(value)
    return out


def sample_text(conn: sqlite3.Connection, asset_id: int) -> str:
    s = samples_of(conn, asset_id)
    if "skip" in s:
        return "Mẫu: chưa đánh giá"
    parts = [lb.SHOT[v] for v in s.get("shot", [])] + [FOCUS_NAMES[v] for v in s.get("focus", [])] + \
        [lb.CONTENT[v] for v in s.get("content", [])] + (["▶ bắt đầu khoảnh khắc"] if "boundary" in s else [])
    return "Mẫu: " + (", ".join(parts) if parts else "—")


# ------------------------------------------------------------------------------------------------ scoring
def _rate(n: int, of: int) -> dict:
    if of < MIN_SAMPLES:
        return {"n": n, "of": of, "rate": None, "text": f"{n}/{of} — chưa đủ mẫu"}
    r = n / of
    return {"n": n, "of": of, "rate": round(r, 4), "text": f"{n}/{of} ({round(r * 100)} %)"}


def _verdict(rate: dict, target: float, at_most: bool = False) -> str:
    if rate["rate"] is None:
        return "chưa đủ mẫu"
    ok = rate["rate"] <= target if at_most else rate["rate"] >= target
    return "đạt" if ok else "chưa đạt"


def split_sets(conn: sqlite3.Connection) -> tuple[set[int], set[int]]:
    """(tuning, scoring) photo ids, whole moments on one side; photos without a moment go to scoring."""
    tuning: set[int] = set()
    scoring: set[int] = set()
    in_moment: set[int] = set()
    for m in mo.moments(conn):
        if not m.assets:
            continue
        in_moment.update(m.assets)
        h = int(hashlib.sha256(str(min(m.assets)).encode()).hexdigest()[:8], 16) % 100
        (tuning if h < TUNING_SHARE else scoring).update(m.assets)
    scoring.update(r[0] for r in conn.execute("SELECT id FROM assets WHERE status = 'ok'") if r[0] not in in_moment)
    return tuning, scoring


def _ai(conn: sqlite3.Connection) -> dict[int, dict]:
    return {a: json.loads(m) for a, m in conn.execute(
        "SELECT asset_id, measures_json FROM media_analysis WHERE status = 'done' AND measures_json IS NOT NULL")}


def _truth(conn: sqlite3.Connection) -> tuple[dict[str, dict[int, set[str]]], set[int]]:
    truth: dict[str, dict[int, set[str]]] = {}
    skipped = set()
    for a, grp, value in conn.execute("SELECT asset_id, grp, value FROM sample_labels"):
        if grp == "skip":
            skipped.add(a)
        else:
            truth.setdefault(grp, {}).setdefault(a, set()).add(value)
    return truth, skipped


def _shot_report(truth: dict[int, set[str]], ai: dict[int, dict], ids: set[int]) -> dict:
    confusion: Counter = Counter()
    correct = decided = unknown = with_people = 0
    for a, values in truth.items():
        if a not in ids or a not in ai or "shot_ai" not in ai[a]:
            continue
        true = next(iter(values))
        guess = ai[a]["shot_ai"]
        with_people += 1
        confusion[f"{true}->{guess}"] += 1
        if guess == lb.UNKNOWN:
            unknown += 1
        else:
            decided += 1
            correct += guess == true
    accuracy, unknown_rate = _rate(correct, decided), _rate(unknown, with_people)
    return {"accuracy": accuracy, "accuracy_verdict": _verdict(accuracy, TARGETS["shot_accuracy"]),
            "unknown_rate": unknown_rate,
            "unknown_verdict": _verdict(unknown_rate, TARGETS["shot_unknown_max"], at_most=True),
            "confusion": dict(sorted(confusion.items()))}


def _focus_report(truth: dict[int, set[str]], ai: dict[int, dict], ids: set[int], warning: str) -> dict:
    caught = positives = false_alarms = negatives = unmeasured = 0
    for a, values in truth.items():
        if a not in ids or a not in ai or "focus_ai" not in ai[a]:
            continue
        flagged = ai[a]["focus_ai"]
        if flagged == "?":
            unmeasured += 1
            continue
        true = next(iter(values))
        if true == warning:
            positives += 1
            caught += warning in flagged
        else:
            negatives += 1
            false_alarms += warning in flagged
    catch, false = _rate(caught, positives), _rate(false_alarms, negatives)
    return {"catch": catch, "catch_verdict": _verdict(catch, TARGETS[f"{warning}_catch"]),
            "false_alarm": false, "false_alarm_verdict": _verdict(false, TARGETS[f"{warning}_false_max"], at_most=True),
            "not_measured": unmeasured}


def _boundary_report(conn: sqlite3.Connection, truth: dict[int, set[str]], skipped: set[int]) -> dict:
    """Over the stretch of photos the sampler went through (first to last photo with any sample label)."""
    labelled = {r[0] for r in conn.execute("SELECT DISTINCT asset_id FROM sample_labels")}
    if not truth:
        return {"applies": False, "text": "chưa có nhãn ranh giới"}
    order = time_order(conn)
    span = sorted((a for a in order if order[a] >= min(order[x] for x in labelled if x in order)
                   and order[a] <= max(order[x] for x in labelled if x in order)), key=order.get)
    span = [a for a in span if a not in skipped]
    starts_true = {a for a in span if a in truth}
    starts_ai = {min(m.assets, key=lambda x: order.get(x, 0)) for m in mo.moments(conn) if m.assets}
    starts_ai &= set(span[1:])  # the first photo of the stretch starts nothing we can judge
    starts_true &= set(span[1:])
    return {"applies": True, "photos": len(span), "true_boundaries": len(starts_true),
            "correct": len(starts_true & starts_ai), "extra": len(starts_ai - starts_true),
            "missing": len(starts_true - starts_ai)}


def _suggest_shot_thresholds(truth: dict[int, set[str]], ai: dict[int, dict], ids: set[int]) -> dict:
    """On the TUNING set: the close / wide face-ratio thresholds that agree best with the reference (not applied)."""
    rows = [(ai[a]["shot"]["face_h"], next(iter(v))) for a, v in truth.items()
            if a in ids and a in ai and (ai[a].get("shot") or {}).get("face_h") is not None]
    if len(rows) < MIN_SAMPLES:
        return {"photos": len(rows), "text": "chưa đủ mẫu để đề xuất ngưỡng"}
    best = None
    for close in [x / 100 for x in range(6, 31)]:
        for wide in [x / 1000 for x in range(10, 81, 5)]:
            if wide >= close:
                continue
            hits = sum((("can" if f > close else "trung" if f >= wide else "toan") == t) for f, t in rows)
            if best is None or hits > best[0]:
                best = (hits, close, wide)
    hits, close, wide = best  # type: ignore[misc]
    return {"photos": len(rows), "close_face": close, "wide_face": wide, "agree": _rate(hits, len(rows))["text"],
            "note": "đề xuất từ tập chỉnh ngưỡng, chưa áp dụng"}


def score(project: Project) -> dict:
    conn = project.conn
    truth, skipped = _truth(conn)
    ai = _ai(conn)
    tuning, scoring = split_sets(conn)
    tuning -= skipped
    scoring -= skipped
    labelled = {a for g in truth.values() for a in g}
    return {
        "kind": "kirapick-media-score",
        "version": 1,
        "samples": {"photos_labelled": len(labelled), "skipped": len(skipped),
                    "tuning_set_photos": len(tuning & labelled), "scoring_set_photos": len(scoring & labelled),
                    "analysed": len(ai)},
        "shot": _shot_report(truth.get("shot", {}), ai, scoring),
        "out_net": _focus_report(truth.get("focus", {}), ai, scoring, "out_net"),
        "trat_net": _focus_report(truth.get("focus", {}), ai, scoring, "trat_net"),
        "moments": _boundary_report(conn, truth.get("boundary", {}), skipped),
        "content": {"applies": False, "text": "không áp dụng: chưa có nhãn nội dung bằng AI (CLIP chưa được duyệt)",
                    "labelled": {k: sum(1 for v in truth.get("content", {}).values() if k in v) for k in lb.CONTENT}},
        "suggested_thresholds": {"shot": _suggest_shot_thresholds(truth.get("shot", {}), ai, tuning)},
        "sample_counts": {
            "shot": {k: sum(1 for v in truth.get("shot", {}).values() if k in v) for k in lb.SHOT},
            "focus": {k: sum(1 for v in truth.get("focus", {}).values() if k in v) for k in FOCUS_NAMES},
            "enough": MIN_SAMPLES},
    }


def run_cli(args: list[str]) -> int:
    """``--media-score <event id | event name> [--out report.json]``: read-only, network blocked, numbers only."""
    from pathlib import Path

    from app.media import event as ev
    from app.selftest import _block_network

    args = list(args)
    out = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            print("--out needs a file path")
            return 2
        out = Path(args[i + 1].strip().strip('"'))
        del args[i:i + 2]
    if not args:
        print('usage: KiraPick.exe --media-score "<event id or name>" [--out report.json]')
        return 2
    wanted = args[0].strip().strip('"')
    attempts: list[str] = []
    _block_network(attempts)
    match = [e for e in ev.list_events() if wanted in (e.id, e.name)]
    if len(match) != 1:
        print("không tìm thấy sự kiện" if not match else "có nhiều sự kiện cùng tên: dùng mã sự kiện")
        return 2
    import sqlite3 as _sqlite

    from app.storage.project import DB_NAME

    db = match[0].folder / DB_NAME
    conn = _sqlite.connect(f"file:{db}?mode=ro", uri=True)  # read-only: scoring never changes the event
    conn.row_factory = _sqlite.Row
    try:
        report = score(_ReadOnly(conn))
    finally:
        conn.close()
    report["network_attempts"] = len(attempts)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if out is not None:
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0


class _ReadOnly:
    """The bits of Project the scorer reads, over a read-only connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
