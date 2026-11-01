"""CI only: a synthetic KiraPick session for a synthetic photo folder, to test the PACKAGED
``--diagnose-grouping`` on Windows (F3). Synthetic vectors, no real photos or faces.

    python scripts/ci_make_diag_session.py <photo folder> <data dir> [closed|wal_no_shm]
    python scripts/ci_make_diag_session.py --hold <photo folder> <data dir> <seconds>    # an open writer
    python scripts/ci_make_diag_session.py --append-wal <photo folder> <data dir> <seconds>  # a changing -wal

Layout as the app makes it: <data dir>/sessions/<session_key(folder)>/project.snorlu.db (+ marker).
Two customers: K1 in costume A (+ a face-less burst 8 min later) and costume B 40 min later; K2 in costume A.
Subjects are named as the owner would label them. Prints the expected label counts as JSON.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from app.identity import actions  # noqa: E402
from app.identity.cluster import recluster  # noqa: E402
from app.storage.project import Project  # noqa: E402
from app.storage.sessions import session_dir  # noqa: E402

RNG = np.random.default_rng(11)
T0 = datetime(2026, 10, 25, 10, 0, 0)


def unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def near(base: np.ndarray, noise: float) -> np.ndarray:
    return unit(base + unit(RNG.normal(size=base.size)) * noise)


def main(folder: Path, data: Path, mode: str = "closed") -> None:
    import shutil
    import tempfile

    folder.mkdir(parents=True, exist_ok=True)
    target = session_dir(data / "sessions", folder)
    work = Path(tempfile.mkdtemp()) / "s" if mode == "wal_no_shm" else target
    p = Project.create(work, folder.name)
    if mode != "wal_no_shm":
        (target / "kirapick-session").write_text("KiraPick session data\n", encoding="utf-8")
    conn = p.conn
    conn.execute("INSERT INTO sources (root_path, added_at) VALUES (?, 'n')", (str(folder),))
    k1, k2 = unit(RNG.normal(size=128)), unit(RNG.normal(size=128))
    # Distinct costumes: different dominant colour bins (uniform random histograms would all look alike).
    look_a, look_b, look_c = (unit(np.eye(96)[k * 30 : k * 30 + 6].sum(0) + 0.05 * RNG.random(96)) for k in range(3))
    k1_makeup = near(k1, 1.2)
    plan = ([("K1-A", near(k1, 0.3), look_a, j * 20) for j in range(5)]
            + [("K1-A", None, look_a, 480 + j * 20) for j in range(3)]
            + [("K2-A", near(k2, 0.3), look_c, 1200 + j * 20) for j in range(5)]
            + [("K1-B", near(k1_makeup, 0.3), look_b, 2400 + j * 20) for j in range(5)])
    occ_label = {}
    for asset, (label, face, look, seconds) in enumerate(plan, start=1):
        conn.execute(
            """INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, capture_time, added_at, updated_at)
               VALUES (?, 1, ?, '.jpg', 'raster', 'verified', 1, 1, ?, 'ok', ?, 'n', 'n')""",
            (asset, f"SYN_{asset:04d}.JPG", str(asset), (T0 + timedelta(seconds=seconds)).isoformat()))
        occ = int(conn.execute(
            """INSERT INTO occurrences (asset_id, person_box, prominence, is_main, analysis_version, created_at)
               VALUES (?, '[0.1,0.1,0.5,0.8]', 1.0, 1, 1, 'n')""", (asset,)).lastrowid)
        occ_label[occ] = label
        vecs = (("face", None if face is None else near(face, 0.0)), ("outfit", near(look, 0.05)))
        for kind, vec in vecs:
            if vec is not None:
                conn.execute("INSERT INTO occurrence_vectors VALUES (?, ?, 't', ?)",
                             (occ, kind, vec.astype("<f4").tobytes()))
    recluster(p)
    # The owner's labelling on a copy: every occurrence in a subject named after its true person and costume
    # (manual, as renaming + fixing would leave it). The diagnostic clears these to rebuild the automatic result.
    by_label: dict[str, list[int]] = {}
    for occ, label in occ_label.items():
        by_label.setdefault(label, []).append(occ)
    for label, occs in by_label.items():
        assets = [conn.execute("SELECT asset_id FROM occurrences WHERE id = ?", (o,)).fetchone()[0] for o in occs]
        sid = int(conn.execute("INSERT INTO subjects (created_at) VALUES ('n')").lastrowid)
        actions.rename_subject(conn, sid, label)
        conn.executemany("UPDATE occurrences SET subject_id = ?, assignment = 'manual' WHERE id = ?",
                         [(sid, o) for o in occs])
        del assets
    conn.execute("""DELETE FROM subjects WHERE display_name IS NULL
                    AND id NOT IN (SELECT subject_id FROM occurrences WHERE subject_id IS NOT NULL)""")
    conn.commit()
    if mode == "wal_no_shm":  # as after a crash: .db + -wal with committed data, no -shm
        target.mkdir(parents=True, exist_ok=True)
        (target / "kirapick-session").write_text("KiraPick session data\n", encoding="utf-8")
        for name in ("project.snorlu.db", "project.snorlu.db-wal"):
            shutil.copyfile(work / name, target / name)
        p.close()
    else:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # as after KiraPick closes
        p.close()
    print(json.dumps({"occurrences": len(plan), "persons": 2, "looks": 3}))


def hold(folder: Path, data: Path, seconds: float) -> None:
    """An open writer: a connection with an open write transaction, for ``seconds``."""
    import sqlite3
    import time

    conn = sqlite3.connect(session_dir(data / "sessions", folder) / "project.snorlu.db")
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("UPDATE subjects SET display_name = 'K9-Z'")
    print("holding", flush=True)
    time.sleep(seconds)
    conn.execute("ROLLBACK")
    conn.close()


def append_wal(folder: Path, data: Path, seconds: float) -> None:
    """A source that keeps changing: bytes appended to the -wal every 50 ms for ``seconds``."""
    import time

    wal = session_dir(data / "sessions", folder) / "project.snorlu.db-wal"
    end = time.time() + seconds
    while time.time() < end:
        with open(wal, "ab") as f:
            f.write(b"\0")
        time.sleep(0.05)


if __name__ == "__main__":
    if sys.argv[1] == "--hold":
        hold(Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4]))
    elif sys.argv[1] == "--append-wal":
        append_wal(Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4]))
    else:
        main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "closed")
