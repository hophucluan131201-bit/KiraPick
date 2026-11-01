"""CI only: a synthetic KiraPick session for a synthetic photo folder, to test the PACKAGED
``--diagnose-grouping`` on Windows (F3). Synthetic vectors, no real photos or faces.

    python scripts/ci_make_diag_session.py <photo folder> <data dir>   # data dir = %LOCALAPPDATA%\\KiraPick

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


def main(folder: Path, data: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    target = session_dir(data / "sessions", folder)
    p = Project.create(target, folder.name)
    (target / "kirapick-session").write_text("KiraPick session data\n", encoding="utf-8")
    conn = p.conn
    conn.execute("INSERT INTO sources (root_path, added_at) VALUES (?, 'n')", (str(folder),))
    k1, k2 = unit(RNG.normal(size=128)), unit(RNG.normal(size=128))
    look_a, look_b, look_c = (unit(RNG.random(96)) for _ in range(3))
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
    # The owner's labelling: the face-less burst joined to its costume, then every subject renamed.
    by_label: dict[str, set[int]] = {}
    for occ, label in occ_label.items():
        sid = conn.execute("SELECT subject_id FROM occurrences WHERE id = ?", (occ,)).fetchone()[0]
        if sid is not None:
            by_label.setdefault(label, set()).add(sid)
    for label, sids in by_label.items():
        keep, *rest = sorted(sids)
        for other in rest:
            actions.merge_subjects(conn, keep, other)
        actions.rename_subject(conn, keep, label)
    conn.commit()
    p.close()
    print(json.dumps({"occurrences": len(plan), "persons": 2, "looks": 3}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
