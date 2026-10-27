"""Simulate a user correcting one half of a labelled shoot, then measure the learnt tuning on the other half.

python scripts/calibration/simulate_learning.py <extracted debug bundle> [labels module]
"""
import importlib, re, shutil, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1])); sys.path.insert(0, str(HERE))
from evaluate_grouping import evaluate, add_plus_vectors  # noqa: E402
from app.identity import actions  # noqa: E402
from app.identity.cluster import merge_suggestions, recluster, session_profile  # noqa: E402
from app.learning.store import LearningStore  # noqa: E402
from app.learning.teacher import Teacher  # noqa: E402
from app.learning.tuning import tune_from_store  # noqa: E402
from app.storage.project import CACHE_DIR, DB_NAME, Project  # noqa: E402
from app.workers.analyze_job import refresh_outfits  # noqa: E402

bundle = Path(sys.argv[1]); labels = sys.argv[2] if len(sys.argv) > 2 else "labels_aki_20261025"
looks = importlib.import_module(labels).LOOKS
look_of = {n: l for l, ns in looks.items() for n in ns}


def number(rel):
    m = re.search(r"(\d+)\D*$", Path(rel).stem)
    return int(m.group(1)) if m else None


def copy(keep) -> Path:
    tmp = Path(tempfile.mkdtemp())
    (tmp / CACHE_DIR / "thumbs").mkdir(parents=True)
    shutil.copyfile(bundle / DB_NAME, tmp / DB_NAME)
    for f in (bundle / "thumbs").glob("*.jpg"):
        shutil.copyfile(f, tmp / CACHE_DIR / "thumbs" / f.name)
    with Project.open(tmp) as p:
        refresh_outfits(p)
        add_plus_vectors(p)
        drop = [r["id"] for r in p.conn.execute("SELECT id, relative_path FROM assets") if not keep(number(r["relative_path"]))]
        with p.transaction() as c:
            c.executemany("DELETE FROM assets WHERE id = ?", [(d,) for d in drop])
    return tmp / DB_NAME


def look_of_asset(conn):
    return {r["id"]: look_of.get(number(r["relative_path"])) for r in conn.execute("SELECT id, relative_path FROM assets")}


def simulate_user(db: Path, store_dir: Path) -> Counter:
    done = Counter()
    with Project.open(db.parent) as p:
        conn = p.conn
        with p.transaction():
            conn.execute("UPDATE occurrences SET assignment = 'none', subject_id = NULL, excluded_subject_id = NULL")
            conn.execute("DELETE FROM subject_pairs")
            conn.execute("DELETE FROM subjects")
        recluster(p)
        teacher = Teacher(LearningStore(store_dir))
        lo = look_of_asset(conn)
        members = defaultdict(list)
        for r in conn.execute("SELECT DISTINCT subject_id, asset_id FROM occurrences WHERE subject_id IS NOT NULL AND is_main = 1"):
            members[r[0]].append(r[1])
        majority = {}
        for sid, assets in members.items():  # wrong photos out
            c = Counter(lo[a] for a in assets if lo[a])
            if not c:
                continue
            look, _ = c.most_common(1)[0]
            majority[sid] = look
            wrong = [a for a in assets if lo[a] and lo[a] != look]
            if wrong:
                with p.transaction() as tc:
                    teacher.removed(tc, sid, wrong)
                    actions.remove_photos_from_subject(tc, sid, wrong)
                done["remove"] += 1
        for s in merge_suggestions(conn):  # review queue: "different" answers
            if majority.get(s.a) and majority.get(s.b) and majority[s.a] != majority[s.b]:
                with p.transaction() as tc:
                    teacher.different(tc, s.a, s.b)
                    actions.mark_different(tc, s.a, s.b)
                done["different"] += 1
        by_look = defaultdict(list)
        for sid, look in majority.items():
            by_look[look].append(sid)
        for look, sids in by_look.items():  # split people merged
            for other in sids[1:]:
                with p.transaction() as tc:
                    teacher.merged(tc, sids[0], other)
                    actions.merge_subjects(tc, sids[0], other)
                done["merge"] += 1
        teacher.store.close()
    return done


numbers = sorted(n for n in look_of)
half = numbers[len(numbers) // 2]
for name, train, test in (("first half -> second", lambda n: n is not None and n < half, lambda n: n is not None and n >= half),
                          ("second half -> first", lambda n: n is not None and n >= half, lambda n: n is not None and n < half)):
    store_dir = Path(tempfile.mkdtemp())
    answers = simulate_user(copy(train), store_dir)
    test_db = copy(test)
    with Project.open(test_db.parent) as p:
        base = session_profile(p.conn)
    tuning = tune_from_store(store_dir, base)
    looks_test = {l: [n for n in ns if test(n)] for l, ns in looks.items()}
    r0 = evaluate(test_db, looks_test, plus=True)
    r1 = evaluate(test_db, looks_test, tune=tuning.apply, plus=True)
    print(f"{name}: answers {dict(answers)}; tuning face {tuning.face:+.2f} look {tuning.look:+.2f} applied={tuning.applied} "
          f"({tuning.reason or tuning.describe()})")
    print(f"   default  P={r0['precision']:.4f} R={r0['recall']:.4f}")
    print(f"   learnt   P={r1['precision']:.4f} R={r1['recall']:.4f}", flush=True)
