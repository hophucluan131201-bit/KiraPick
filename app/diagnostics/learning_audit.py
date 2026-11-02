"""F3 P0-B: numbers-only audit of the learnt identity tuning (diagnostic only; never changes learning).

Runs on a private snapshot copy of learning.db. Reports what was learnt, which cue versions count, the cost grid
tune() searches, its cross-validation by fold, which answers' links change between default and learnt thresholds,
and "possible contamination": "same" answers (merge / assign) whose pairs look clearly different (median look below
the review look level). Low look similarity is only a hint — a costume change, but also lighting or angle; it is
never proof. The tuning is then re-run without those answers, on the copy only, to show their effect.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from app.learning.store import RESERVATION_VERSION

KINDS = ("merge", "different", "remove", "assign")
SAME_KINDS = ("merge", "assign")


def _shift_key(f: float, g: float) -> str:
    sign = lambda v: ("p" if v >= 0 else "m") + f"{round(abs(v) * 100):03d}"  # noqa: E731
    return f"face_{sign(f)}_look_{sign(g)}"


def answer_kinds(conn: sqlite3.Connection) -> dict[int, str]:
    """answer id (as identity_examples numbers it, pre-v5 rows included) -> kind."""
    out: dict[int, str] = {}
    old: dict[tuple, int] = {}
    for answer, day, kind, same in conn.execute(
            "SELECT answer_id, created_on, kind, same FROM identity_feedback WHERE outfit_version != ? "
            "ORDER BY id DESC LIMIT 20000", (RESERVATION_VERSION,)):
        if answer is None:
            answer = old.setdefault((day, kind, same), -1 - len(old))
        out[int(answer)] = kind if kind in KINDS else "other"
    return out


def _counts(conn: sqlite3.Connection) -> dict:
    from app.ai.identity_plus import ARCFACE_VERSION, BODY_VERSION
    from app.identity.features import OUTFIT_VERSION
    from app.workers.analyze_job import FACE_VECTOR_VERSION

    out: dict = {"pre_v5_rows": conn.execute("SELECT COUNT(*) FROM identity_feedback WHERE answer_id IS NULL")
                 .fetchone()[0],
                 "undo_operation_reservations": conn.execute(
                     "SELECT COUNT(*) FROM identity_feedback WHERE outfit_version = ?", (RESERVATION_VERSION,)).fetchone()[0]}
    rows = conn.execute("""SELECT kind, same, COUNT(*), COUNT(DISTINCT answer_id),
                                  SUM(face_version = ?), SUM(outfit_version = ?), SUM(arc_version = ?),
                                  SUM(body_version = ?)
                           FROM identity_feedback WHERE outfit_version != ? GROUP BY kind, same""",
                        (FACE_VECTOR_VERSION, OUTFIT_VERSION, ARCFACE_VERSION, BODY_VERSION, RESERVATION_VERSION)
                        ).fetchall()
    by = {}
    for kind, same, pairs, answers, face_cur, outfit_cur, arc_cur, body_cur in rows:
        key = f"{kind if kind in KINDS else 'other'}_{'same' if same else 'different'}"
        cur = by.setdefault(key, {"pairs": 0, "answers": 0, "pairs_current_face": 0, "pairs_current_look": 0,
                                  "pairs_current_arcface": 0, "pairs_current_body": 0})
        for k, v in (("pairs", pairs), ("answers", answers), ("pairs_current_face", face_cur),
                     ("pairs_current_look", outfit_cur), ("pairs_current_arcface", arc_cur),
                     ("pairs_current_body", body_cur)):
            cur[k] += int(v or 0)
    out["by_kind"] = by
    return out


def _reason_code(d, base, tuning_mod) -> str:  # noqa: ANN001
    if d is None:
        return "no_usable_examples"
    same = len(np.unique(d.answer[d.same]))
    diff = len(np.unique(d.answer[~d.same]))
    if same < tuning_mod.MIN_ANSWERS or diff < tuning_mod.MIN_ANSWERS:
        return "too_few_answers"
    if tuning_mod._best(d, base, np.ones(len(d.same), bool)) == (0.0, 0.0):
        return "defaults_best"
    return "cross_validation"


def _cv(d, base, tuning_mod) -> dict:  # noqa: ANN001
    """tune()'s cross-validation, fold by fold (same folds)."""
    answers = np.unique(d.answer)
    folds = np.arange(len(answers)) % min(tuning_mod.FOLDS, len(answers))
    fold_of = dict(zip(answers.tolist(), folds.tolist(), strict=True))
    fold = np.array([fold_of[a] for a in d.answer.tolist()])
    out, tuned_total, default_total = {}, 0.0, 0.0
    for k in np.unique(folds):
        train, test = fold != k, fold == k
        if not test.any() or not train.any():
            continue
        f, g = tuning_mod._best(d, base, train)
        tuned = tuning_mod._cost(d, base.shifted(f, g), test)[0]
        default = tuning_mod._cost(d, base, test)[0]
        tuned_total += tuned
        default_total += default
        out[f"fold_{int(k)}"] = {"face_shift": f, "look_shift": g, "tuned_cost": round(tuned, 4),
                                 "default_cost": round(default, 4)}
    out["tuned_total"] = round(tuned_total, 4)
    out["default_total"] = round(default_total, 4)
    return out


