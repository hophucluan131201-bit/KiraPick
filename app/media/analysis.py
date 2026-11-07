"""'Phân tích sự kiện' (one button, UX-1; plan Mốc 1 M6/M7): shot size and focus warnings per photo, then moments.

Models: only through MediaRegistry (YOLOX-S, YOLOX-M on a fast GPU, YuNet: verified for Media). CLIP and SFace are
pending, so there is no AI content label and no grouping of people here. Every run is an ``analysis_runs`` row
(mode 'media') with the weights really opened (id, SHA-256, provider); every label it writes carries its run_id.

Without the detection weights the shot size and focus warnings are not computed at all (nothing is guessed): the
summary says why, the photos stay ⏳, and the moments are still split by pauses (they need no model).

Resumable: a photo is done when ``media_analysis`` has it at the current versions; cancelling keeps what is done.
Nothing here writes to a photo or changes a user decision (labels the user confirmed or removed are kept: labels.py).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.media import labels as lb
from app.media import moments
from app.media.shot import SHOT_VERSION, Box, ShotRules, classify, subjects_from
from app.storage import provenance
from app.storage.project import Project, utc_now

log = logging.getLogger(__name__)

STAGE = "media_analyse"
DETECT_LONG_SIDE = 1600  # as the personal-mode detection: YuNet runs at 640 and 1600
DETECTION_MODELS = ("person_detector_s", "face_detector")
NO_DETECTION = ("Chưa có mô hình dò người / khuôn mặt được phép dùng cho Media (YOLOX-S, YuNet): không xếp cỡ cảnh "
                "và không cảnh báo nét. Khoảnh khắc vẫn được chia theo khoảng nghỉ.")

# detect(bgr) -> (persons [(box, score)], faces [(box, score)]) on the image passed in
Detect = Callable[[np.ndarray], tuple[list[tuple[Box, float]], list[tuple[Box, float]]]]


@dataclass
class AnalysisSummary:
    analysed: int = 0
    failed: int = 0
    already_done: int = 0
    cancelled: bool = False
    unavailable: str | None = None
    device: str | None = None
    run_id: int | None = None
    models: list[dict] = field(default_factory=list)
    moments: int = 0


def focus_version() -> str | None:
    """Version of the focus rule (M7); None while it is not part of the analysis."""
    try:
        from app.media.focus import FOCUS_VERSION
    except ImportError:
        return None
    return FOCUS_VERSION


def load_detectors(registry=None, prefer_gpu: bool = True) -> tuple[Detect, str, list[str]]:  # noqa: ANN001
    """The real detectors, through MediaRegistry only. Returns (detect, device, model ids that may be opened)."""
    from app.ai.detect import FaceDetector, PersonDetector
    from app.media.models import MediaRegistry

    media = registry if registry is not None else MediaRegistry()
    persons = PersonDetector.load(media, prefer_gpu=prefer_gpu)
    faces = FaceDetector(media)

    def detect(bgr: np.ndarray) -> tuple[list, list]:
        return persons.detect(bgr), [(f.box, f.score) for f in faces.detect(bgr)]

    return detect, persons.device, ["person_detector_s", "person_detector_m", "face_detector"]


def detection_available(registry=None) -> bool:  # noqa: ANN001
    from app.media.models import MediaRegistry

    media = registry if registry is not None else MediaRegistry()
    return all(media.available(m) for m in DETECTION_MODELS)


def _todo(conn, shot_v: str, focus_v: str | None) -> tuple[list[tuple[int, str]], int]:  # noqa: ANN001
    rows = conn.execute("""SELECT a.id, m.shot_version, m.focus_version, m.status FROM assets a
                           LEFT JOIN media_analysis m ON m.asset_id = a.id
                           WHERE a.status = 'ok' ORDER BY a.id""").fetchall()
    todo, done = [], 0
    for asset_id, sv, fv, status in rows:
        if status is not None and sv == shot_v and fv == focus_v:
            done += 1
        else:
            todo.append(asset_id)
    return todo, done


def _bgr(path) -> np.ndarray:  # noqa: ANN001
    from app.ai.detect import pil_to_bgr
    from app.ingest.preview import load_image

    return pil_to_bgr(load_image(path, max_long_side=DETECT_LONG_SIDE, min_long_side=DETECT_LONG_SIDE).image)


def analyse_event(event: Project, *, detect: Detect | None = None, registry=None,  # noqa: ANN001, C901
                  prefer_gpu: bool = True, rules: ShotRules = ShotRules(),  # noqa: B008
                  progress: Callable[[int, int], None] | None = None,
                  should_cancel: Callable[[], bool] | None = None,
                  load_full: Callable | None = None) -> AnalysisSummary:
    """Analyse every photo not done yet. ``detect`` replaces the models (tests: synthetic boxes)."""
    summary = AnalysisSummary()
    progress = progress or (lambda done, total: None)
    should_cancel = should_cancel or (lambda: False)
    focus_v = focus_version()
    model_ids: list[str] = []
    if detect is None:
        if not detection_available(registry):
            summary.unavailable = NO_DETECTION
        else:
            detect, summary.device, model_ids = load_detectors(registry, prefer_gpu)
    if detect is not None:
        todo, summary.already_done = _todo(event.conn, SHOT_VERSION, focus_v)
        if todo:
            with event.transaction() as conn:
                summary.run_id = provenance.start_run(conn, STAGE, mode="media")
            recorded = False
            for i, asset_id in enumerate(todo):
                if should_cancel():
                    summary.cancelled = True
                    break
                try:
                    measures = _one(event, asset_id, detect, rules, summary.run_id, focus_v, load_full)
                    summary.analysed += 1
                except Exception as exc:  # noqa: BLE001 - one bad photo never stops the event
                    log.warning("media analysis: photo %s failed: %s", asset_id, type(exc).__name__)
                    with event.transaction() as conn:
                        _mark(conn, asset_id, "failed", summary.run_id, None, focus_v)
                    summary.failed += 1
                    measures = None
                if measures is not None and not recorded and model_ids:
                    with event.transaction() as conn:  # the weights are opened lazily: record after the first photo
                        provenance.record_models(conn, summary.run_id, model_ids)
                    recorded = True
                progress(i + 1, len(todo))
            summary.models = provenance.run_models(event.conn, summary.run_id)
    if not summary.cancelled:
        moments.analyse(event)
        summary.moments = len(moments.moments(event.conn))
    return summary


def _mark(conn, asset_id: int, status: str, run_id: int | None, measures: dict | None,  # noqa: ANN001
          focus_v: str | None) -> None:
    conn.execute("""INSERT INTO media_analysis (asset_id, shot_version, focus_version, status, run_id, measures_json,
                                                updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (asset_id) DO UPDATE SET shot_version = excluded.shot_version,
                    focus_version = excluded.focus_version, status = excluded.status, run_id = excluded.run_id,
                    measures_json = excluded.measures_json, updated_at = excluded.updated_at""",
                 (asset_id, SHOT_VERSION, focus_v, status, run_id,
                  None if measures is None else json.dumps(measures), utc_now()))


def _one(event: Project, asset_id: int, detect: Detect, rules: ShotRules, run_id: int,  # noqa: ANN001
         focus_v: str | None, load_full) -> dict:
    path = event.asset_path(asset_id)
    bgr = _bgr(path)
    h, w = bgr.shape[:2]
    persons, faces = detect(bgr)
    subjects = subjects_from(persons, faces)
    shot = classify(subjects, w, h, rules)
    measures: dict = {"shot": shot.measures, "shot_path": shot.path}
    focus_values: dict[str, float | None] | None = None
    unmeasurable = False
    if focus_v is not None:
        from app.media import focus

        result = focus.analyse(path, shot.subject, (w, h), load_full=load_full)
        focus_values, unmeasurable = result.warnings, result.unmeasurable
        measures["focus"] = result.measures
    with event.transaction() as conn:
        lb.write_ai(conn, asset_id, "shot", {} if shot.value == "?" else {shot.value: shot.confidence}, run_id)
        if focus_values is not None:
            lb.write_ai(conn, asset_id, "focus", focus_values, run_id, unmeasurable=unmeasurable)
        _mark(conn, asset_id, "done", run_id, measures, focus_v)
    return measures


def progress_of(conn) -> dict[str, int]:  # noqa: ANN001
    """Readable photos analysed / failed / waiting (⏳)."""
    total = int(conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'ok'").fetchone()[0])
    done, failed = (int(conn.execute(f"SELECT COUNT(*) FROM media_analysis m JOIN assets a ON a.id = m.asset_id "  # noqa: S608
                                     f"WHERE a.status = 'ok' AND m.status = '{s}'").fetchone()[0])
                    for s in ("done", "failed"))
    return {"total": total, "done": done, "failed": failed, "waiting": total - done - failed}
