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
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath

from app.core.errors import KiraPickError
from app.export.formats import ExportFormat, wanted_kinds
from app.export.layout import Layout
from app.export.photos import Photo, PhotoFile, load_photos
from app.export.sources import SourceSpec
from app.ingest.fingerprint import quick_fingerprint
from app.storage.project import Project

_CHUNK = 1024 * 1024
MANIFEST_DIR = "_kirapick_danh_sach"  # export lists live here, not between the photos


class ExportError(KiraPickError):
    pass


class Selection(str, Enum):
    KEEP = "keep"
    FAVORITE = "favorite"
    RATED = "rated"
    IDS = "ids"
    COLLECTION = "collection"  # a client's pick list


class IssueStatus(str, Enum):
    MISSING = "missing"  # the file is no longer on disk
    MISSING_FORMAT = "missing_format"  # the photo has no file of the chosen format
    NOT_MATCHED = "not_matched"
    CONTENT_DIFFERS = "content_differs"
    AMBIGUOUS = "ambiguous"
    PATH_TOO_LONG = "path_too_long"


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """A source file as it was when planned; checked again before it is copied."""
    size: int
    mtime_ns: int
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ExportOp:
    """One file copy."""
    photo_id: int
    asset_id: int  # the imported file of that kind (the photo's primary when the kind was not imported)
    kind: str
    source: Path
    source_relative: str
    folder: str  # "" = the destination folder itself
    dest_relative: str  # POSIX path relative to the destination folder
    size: int
    match: str  # imported | content | time | manual
    identity: SourceIdentity
    maybe_present: bool = False  # the target seems to hold this file already (checked fully when copying)


@dataclass(frozen=True, slots=True)
class ExportIssue:
    photo_id: int
    stem: str
    kind: str | None
    status: IssueStatus
    detail: str
    source_relative: str | None = None
    candidates: tuple[object, ...] = ()


@dataclass(slots=True)
class ExportPlan:
    destination: Path
    operations: list[ExportOp]
    issues: list[ExportIssue] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)  # identical copy already at the destination
    photos: dict[int, Photo] = field(default_factory=dict)

    @property
    def items(self) -> list[ExportOp]:
        """The copies to make (the name callers used before Part 3)."""
        return self.operations

    @property
    def missing(self) -> list[str]:
        """Selected files no longer on disk (path relative to their source folder)."""
        return [i.source_relative or i.stem for i in self.issues if i.status is IssueStatus.MISSING]

    @property
    def total_bytes(self) -> int:
        return sum(op.size for op in self.operations)

    @property
    def photos_planned(self) -> int:
        return len({op.photo_id for op in self.operations})

    def counts(self) -> dict[IssueStatus, int]:
        out: dict[IssueStatus, int] = {}
        for issue in self.issues:
            out[issue.status] = out.get(issue.status, 0) + 1
        return out


@dataclass(slots=True)
class ExportResult:
    copied: list[str] = field(default_factory=list)
    renamed: dict[str, str] = field(default_factory=dict)  # planned -> actual (race with another program)
    failed: dict[str, str] = field(default_factory=dict)
    cancelled: bool = False
    manifest_csv: Path | None = None
    manifest_json: Path | None = None
    copied_ids: list[int] = field(default_factory=list)  # asset id of each entry of `copied`, same order


def select_assets(
    project: Project, selection: Selection, *, min_rating: int = 1, ids: list[int] | None = None,
    collection_id: int | None = None,
) -> list[int]:
    """Photo-level selection (RAW of a pair stands for the pair)."""
    return select_ids(project.conn, selection, min_rating=min_rating, ids=ids, collection_id=collection_id)


