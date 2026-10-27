"""Identity-plus stage: ArcFace + YoutuReID vectors for the people found by detection.

Runs after detection, resumable per photo (``stage_status`` 'embed'). It only adds
vectors (kinds 'face_arc' and 'body') and never touches the occurrences, so
older sessions gain the stronger cues without re-detecting people or re-measuring
quality. Optional: without both models the stage does nothing and grouping
keeps using SFace + outfit colours.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from app.ai.detect import pil_to_bgr
from app.ai.face_quality import FaceRefiner
from app.ai.identity_plus import ARCFACE_VERSION, BODY_VERSION, ArcFaceEmbedder, BodyEmbedder
from app.ai.models import ModelRegistry, ModelUnavailableError
from app.core.errors import ImageReadError
from app.ingest.preview import load_image
from app.storage.project import Project, utc_now

log = logging.getLogger(__name__)

STAGE = "embed"
STAGE_VERSION = 1
WORK_LONG_SIDE = 1600  # same image size as detection
USABLE_FACE_SCORE = 0.75  # = analyze_job.USABLE_FACE_SCORE
MAX_ATTEMPTS = 2
_PREFETCH = 4


class Embedders:
    """The three models the stage needs, loaded once."""

    def __init__(self, registry: ModelRegistry, *, prefer_gpu: bool = True) -> None:
        self.refiner = FaceRefiner(registry)
        self.face = ArcFaceEmbedder(registry, prefer_gpu=prefer_gpu)
        self.body = BodyEmbedder(registry, prefer_gpu=prefer_gpu)

    @property
    def device(self) -> str:
        return self.face.session.device


def available(registry: ModelRegistry) -> bool:
    return registry.ready("identity_plus")


def queue(project: Project) -> list[tuple[int, Path]]:
    conn = project.conn
    now = utc_now()
    with project.transaction():
        conn.execute(
            """INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at)
               SELECT d.asset_id, ?, ?, 'pending', 0, ? FROM stage_status d
               WHERE d.stage = 'detect' AND d.state = 'done'
               ON CONFLICT (asset_id, stage) DO UPDATE SET state = 'pending', attempts = 0,
                   stage_version = excluded.stage_version, updated_at = excluded.updated_at
               WHERE stage_status.stage_version < excluded.stage_version""",
            (STAGE, STAGE_VERSION, now),
        )
    rows = conn.execute(
        """SELECT a.id, s.root_path, a.relative_path FROM stage_status st
           JOIN assets a ON a.id = st.asset_id JOIN sources s ON s.id = a.source_id
           WHERE st.stage = ? AND a.status = 'ok'
             AND (st.state = 'pending' OR (st.state = 'failed' AND st.attempts < ?))
           ORDER BY a.capture_time, a.relative_path""",
        (STAGE, MAX_ATTEMPTS),
    ).fetchall()
    return [(int(r["id"]), Path(r["root_path"]) / Path(r["relative_path"])) for r in rows]


def vectors_for(bgr: np.ndarray, rows: list, models: Embedders) -> list[tuple[int, str, str, np.ndarray]]:
    """(occurrence id, kind, version, vector) for the occurrences of one photo.

    ``rows`` carry id, person_box, face_box, face_score (normalised boxes, as stored).
    """
    out = []
    for r in rows:
        if r["face_box"] and (r["face_score"] or 0.0) >= USABLE_FACE_SCORE:
            geo = models.refiner.refine(bgr, tuple(json.loads(r["face_box"])))
            vec = models.face.embed(bgr, geo) if geo is not None else None
            if vec is not None:
                out.append((r["id"], "face_arc", ARCFACE_VERSION, vec))
        if r["person_box"]:
            vec = models.body.embed(bgr, tuple(json.loads(r["person_box"])))
            if vec is not None:
                out.append((r["id"], "body", BODY_VERSION, vec))
    return out


def store(project: Project, asset_id: int, found: list[tuple[int, str, str, np.ndarray]]) -> None:
    with project.transaction() as conn:
        conn.execute("""DELETE FROM occurrence_vectors WHERE kind IN ('face_arc', 'body')
                        AND occurrence_id IN (SELECT id FROM occurrences WHERE asset_id = ?)""", (asset_id,))
        for occ_id, kind, version, vec in found:
            conn.execute("INSERT INTO occurrence_vectors VALUES (?, ?, ?, ?)",
                         (occ_id, kind, version, np.asarray(vec, "<f4").tobytes()))
        _mark(conn, asset_id, "done", None)


def _mark(conn, asset_id: int, state: str, error: str | None) -> None:  # noqa: ANN001
    conn.execute("""UPDATE stage_status SET state = ?, stage_version = ?, attempts = attempts + 1, error = ?,
                    updated_at = ? WHERE asset_id = ? AND stage = ?""",
                 (state, STAGE_VERSION, error, utc_now(), asset_id, STAGE))


def run(project: Project, registry: ModelRegistry, progress: Callable[[str, int, int], None],
        should_cancel: Callable[[], bool], *, prefer_gpu: bool = True) -> tuple[int, int, bool]:
    """Returns (photos done, photos failed, cancelled). Does nothing without the models."""
    if not available(registry):
        return 0, 0, False
    todo = queue(project)
    if not todo:
        return 0, 0, False
    try:
        models = Embedders(registry, prefer_gpu=prefer_gpu)
    except ModelUnavailableError:
        return 0, 0, False
    progress("device:" + models.device, 0, 0)
    done = failed = 0
    total = len(todo)
    progress(STAGE, 0, total)

    def load(path: Path) -> np.ndarray:
        return pil_to_bgr(load_image(path, max_long_side=WORK_LONG_SIDE, min_long_side=WORK_LONG_SIDE).image)

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed-load") as pool:
        pending: list[tuple[int, Future]] = []
        it = iter(todo)
        while True:
            while len(pending) < _PREFETCH:
                nxt = next(it, None)
                if nxt is None:
                    break
                pending.append((nxt[0], pool.submit(load, nxt[1])))
            if not pending:
                break
            if should_cancel():
                for _, fut in pending:
                    fut.cancel()
                return done, failed, True
            asset_id, fut = pending.pop(0)
            try:
                bgr = fut.result()
                rows = project.conn.execute(
                    "SELECT id, person_box, face_box, face_score FROM occurrences WHERE asset_id = ?", (asset_id,)
                ).fetchall()
                store(project, asset_id, vectors_for(bgr, rows, models))
                done += 1
            except (ImageReadError, cv2.error, OSError, MemoryError) as exc:
                with project.transaction() as conn:
                    _mark(conn, asset_id, "failed", f"{type(exc).__name__}: {exc}"[:300])
                failed += 1
            except Exception as exc:  # noqa: BLE001 - one photo must not stop the stage
                log.exception("identity embedding failed for one photo")
                with project.transaction() as conn:
                    _mark(conn, asset_id, "failed", f"internal_error: {type(exc).__name__}")
                failed += 1
            progress(STAGE, done + failed, total)
    return done, failed, False
