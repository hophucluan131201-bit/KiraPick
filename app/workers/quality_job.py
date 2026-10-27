"""Quality stage: measure every main subject occurrence on the full-resolution photo.

Runs after detection (it uses the stored person/face boxes), resumable per photo
(``stage_status`` 'quality'). No score is stored here — only measurements; the
rubric in app.quality.score turns them into scores and can change without
re-measuring.
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
from app.ai.aesthetic import AestheticModel
from app.ai.eyes import EyeState
from app.ai.face_quality import FaceQuality, FaceRefiner
from app.ai.models import ModelRegistry, ModelUnavailableError
from app.core.errors import ImageReadError
from app.ingest.preview import load_full_resolution
from app.quality.measure import (
    LAYOUT_VERSION,
    QUALITY_VERSION,
    edge_sharpness,
    exposure,
    eye_region,
    framing,
    layout_descriptor,
)
from app.storage.project import Project, utc_now

log = logging.getLogger(__name__)

STAGE = "quality"
STAGE_VERSION = 3  # 2: eyes open/closed (MediaPipe blendshapes); 3: aesthetic hint (TOPIQ)
EXTRACTOR = "quality"
WORK_LONG_SIDE = 1600  # exposure / layout are measured at this size
FACE_FOR_FOCUS = 0.6  # detection score needed to look for the eyes
MAX_ATTEMPTS = 2
_PREFETCH = 3


def queue(project: Project) -> list[tuple[int, Path]]:
    """Photos whose people were detected but not measured (or measured by an older version)."""
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


def measure_occurrence(full: np.ndarray, small: np.ndarray, person: tuple | None, face: tuple | None,
                       face_score: float | None, refiner: FaceRefiner | None,
                       face_quality: FaceQuality | None,
                       eyes: EyeState | None = None) -> tuple[dict, np.ndarray | None]:
    h, w = full.shape[:2]
    values: dict = {"eye_sharp": None, "face_sharp": None, "body_sharp": None, "face_quality": None,
                    "face_luma": None, "face_clip": None, "eyes_found": 0.0}
    gray = None
    if face is not None and face_score is not None and face_score >= FACE_FOR_FOCUS and refiner is not None:
        geo = refiner.refine(full, face)
        if geo is not None:
            gray = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY)
            eye_box = eye_region(geo, w, h)
            if eye_box is not None:
                x0, y0, x1, y1 = eye_box
                values["eye_sharp"] = edge_sharpness(gray[y0:y1, x0:x1])
                values["eyes_found"] = 1.0
            fx, fy, fw, fh = geo.box
            ix0, iy0 = max(0, int(fx + fw * 0.15)), max(0, int(fy + fh * 0.1))
            ix1, iy1 = min(w, int(fx + fw * 0.85)), min(h, int(fy + fh * 0.9))
            if ix1 - ix0 >= 16 and iy1 - iy0 >= 16:
                values["face_sharp"] = edge_sharpness(gray[iy0:iy1, ix0:ix1])
                exp = exposure(full[iy0:iy1, ix0:ix1])
                values["face_luma"], values["face_clip"] = exp["luma"], exp["clip"]
            if face_quality is not None:
                values["face_quality"] = face_quality.score(full, geo)
            if eyes is not None:
                state = eyes.measure(full, geo)
                if state is not None:
                    values.update(state)
                    values["blink"] = max(state["blink_left"], state["blink_right"])
    if person is not None:
        px, py, pw, ph = person[0] * w, person[1] * h, person[2] * w, person[3] * h
        bx0, by0 = max(0, int(px + pw * 0.25)), max(0, int(py + ph * 0.15))
        bx1, by1 = min(w, int(px + pw * 0.75)), min(h, int(py + ph * 0.6))
        if bx1 - bx0 >= 16 and by1 - by0 >= 16:
            if gray is None:
                gray = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY)
            values["body_sharp"] = edge_sharpness(gray[by0:by1, bx0:bx1])
        sh, sw = small.shape[:2]
        sx0, sy0 = max(0, int(person[0] * sw)), max(0, int(person[1] * sh))
        sx1, sy1 = min(sw, int((person[0] + person[2]) * sw)), min(sh, int((person[1] + person[3]) * sh))
        if sx1 - sx0 >= 8 and sy1 - sy0 >= 8:
            exp = exposure(small[sy0:sy1, sx0:sx1])
            values["body_luma"], values["body_clip"], values["body_dark"] = exp["luma"], exp["clip"], exp["dark"]
    values.update(framing(person, face))
    return values, layout_descriptor(small, person)


def run(project: Project, registry: ModelRegistry, progress: Callable[[str, int, int], None],
        should_cancel: Callable[[], bool]) -> tuple[int, int, bool]:
    """Returns (measured photos, failed photos, cancelled)."""
    todo = queue(project)
    if not todo:
        return 0, 0, False
    try:
        refiner: FaceRefiner | None = FaceRefiner(registry)
    except ModelUnavailableError:
        refiner = None
    try:
        face_quality: FaceQuality | None = FaceQuality(registry)
    except ModelUnavailableError:
        face_quality = None  # honest: face quality stays "not available"
    try:
        eyes: EyeState | None = EyeState(registry)
    except ModelUnavailableError:
        eyes = None  # honest: eyes stay "not judged"
    try:
        aesthetic: AestheticModel | None = AestheticModel(registry)
    except ModelUnavailableError:
        aesthetic = None  # honest: aesthetics stay "not judged"
    done = failed = 0
    total = len(todo)
    progress(STAGE, 0, total)

    def load(path: Path) -> tuple[np.ndarray, str]:
        loaded = load_full_resolution(path)
        return pil_to_bgr(loaded.image), loaded.source.value

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="quality-load") as pool:
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
                full, source = fut.result()
                _store(project, asset_id, full, source, refiner, face_quality, eyes, aesthetic)
                done += 1
            except (ImageReadError, cv2.error, OSError, MemoryError) as exc:
                _mark(project, asset_id, "failed", f"{type(exc).__name__}: {exc}"[:300])
                failed += 1
            except Exception as exc:  # noqa: BLE001 - one photo must not stop the stage
                log.exception("quality measurement failed for one photo")
                _mark(project, asset_id, "failed", f"internal_error: {type(exc).__name__}")
                failed += 1
            progress(STAGE, done + failed, total)
    return done, failed, False


def _store(project: Project, asset_id: int, full: np.ndarray, source: str, refiner: FaceRefiner | None,
           face_quality: FaceQuality | None, eyes: EyeState | None = None,
           aesthetic: AestheticModel | None = None) -> None:
    h, w = full.shape[:2]
    scale = min(1.0, WORK_LONG_SIDE / max(h, w))
    small = cv2.resize(full, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else full
    rows = project.conn.execute(
        "SELECT id, person_box, face_box, face_score FROM occurrences WHERE asset_id = ? AND is_main = 1",
        (asset_id,),
    ).fetchall()
    mos = aesthetic.score(small) if aesthetic is not None and rows else None  # one per photo
    results = []
    for r in rows:
        person = tuple(json.loads(r["person_box"])) if r["person_box"] else None
        face = tuple(json.loads(r["face_box"])) if r["face_box"] else None
        values, layout = measure_occurrence(full, small, person, face, r["face_score"], refiner, face_quality, eyes)
        values["full_long_side"] = float(max(h, w))
        values["aesthetic_mos"] = mos
        results.append((r["id"], values, layout))
    now = utc_now()
    with project.transaction() as conn:
        conn.execute("DELETE FROM measurements WHERE asset_id = ? AND extractor = ?", (asset_id, EXTRACTOR))
        for occ_id, values, layout in results:
            conn.execute(
                """INSERT INTO measurements (asset_id, occurrence_id, extractor, extractor_version, input_source,
                   values_json, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (asset_id, occ_id, EXTRACTOR, QUALITY_VERSION, source, json.dumps(values), now),
            )
            conn.execute("DELETE FROM occurrence_vectors WHERE occurrence_id = ? AND kind = 'layout'", (occ_id,))
            if layout is not None:
                conn.execute("INSERT INTO occurrence_vectors VALUES (?, 'layout', ?, ?)",
                             (occ_id, LAYOUT_VERSION, np.asarray(layout, "<f4").tobytes()))
        _mark(project, asset_id, "done", None, conn)


def _mark(project: Project, asset_id: int, state: str, error: str | None, conn=None) -> None:  # noqa: ANN001
    sql = """UPDATE stage_status SET state = ?, stage_version = ?, attempts = attempts + 1, error = ?, updated_at = ?
             WHERE asset_id = ? AND stage = ?"""
    args = (state, STAGE_VERSION, error, utc_now(), asset_id, STAGE)
    if conn is not None:
        conn.execute(sql, args)
    else:
        with project.transaction() as c:
            c.execute(sql, args)