def select_ids(
    conn: sqlite3.Connection, selection: Selection, *, min_rating: int = 1, ids: list[int] | None = None,
    collection_id: int | None = None,
) -> list[int]:
    """``select_assets`` on a connection (the bottom bar's size estimate uses the same selection)."""
    base = """SELECT a.id FROM assets a LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
              WHERE a.status = 'ok'"""
    if selection is Selection.KEEP:
        rows = conn.execute(base + " AND d.flag = 'keep'")
    elif selection is Selection.FAVORITE:
        rows = conn.execute(base + " AND d.favorite = 1")
    elif selection is Selection.RATED:
        rows = conn.execute(base + " AND COALESCE(d.rating, 0) >= ?", (min_rating,))
    elif selection is Selection.COLLECTION:
        rows = conn.execute(
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


_KIND_LABEL = {"raw": "RAW", "jpeg": "JPEG"}


def plan_export(
    project: Project,
    asset_ids: list[int],
    destination: Path,
    *,
    source: SourceSpec | None = None,
    fmt: ExportFormat = ExportFormat.RAW_JPEG,
    layout: Layout = Layout.SINGLE,
    confirmations: dict[tuple[int, str], Path] | None = None,
) -> ExportPlan:
    """What an export would copy, and what it cannot (Part 3 spec §3.5). Disk access: ``stat`` of the sources and of
    existing targets, and the quick fingerprint of a target that may already hold the file."""
    source = source or SourceSpec()
    if source.mode != "imported":
        raise ExportError("xuất từ nguồn khác chưa có trong bản này")
    if layout is not Layout.SINGLE:
        raise ExportError("xuất theo chủ thể chưa có trong bản này")
    dest = _validate_destination(project, destination)
    plan = ExportPlan(dest, [])
    taken: set[str] = set()
    seen: set[int] = set()
    wanted = wanted_kinds(fmt, external=False)
    for photo in load_photos(project.conn, asset_ids):
        if photo.photo_id in seen:
            continue  # a file of a photo already planned (a pair's JPEG selected with its RAW)
        seen.update(f.asset_id for f in photo.files)
        plan.photos[photo.photo_id] = photo
        files = [f for f in photo.files if f.kind in wanted]
        if not files:
            for kind in sorted(wanted - {"other"}):
                plan.issues.append(ExportIssue(photo.photo_id, photo.stem, kind, IssueStatus.MISSING_FORMAT,
                                               f"Thiếu {_KIND_LABEL[kind]}"))
            continue
        present = []
        for f in files:
            if not f.path.is_file() or f.path.is_symlink():
                plan.issues.append(ExportIssue(photo.photo_id, photo.stem, f.kind, IssueStatus.MISSING,
                                               "không còn trên ổ đĩa", f.relative_path))
                continue
            present.append(f)
        if present:
            _plan_folder(plan, photo, present, "", taken)
    return plan


def _plan_folder(plan: ExportPlan, photo: Photo, files: list[PhotoFile], folder: str, taken: set[str]) -> None:
    """The files of one photo into one folder, under one stem (a pair stays a pair)."""
    stem = PurePosixPath(files[0].relative_path).stem
    suffixes = [PurePosixPath(f.relative_path).suffix for f in files]
    free, present = _choose_stem(plan.destination, folder, stem, [(sfx, f.path) for sfx, f in zip(suffixes, files)],
                                 taken)
    for i, (f, suffix) in enumerate(zip(files, suffixes)):
        rel = str(PurePosixPath(folder, free + suffix)) if folder else free + suffix
        taken.add(rel.casefold())
        if i in present:
            plan.already_present.append(rel)
            continue
        st = f.path.stat()
        plan.operations.append(ExportOp(
            photo.photo_id, f.asset_id, f.kind, f.path, f.relative_path, folder, rel, st.st_size, "imported",
            SourceIdentity(st.st_size, st.st_mtime_ns),
        ))


def estimated_bytes(conn: sqlite3.Connection, asset_ids: list[int], *, fmt: ExportFormat) -> int:
    """Bytes an export of these photos would copy from the imported folders into one folder, from the sizes recorded at
    import (no disk access): the files plan_export picks."""
    total = 0
    seen: set[int] = set()
    wanted = wanted_kinds(fmt, external=False)
    for photo in load_photos(conn, asset_ids):
        if photo.photo_id in seen:
            continue
        seen.update(f.asset_id for f in photo.files)
        total += sum(f.size for f in photo.files if f.kind in wanted)
    return total


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
    done_items: list[tuple[ExportOp, str]] = []
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
            result.copied_ids.append(item.asset_id)
            if actual != item.dest_relative:
                result.renamed[item.dest_relative] = actual
            done_items.append((item, actual))
        if progress is not None:
            progress(i, total)
    if done_items:
        result.manifest_csv, result.manifest_json = _write_manifests(plan.destination, done_items, plan.photos)
    return result


def _write_manifests(dest: Path, done: list[tuple[ExportOp, str]], photos: dict[int, Photo]) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rows = []
    for item, actual in done:
        photo = photos.get(item.photo_id)
        rows.append({
            "exported_as": actual, "source_path": str(item.source), "flag": (photo.flag if photo else None) or "",
            "rating": photo.rating if photo else 0, "favorite": photo.favorite if photo else False,
            "capture_time": photo.capture_time.isoformat() if photo and photo.capture_time else "",
            "camera": (photo.camera if photo else None) or "", "size_bytes": item.size,
        })
    folder = dest / MANIFEST_DIR
    folder.mkdir(exist_ok=True)
    csv_path = folder / f"kirapick_export_{stamp}.csv"
    json_path = folder / f"kirapick_export_{stamp}.json"
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
