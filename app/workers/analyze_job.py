"""Resumable AI analysis: find people and faces in every photo, then group them.

One heavy model at a time on the GPU; photo decoding is prefetched on a small
thread pool. Each photo's results are committed on their own, so a cancel or
crash resumes where it stopped (``stage_status`` 'detect').

Re-analysis keeps occurrence ids stable: new detections are matched to the
previous ones of the same photo by box overlap, so manual assignments survive.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.ai.detect import FaceDetector, FaceEmbedder, PersonDetector, associate, iou, pil_to_bgr
from app.ai.models import ModelRegistry
from app.core.errors import ImageReadError
from app.identity.features import OUTFIT_VERSION, OccurrenceFeatures, features_for, outfit_descriptor, outfit_image
from app.ingest.preview import load_image
from app.storage.project import Project, utc_now

log = logging.getLogger(__name__)

STAGE = "detect"
STAGE_VERSION = 1  # bump when detection/feature extraction changes
ANALYSIS_LONG_SIDE = 1600
USABLE_FACE_SCORE = 0.75  # below this a face is "seen" but not trusted for identity
FACE_VECTOR_VERSION = "sface-2021dec"
MAX_ATTEMPTS = 2
_PREFETCH = 4


@dataclass(slots=True)
class AnalyzeProgress:
    phase: str  # "load_models" | "detect" | "quality" | "group"
    done: int
    total: int


@dataclass(slots=True)
class AnalyzeSummary:
    analysed: int = 0
    failed: int = 0
    occurrences: int = 0
    measured: int = 0
    measure_failed: int = 0
    cancelled: bool = False
    device: str = "cpu"
    fallback_reason: str | None = None


def _box_json(box: tuple[float, float, float, float] | None) -> str | None:
    return json.dumps([round(v, 5) for v in box]) if box is not None else None


def _vec(v: np.ndarray) -> bytes:
    return np.asarray(v, dtype="<f4").tobytes()


class AnalyzeJob:
    def __init__(self, project: Project, registry: ModelRegistry | None = None, *, prefer_gpu: bool = True) -> None:
        self.project = project
        self.registry = registry or ModelRegistry()
        self.prefer_gpu = prefer_gpu
        self.crop_dir = project.cache_dir / "crops"

    # ----------------------------------------------------------- queue
    def _queue_and_list(self) -> list[tuple[int, Path]]:
        conn = self.project.conn
        now = utc_now()
        with self.project.transaction():
            conn.execute(
                """INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at)
                   SELECT a.id, ?, ?, 'pending', 0, ? FROM assets a WHERE a.status = 'ok'
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

    # ------------------------------------------------------------- run
    def run(
        self,
        progress: Callable[[AnalyzeProgress], None] = lambda _p: None,
        should_cancel: Callable[[], bool] = lambda: False,
    ) -> AnalyzeSummary:
        summary = AnalyzeSummary()
        todo = self._queue_and_list()
        if todo:
            progress(AnalyzeProgress("load_models", 0, len(todo)))
            persons = PersonDetector.load(self.registry, prefer_gpu=self.prefer_gpu)
            faces = FaceDetector(self.registry)
            embedder = FaceEmbedder(self.registry)
            summary.device = persons.device
            summary.fallback_reason = persons.session.fallback_reason
            self.crop_dir.mkdir(parents=True, exist_ok=True)
            self._detect_all(todo, persons, faces, embedder, summary, progress, should_cancel)
        if not summary.cancelled:
            from app.workers import quality_job  # local import: avoids a cycle through app.quality

            summary.measured, summary.measure_failed, summary.cancelled = quality_job.run(
                self.project, self.registry, lambda phase, done, total: progress(AnalyzeProgress(phase, done, total)),
                should_cancel)
        if not summary.cancelled:
            from app.identity.cluster import recluster  # local import: clustering is pure, no models

            progress(AnalyzeProgress("group", 0, 1))
            refresh_outfits(self.project)
            recluster(self.project)
            progress(AnalyzeProgress("group", 1, 1))
        return summary

    def _detect_all(self, todo, persons, faces, embedder, summary, progress, should_cancel) -> None:  # noqa: ANN001
        total = len(todo)

        def load(path: Path) -> np.ndarray:
            return pil_to_bgr(load_image(path, max_long_side=ANALYSIS_LONG_SIDE, min_long_side=ANALYSIS_LONG_SIDE).image)

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="analyze-load") as pool:
            pending: list[tuple[int, Future[np.ndarray]]] = []
            queue = iter(todo)
            done = 0
            while True:
                while len(pending) < _PREFETCH:
                    item = next(queue, None)
                    if item is None:
                        break
                    pending.append((item[0], pool.submit(load, item[1])))
                if not pending:
                    break
                if should_cancel():
                    summary.cancelled = True
                    for _, fut in pending:
                        fut.cancel()
                    break
                asset_id, fut = pending.pop(0)
                try:
                    bgr = fut.result()
                    found_persons = persons.detect(bgr)
                    found_faces = faces.detect(bgr)
                    for face in found_faces:
                        if face.score >= USABLE_FACE_SCORE:
                            face.embedding = embedder.embed(bgr, face)
                    feats = features_for(bgr, associate(found_persons, found_faces), USABLE_FACE_SCORE)
                    self._store(asset_id, feats)
                    summary.analysed += 1
                    summary.occurrences += len(feats)
                except (ImageReadError, cv2.error, OSError) as exc:
                    self._mark_failed(asset_id, f"{type(exc).__name__}: {exc}"[:300])
                    summary.failed += 1
                except Exception as exc:  # noqa: BLE001 - one photo must not stop the analysis
                    log.exception("analysis failed for one photo")
                    self._mark_failed(asset_id, f"internal_error: {type(exc).__name__}")
                    summary.failed += 1
                done += 1
                progress(AnalyzeProgress("detect", done, total))

    # ----------------------------------------------------------- store
    def _store(self, asset_id: int, feats: list[OccurrenceFeatures]) -> None:
        now = utc_now()
        with self.project.transaction() as conn:
            old = conn.execute(
                "SELECT id, person_box, face_box, crop_file FROM occurrences WHERE asset_id = ?", (asset_id,)
            ).fetchall()
            unmatched = {r["id"]: r for r in old}
            for f in feats:
                occ_id = self._match(f, unmatched)
                values = (
                    _box_json(f.person_box), f.person_score, _box_json(f.face_box), f.face_score,
                    f.prominence, int(f.is_main), STAGE_VERSION,
                )
                if occ_id is None:
                    occ_id = int(conn.execute(
                        """INSERT INTO occurrences (asset_id, person_box, person_score, face_box, face_score,
                           prominence, is_main, analysis_version, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (asset_id, *values, now),
                    ).lastrowid)
                else:
                    del unmatched[occ_id]
                    conn.execute(
                        """UPDATE occurrences SET person_box = ?, person_score = ?, face_box = ?, face_score = ?,
                           prominence = ?, is_main = ?, analysis_version = ? WHERE id = ?""",
                        (*values, occ_id),
                    )
                conn.execute("DELETE FROM occurrence_vectors WHERE occurrence_id = ?", (occ_id,))
                if f.face_vector is not None:
                    conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'face', ?, ?)",
                                 (occ_id, FACE_VECTOR_VERSION, _vec(f.face_vector)))
                if f.outfit_vector is not None:
                    conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'outfit', ?, ?)",
                                 (occ_id, OUTFIT_VERSION, _vec(f.outfit_vector)))
                crop_name = None
                if f.crop is not None:
                    crop_name = f"crops/{occ_id:08d}.jpg"
                    target = self.project.cache_dir / crop_name
                    tmp = target.with_name(target.stem + ".tmp.jpg")
                    cv2.imwrite(str(tmp), f.crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    os.replace(tmp, target)
                conn.execute("UPDATE occurrences SET crop_file = ? WHERE id = ?", (crop_name, occ_id))
            for occ_id in unmatched:  # people no longer detected in this photo
                conn.execute("DELETE FROM occurrences WHERE id = ?", (occ_id,))
            # New boxes: the quality measurements of this photo must be redone.
            conn.execute("DELETE FROM measurements WHERE asset_id = ? AND extractor = 'quality'", (asset_id,))
            conn.execute("UPDATE stage_status SET state = 'pending', attempts = 0 WHERE asset_id = ? AND stage = 'quality'",
                         (asset_id,))
            conn.execute(
                """UPDATE stage_status SET state = 'done', stage_version = ?, attempts = attempts + 1, error = NULL,
                   updated_at = ? WHERE asset_id = ? AND stage = ?""",
                (STAGE_VERSION, now, asset_id, STAGE),
            )

    @staticmethod
    def _match(f: OccurrenceFeatures, candidates: dict) -> int | None:  # noqa: ANN001
        best, best_iou = None, 0.5
        for occ_id, row in candidates.items():
            for mine, theirs in ((f.person_box, row["person_box"]), (f.face_box, row["face_box"])):
                if mine is None or theirs is None:
                    continue
                overlap = iou(mine, tuple(json.loads(theirs)))
                if overlap > best_iou:
                    best, best_iou = occ_id, overlap
        return best

    def _mark_failed(self, asset_id: int, error: str) -> None:
        self.project.conn.execute(
            """UPDATE stage_status SET state = 'failed', attempts = attempts + 1, error = ?, updated_at = ?
               WHERE asset_id = ? AND stage = ?""",
            (error, utc_now(), asset_id, STAGE),
        )


def refresh_outfits(project: Project) -> int:
    """Recompute outfit vectors made by an older descriptor from the cached thumbnails.

    Needs no AI model, so an improved descriptor reaches existing sessions in
    seconds instead of a full re-analysis. Returns the number of vectors updated.
    """
    rows = project.conn.execute(
        """SELECT o.id, o.asset_id, o.person_box, p.file_name FROM occurrences o
           JOIN previews p ON p.asset_id = o.asset_id AND p.kind = 'thumb'
           LEFT JOIN occurrence_vectors v ON v.occurrence_id = o.id AND v.kind = 'outfit'
           WHERE o.person_box IS NOT NULL AND (v.model_version IS NULL OR v.model_version != ?)
           ORDER BY o.asset_id""",
        (OUTFIT_VERSION,),
    ).fetchall()
    updated = 0
    images: dict[int, np.ndarray | None] = {}
    with project.transaction() as conn:
        for r in rows:
            if r["asset_id"] not in images:
                images.clear()  # rows are ordered by photo: keep one decoded thumbnail
                try:  # np.fromfile + imdecode: cv2.imread cannot open non-ASCII paths on Windows
                    data = np.fromfile(project.cache_dir / r["file_name"], dtype=np.uint8)
                    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
                except OSError:
                    img = None
                images[r["asset_id"]] = None if img is None else outfit_image(img)
            small = images[r["asset_id"]]
            vec = outfit_descriptor(small, tuple(json.loads(r["person_box"]))) if small is not None else None
            conn.execute("DELETE FROM occurrence_vectors WHERE occurrence_id = ? AND kind = 'outfit'", (r["id"],))
            if vec is not None:
                conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'outfit', ?, ?)",
                             (r["id"], OUTFIT_VERSION, _vec(vec)))
                updated += 1
    if rows:
        log.info("outfit vectors refreshed: %d of %d", updated, len(rows))
    return updated
