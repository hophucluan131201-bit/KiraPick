"""Copy selected photos to a destination folder — originals are never touched.

Safety rules:
- copies only; destination files are created with exclusive-create, so an
  existing file is never overwritten (a free " (n)" name is chosen instead);
- a photo already present at the destination (same bytes, e.g. from an
  earlier export) is skipped instead of being copied again as " (1)";
- RAW+JPEG pairs are exported together and keep a common stem;
- every copy is verified by size, a failed/cancelled partial copy is removed
  (only files this export created are ever removed);
- the destination may not be an imported source folder itself, nor the
  project folder.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath

from app.core.errors import SnorluError
from app.ingest.fingerprint import quick_fingerprint
from app.storage.project import Project

_CHUNK = 1024 * 1024
MANIFEST_DIR = "_snorlu_danh_sach"  # export lists live here, not between the photos


class ExportError(SnorluError):
    pass


class Selection(str, Enum):
    KEEP = "keep"
    FAVORITE = "favorite"
    RATED = "rated"
    IDS = "ids"
    COLLECTION = "collection"  # a client's pick list


@dataclass(frozen=True, slots=True)
class ExportItem:
    asset_id: int
    source: Path
    dest_relative: str  # POSIX path relative to the destination folder
    size: int
    flag: str | None
    rating: int
    favorite: bool
    capture_time: str | None
    camera: str | None


@dataclass(slots=True)
class ExportPlan:
    destination: Path
    items: list[ExportItem]
    missing: list[str] = field(default_factory=list)  # selected files no longer on disk
    already_present: list[str] = field(default_factory=list)  # identical copy already at the destination

    @property
    def total_bytes(self) -> int:
        return sum(i.size for i in self.items)


@dataclass(slots=True)
class ExportResult:
    copied: list[str] = field(default_factory=list)
    renamed: dict[str, str] = field(default_factory=dict)  # planned -> actual (race with another program)
    failed: dict[str, str] = field(default_factory=dict)
    cancelled: bool = False
    manifest_csv: Path | None = None
    manifest_json: Path | None = None


def select_assets(
    project: Project, selection: Selection, *, min_rating: int = 1, ids: list[int] | None = None,
    collection_id: int | None = None,
) -> list[int]:
    """Photo-level selection (RAW of a pair stands for the pair)."""
    base = """SELECT a.id FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
              WHERE a.status = 'ok'"""
    if selection is Selection.KEEP:
        rows = project.conn.execute(base + " AND d.flag = 'keep'")
    elif selection is Selection.FAVORITE:
        rows = project.conn.execute(base + " AND d.favorite = 1")
    elif selection is Selection.RATED:
        rows = project.conn.execute(base + " AND COALESCE(d.rating, 0) >= ?", (min_rating,))
    elif selection is Selection.COLLECTION:
        rows = project.conn.execute(
            base + " AND a.id IN (SELECT asset_id FROM collection_items WHERE collection_id = ?) ORDER BY a.id",
            (collection_id,),
        )
    else:
        return list(dict.fromkeys(ids or []))
    return [int(r[0]) for r in rows]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_destination(project: Project, destination: Path) -> Path:
    dest = destination.resolve()
    if dest.exists() and not dest.is_dir():
        raise ExportError(f"đích xuất không phải thư mục: {dest}")
    for (root,) in project.conn.execute("SELECT root_path FROM sources"):
        if dest == Path(root).resolve():
            raise ExportError("không thể xuất thẳng vào thư mục ảnh gốc; hãy chọn hoặc tạo một thư mục con/khác")
    if _is_within(dest, project.folder.resolve()):
        raise ExportError("không thể xuất vào thư mục dự án")
    return dest


def _same_content(src: Path, existing: Path) -> bool:
    """True when ``existing`` is a copy of ``src`` (size + head/tail hash)."""
    try:
        if existing.is_symlink() or not existing.is_file() or existing.stat().st_size != src.stat().st_size:
            return False
        return quick_fingerprint(existing).content_key() == quick_fingerprint(src).content_key()
    except OSError:
        return False


def _choose_stem(
    dest: Path, parent: str, stem: str, members: list[tuple[str, Path]], taken: set[str]
) -> tuple[str, set[int]]:
    """Smallest 'stem', 'stem (1)', ... usable for every file of the group.

    A name is usable when it is free (on disk and in this plan) or already holds
    an identical copy of that very file. Returns the stem and the indexes of the
    members that are already present (to be skipped).
    """
    n = 0
    while True:
        candidate = stem if n == 0 else f"{stem} ({n})"
        present: set[int] = set()
        usable = True
        for i, (suffix, src) in enumerate(members):
            name = str(PurePosixPath(parent, candidate + suffix))
            if name.casefold() in taken:
                usable = False
                break
            target = dest / name
            if target.exists() or target.is_symlink():
                if _same_content(src, target):
                    present.add(i)
                else:
                    usable = False
                    break
        if usable:
            return candidate, present
        n += 1


def plan_export(
    project: Project,
    asset_ids: list[int],
    destination: Path,
    *,
    include_pairs: bool = True,
    keep_folders: bool = False,
) -> ExportPlan:
    dest = _validate_destination(project, destination)
    conn = project.conn
    plan = ExportPlan(dest, [])
    taken: set[str] = set()
    seen: set[int] = set()
    for asset_id in asset_ids:
        if asset_id in seen:
            continue
        row = conn.execute("SELECT pair_group_id FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if row is None:
            continue
        group_ids = [asset_id]
        if include_pairs and row["pair_group_id"] is not None:
            group_ids += [r[0] for r in conn.execute(
                "SELECT id FROM assets WHERE pair_group_id = ? AND id != ? AND status = 'ok' ORDER BY id",
                (row["pair_group_id"], asset_id))]
        members = []
        for gid in group_ids:
            seen.add(gid)
            r = conn.execute(
                """SELECT a.id, a.relative_path, a.capture_time, a.make, a.model, s.root_path, d.flag,
                          COALESCE(d.rating, 0) AS rating, COALESCE(d.favorite, 0) AS favorite
                   FROM assets a JOIN sources s ON s.id = a.source_id
                   LEFT JOIN decisions d ON d.asset_id = ? AND d.subject_id IS NULL
                   WHERE a.id = ?""",
                (asset_id, gid),  # decisions of the pair's primary photo apply to the pair
            ).fetchone()
            src = Path(r["root_path"]) / Path(r["relative_path"])
            if not src.is_file() or src.is_symlink():
                plan.missing.append(r["relative_path"])
                continue
            members.append((r, src))
        if not members:
            continue
        first_rel = PurePosixPath(members[0][0]["relative_path"])
        parent = ""
        if keep_folders:
            source_name = Path(members[0][0]["root_path"]).name
            parent = str(PurePosixPath(source_name, first_rel.parent))
        stem = first_rel.stem
        suffixes = [PurePosixPath(m[0]["relative_path"]).suffix for m in members]
        free, present = _choose_stem(dest, parent, stem, [(sfx, m[1]) for sfx, m in zip(suffixes, members)], taken)
        for i, ((r, src), suffix) in enumerate(zip(members, suffixes)):
            rel = str(PurePosixPath(parent, free + suffix)) if parent else free + suffix
            taken.add(rel.casefold())
            if i in present:
                plan.already_present.append(rel)
                continue
            camera = " ".join(filter(None, [r["make"], r["model"]])) or None
            plan.items.append(ExportItem(
                r["id"], src, rel, src.stat().st_size, r["flag"], int(r["rating"]), bool(r["favorite"]),
                r["capture_time"], camera,
            ))
    return plan


def _copy_exclusive(src: Path, dest_root: Path, rel: str) -> str:
    """Copy into a new file; if the name got taken meanwhile, pick the next free one."""
    target = dest_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    stem, suffix = target.stem, target.suffix
    n = 0
    while True:
        candidate = target if n == 0 else target.with_name(f"{stem} ({n}){suffix}")
        try:
            out = open(candidate, "xb")  # noqa: SIM115 - closed below; 'x' never overwrites
        except FileExistsError:
            n += 1
            continue
        try:
            with out, open(src, "rb") as inp:
                shutil.copyfileobj(inp, out, _CHUNK)
            shutil.copystat(src, candidate)
            if candidate.stat().st_size != src.stat().st_size:
                raise OSError("size mismatch after copy")
        except BaseException:
            candidate.unlink(missing_ok=True)  # only ever our own partial file
            raise
        return candidate.relative_to(dest_root).as_posix()


def run_export(
    plan: ExportPlan,
    *,
    progress: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ExportResult:
    result = ExportResult()
    plan.destination.mkdir(parents=True, exist_ok=True)
    total = len(plan.items)
    done_items: list[tuple[ExportItem, str]] = []
    for i, item in enumerate(plan.items, 1):
        if should_cancel is not None and should_cancel():
            result.cancelled = True
            break
        try:
            actual = _copy_exclusive(item.source, plan.destination, item.dest_relative)
        except OSError as exc:
            result.failed[item.dest_relative] = exc.strerror or str(exc)
        else:
            result.copied.append(actual)
            if actual != item.dest_relative:
                result.renamed[item.dest_relative] = actual
            done_items.append((item, actual))
        if progress is not None:
            progress(i, total)
    if done_items:
        result.manifest_csv, result.manifest_json = _write_manifests(plan.destination, done_items)
    return result


def _write_manifests(dest: Path, done: list[tuple[ExportItem, str]]) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rows = [
        {
            "exported_as": actual, "source_path": str(item.source), "flag": item.flag or "",
            "rating": item.rating, "favorite": item.favorite, "capture_time": item.capture_time or "",
            "camera": item.camera or "", "size_bytes": item.size,
        }
        for item, actual in done
    ]
    folder = dest / MANIFEST_DIR
    folder.mkdir(exist_ok=True)
    csv_path = folder / f"snorlu_export_{stamp}.csv"
    json_path = folder / f"snorlu_export_{stamp}.json"
    # utf-8-sig so Excel on Windows opens Vietnamese paths correctly
    with open(csv_path, "x", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with open(json_path, "x", encoding="utf-8") as fh:
        json.dump({"exported_at": stamp, "files": rows}, fh, ensure_ascii=False, indent=1)
    return csv_path, json_path


def free_space(path: Path) -> int:
    probe = path
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free


def destination_is_empty(path: Path) -> bool:
    return not path.exists() or not any(os.scandir(path))