def _look_per_answer(d) -> dict[int, float]:  # noqa: ANN001
    looks: dict[int, list[float]] = defaultdict(list)
    for a, v in zip(d.answer.tolist(), d.look.tolist(), strict=True):
        if not np.isnan(v):
            looks[a].append(v)
    return {a: float(np.median(v)) for a, v in looks.items()}


def audit(learning_folder: Path | None, base) -> tuple[dict, object | None]:  # noqa: ANN001
    """(numbers-only audit, Tuning learnt WITHOUT the possibly contaminated answers or None)."""
    from app.learning import tuning as tuning_mod
    from app.learning.store import LearningStore

    if learning_folder is None or not (learning_folder / "learning.db").is_file():
        return {"available": False}, None
    store = LearningStore(learning_folder)  # a private snapshot copy: opening it may upgrade the copy only
    try:
        conn = store.conn
        examples = store.identity_examples()
        kinds = answer_kinds(conn)
        report: dict = {"available": True, "counts": _counts(conn)}
        d = tuning_mod._arrays(examples, base)
        learnt = tuning_mod.tune(examples, base)
        report["tuning"] = {"applied": learnt.applied, "face_shift": learnt.face, "look_shift": learnt.look,
                            "same_answers": learnt.same_answers, "different_answers": learnt.different_answers,
                            "reason_code": _reason_code(d, base, tuning_mod),
                            "usable_pairs": 0 if d is None else len(d.same)}
        if d is None:
            return report, None
        everything = np.ones(len(d.same), bool)
        grid = {}
        for f in tuning_mod._SHIFTS:
            for g in tuning_mod._SHIFTS:
                cost, false = tuning_mod._cost(d, base.shifted(float(f), float(g)), everything)
                grid[_shift_key(float(f), float(g))] = {"cost": round(cost, 4), "false_links": round(false, 4)}
        report["cost_grid"] = grid
        report["cross_validation"] = _cv(d, base, tuning_mod)
        # Which answers change between default and learnt thresholds (an answer changes if any pair flips).
        changed: Counter = Counter()
        if learnt.applied:
            before = tuning_mod._linked(d, base, everything)
            after = tuning_mod._linked(d, learnt.apply(base), everything)
            flipped = {a for a, x, y in zip(d.answer.tolist(), before.tolist(), after.tolist(), strict=True) if x != y}
            same_of = dict(zip(d.answer.tolist(), d.same.tolist(), strict=True))
            for a in flipped:
                changed[f"{kinds.get(a, 'other')}_{'same' if same_of[a] else 'different'}"] += 1
        report["answers_changed_by_learnt_tuning"] = dict(changed)
        # Possible contamination: "same" answers whose pairs look clearly different.
        look_of = _look_per_answer(d)
        same_answers = {a for a, s in zip(d.answer.tolist(), d.same.tolist(), strict=True) if s}
        suspect = {a for a in same_answers if kinds.get(a) in SAME_KINDS and a in look_of
                   and look_of[a] < base.review_look}
        report["possible_contamination"] = {
            "hint_only": True,
            "look_threshold": base.review_look,
            "same_answers_with_look": sum(1 for a in same_answers if a in look_of),
            "same_answers_below_threshold": len(suspect),
            "by_kind": dict(Counter(kinds.get(a, "other") for a in suspect)),
        }
        kept = [e for e in examples if e.answer not in suspect]
        filtered = tuning_mod.tune(kept, base)
        d_kept = tuning_mod._arrays(kept, base)

        def evidence(data) -> dict:  # noqa: ANN001
            if data is None:
                return {"usable_pairs": 0, "same_answers": 0, "different_answers": 0}
            return {"usable_pairs": len(data.same), "same_answers": len(np.unique(data.answer[data.same])),
                    "different_answers": len(np.unique(data.answer[~data.same]))}

        # Why the learnt shift can stay the same without those answers: their cost (missed links, weighted) is the
        # same at the default and at the learnt thresholds, so they cannot have pulled the choice either way.
        excluded = np.isin(d.answer, list(suspect)) if suspect else np.zeros(len(d.same), bool)
        learnt_t = learnt.apply(base)
        cost_default = tuning_mod._cost(d, base, excluded)[0] if excluded.any() else 0.0
        cost_learnt = tuning_mod._cost(d, learnt_t, excluded)[0] if excluded.any() else 0.0
        report["filtered_tuning"] = {
            "applied": filtered.applied, "face_shift": filtered.face, "look_shift": filtered.look,
            "reason_code": _reason_code(d_kept, base, tuning_mod),
            "excluded_answers": len(suspect),
            "evidence_before": evidence(d), "evidence_after": evidence(d_kept),
            "same_shift_as_learnt": (filtered.face, filtered.look) == (learnt.face, learnt.look),
            "excluded_cost_at_default": round(cost_default, 4),
            "excluded_cost_at_learnt": round(cost_learnt, 4),
            "excluded_answers_cost_neutral": abs(cost_default - cost_learnt) < 1e-9,
        }
        return report, filtered
    finally:
        store.close()
