"""Basic export of an event (MED-EXP, approved 2026-11-07; plan Mốc 1 M11).

The photos marked P are COPIED (never moved or changed) with the Chụp cá nhân export: collision-safe names (two
cameras that both wrote DSC_0001.JPG give two files), existing files never overwritten, each copy verified by
SHA-256, a record of the run kept in the event's folder. Sub-folders:
  - by moment: "01 Khai mạc", "02 …" in time order; P photos without a moment (event not analysed yet) go to
    "Chưa chia khoảnh khắc";
  - by shot size: "Toàn" / "Trung" / "Cận" / "Chưa xác định" (the label shown: the user's, else the AI's);
  - one folder.
Photos still ⏳ export by their P / X like any other.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.export.copy_export import ExportPlan, ExportResult, Selection, plan_export, run_export, select_ids
from app.export.formats import ExportFormat
from app.export.layout import safe_folder_name
from app.export.photos import Photo
from app.media import labels as lb
from app.media import moments as mo
from app.storage.project import Project

BY_MOMENT, BY_SHOT, SINGLE = "moment", "shot", "single"
NO_MOMENT = "Chưa chia khoảnh khắc"
NO_SHOT = "Chưa xác định"
RECORD_DIR = "exports"


def folder_names(project: Project, by: str) -> dict[int, str]:
    """asset id -> sub-folder for the photos that have one (others: NO_MOMENT / NO_SHOT)."""
    conn = project.conn
    out: dict[int, str] = {}
    if by == BY_MOMENT:
        for i, m in enumerate(mo.moments(conn), start=1):
            name = f"{i:02d} {safe_folder_name(m.name, 'Khoảnh khắc')}"
            for a in m.assets:
                out[a] = name
    elif by == BY_SHOT:
        for a, value, state in conn.execute(
                "SELECT asset_id, value, state FROM labels WHERE grp = 'shot' AND state IN ('suggested', 'confirmed')"):
            if value in lb.SHOT and (a not in out or state == "confirmed"):
                out[a] = lb.SHOT[value]
    return out


def plan(project: Project, destination: Path, by: str = BY_MOMENT, fmt: ExportFormat = ExportFormat.RAW_JPEG,
         asset_ids: list[int] | None = None) -> ExportPlan:
    ids = asset_ids if asset_ids is not None else select_ids(project.conn, Selection.KEEP)
    if by == SINGLE:
        return plan_export(project, ids, destination, fmt=fmt)
    names = folder_names(project, by)
    fallback = NO_MOMENT if by == BY_MOMENT else NO_SHOT

    def folders_of(photo: Photo) -> list[str]:
        for a in [photo.photo_id, *(f.asset_id for f in photo.files)]:
            if a in names:
                return [names[a]]
        return [fallback]

    return plan_export(project, ids, destination, fmt=fmt, folders_of=folders_of)


def run(project: Project, export_plan: ExportPlan, *, progress: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None) -> ExportResult:
    record = project.folder / RECORD_DIR
    record.mkdir(parents=True, exist_ok=True)
    return run_export(export_plan, progress=progress, should_cancel=should_cancel, record_dir=record)
