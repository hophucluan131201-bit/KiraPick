"""Copy selected photos to a destination folder — originals are never touched (Part 3 spec §3.5–§3.7, §12).

Safety rules:
- copies only; destination files are created with exclusive-create, so an existing file is never overwritten,
  renamed or removed (a free " (n)" name is chosen instead);
- every source is checked again just before it is copied (size, modification time; the SHA-256 when the plan proved
  the content) and hashed from the copy stream; a changed source is reported, never copied silently;
- every copy is read back and compared by SHA-256; a failed, cancelled or unverified copy is removed (only files this
  export created are ever removed);
- a target that seems to hold the file already is compared by full SHA-256 before it is reported present;
- the files of one photo in one folder (a RAW+JPEG pair) keep one stem: when that stem cannot hold them all, the whole
  pair is copied under a new stem; free space is measured again before each pair;
- the destination may not be an imported source folder itself, nor the project folder, nor inside the other folder
  chosen as source;
- a manifest of every operation and issue is written at the end of every run.
"""

from __future__ import annotations

import csv
import errno
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath

from app import __version__
from app.export.errors import ExportError
from app.export.formats import ExportFormat, wanted_kinds
from app.export.layout import (
    MAX_PATH_CHARS,
    UNKNOWN_FOLDER,
    Layout,
    LayoutStats,
    analysed,
    has_suggestion,
    photo_subjects,
    subject_folders,
)
from app.export.photos import Photo, load_photos
from app.export.hashing import CHUNK, HashCache, HashCancelled, sha256_file
from app.export.sources import (  # export lists live in MANIFEST_DIR, not between the photos
    MANIFEST_DIR,
    ExternalIndex,
    Match,
    SourceIdentity,
    SourceSpec,
    check_external_root,
    match_file,
    time_match,
)
from app.ingest.fingerprint import quick_fingerprint
from app.ingest.metadata import PhotoMetadata, read_metadata
from app.storage.project import Project

log = logging.getLogger(__name__)


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
    photos: dict[int, Photo] = field(default_factory=dict)
    layout_stats: LayoutStats | None = None  # Layout.SUBJECTS only
    options: dict[str, str] = field(default_factory=dict)  # source / format / layout, for the manifest

    @property
    def items(self) -> list[ExportOp]:
        """The copies to make (the name callers used before Part 3)."""
        return self.operations

    @property
    def missing(self) -> list[str]:
        """Selected files no longer on disk (path relative to their source folder)."""
        return [i.source_relative or i.stem for i in self.issues if i.status is IssueStatus.MISSING]

    @property
    def to_copy(self) -> list[ExportOp]:
        """Operations whose target does not seem to hold the file yet."""
        return [op for op in self.operations if not op.maybe_present]

    @property
    def already_present(self) -> list[str]:
        """Targets that seem to hold the file already (size + head/tail equal): "có vẻ đã có sẵn". They stay
        operations; run_export compares the whole content before reporting one as already present (CR-P3-A02)."""
        return [op.dest_relative for op in self.operations if op.maybe_present]

    @property
    def estimated_bytes(self) -> int:
        """Bytes the copy writes if every "có vẻ đã có sẵn" target proves identical (spec §12 RV-P3-B-02)."""
        return sum(op.size for op in self.to_copy)

    @property
    def worst_case_bytes(self) -> int:
        """Upper bound: every operation is written at most once, also when seemingly present targets differ and a
        pair is copied again under a new stem."""
        return sum(op.size for op in self.operations)

    @property
    def total_bytes(self) -> int:
        """The estimate (``estimated_bytes``; the name callers used before Part 3) — not an upper bound."""
        return self.estimated_bytes

    @property
    def maybe_present_bytes(self) -> int:
        return sum(op.size for op in self.operations if op.maybe_present)

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
    already_present: list[str] = field(default_factory=list)  # targets proven identical (full SHA-256): not copied
    statuses: dict[str, str] = field(default_factory=dict)  # planned dest_relative -> OpStatus value, every operation
    hashes: dict[str, str] = field(default_factory=dict)  # planned dest_relative -> SHA-256 of the file at the target
    errors: dict[str, str] = field(default_factory=dict)  # planned dest_relative -> why it failed / changed
    notes: dict[str, str] = field(default_factory=dict)  # planned dest_relative -> pair note (spec §12 RV-P3-B-01)
    source_unavailable: bool = False  # the source stopped answering (card ejected): the rest was given up


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
_KINDS = ("raw", "jpeg")  # a photo's files from another folder, RAW first (as the grid shows a pair)
_MATCH_ISSUE = {"missing": IssueStatus.MISSING, "not_matched": IssueStatus.NOT_MATCHED,
                "content_differs": IssueStatus.CONTENT_DIFFERS, "ambiguous": IssueStatus.AMBIGUOUS}


@dataclass(frozen=True, slots=True)
class _Source:
    """One file to copy for a photo, wherever it comes from."""
    asset_id: int  # the matching reference (spec §12 RV-P3-B-03)
    kind: str
    path: Path
    relative: str  # relative to its own root (imported folder or the other folder)
    identity: SourceIdentity
    match: str


def plan_export(
    project: Project,
    asset_ids: list[int],
    destination: Path,
    *,
    source: SourceSpec | None = None,
    fmt: ExportFormat = ExportFormat.RAW_JPEG,
    layout: Layout = Layout.SINGLE,
    confirmations: dict[tuple[int, str], Path] | None = None,
    hashes: HashCache | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ExportPlan:
    """What an export would copy, and what it cannot (Part 3 spec §3.5). Disk access: ``stat`` of the sources and of
    existing targets, the quick fingerprint of a target that may already hold the file; in External mode also the
    content proof (full SHA-256, through ``hashes``) and the capture time of the other folder's candidates."""
    source = source or SourceSpec()
    dest = _validate_destination(project, destination)
    external = source.mode == "external"
    options = {"source": source.mode, "format": fmt.value, "layout": layout.value}
    if external:
        if source.root is None or source.index is None:
            raise ExportError("chưa quét thư mục nguồn — hãy chọn lại thư mục nguồn")
        root = check_external_root(source.root, session_folder=project.folder, destination=dest)
        if root != source.index.root:
            raise ExportError("kết quả quét không thuộc thư mục nguồn đã chọn — hãy quét lại")
        options["source_folder"] = root.name  # the folder's name only, never its full path
    plan = ExportPlan(dest, [], options=options)
    conn = project.conn
    taken: set[str] = set()
    seen: set[int] = set()
    wanted = wanted_kinds(fmt, external=external)
    photos = []
    for photo in load_photos(conn, asset_ids):
        if photo.photo_id in seen:
            continue  # a file of a photo already planned (a pair's JPEG selected with its RAW)
        seen.update(f.asset_id for f in photo.files)
        photos.append(photo)
    found: dict[int, list[_Source]] = {}
    if external:
        assert source.index is not None
        found = _resolve_external(conn, plan, photos, source.index, fmt, wanted, confirmations or {},
                                  hashes or HashCache(), should_cancel)
    names: dict[int, str] = {}
    members: dict[int, tuple[int, ...]] = {}
    if layout is Layout.SUBJECTS:
        names = subject_folders(conn)
        plan.layout_stats = LayoutStats(analysed=analysed(conn))
        members = photo_subjects(conn, photos)
    for photo in photos:
        plan.photos[photo.photo_id] = photo
        folders = [""]
        if plan.layout_stats is not None:
            folders = _subject_folders_of(conn, plan.layout_stats, photo, members, names)
            for folder in folders:
                assigned = plan.layout_stats.assigned_per_folder
                assigned[folder] = assigned.get(folder, 0) + 1
        sources = found.get(photo.photo_id, []) if external else _imported_sources(plan, photo, wanted)
        if sources:
            for folder in folders:
                before = len(plan.operations)
                _plan_folder(plan, photo, sources, folder, taken)
                if plan.layout_stats is not None and len(plan.operations) > before:
                    exportable = plan.layout_stats.exportable_per_folder
                    exportable[folder] = exportable.get(folder, 0) + 1
    return plan


def _imported_sources(plan: ExportPlan, photo: Photo, wanted: frozenset[str]) -> list[_Source]:
    """The photo's own files of the wanted kinds that are still on disk (Imported mode)."""
    files = [f for f in photo.files if f.kind in wanted]
    if not files:
        for kind in sorted(wanted - {"other"}):
            plan.issues.append(ExportIssue(photo.photo_id, photo.stem, kind, IssueStatus.MISSING_FORMAT,
                                           f"Thiếu {_KIND_LABEL[kind]}"))
        return []
    out = []
    for f in files:
        if not f.path.is_file() or f.path.is_symlink():
            plan.issues.append(ExportIssue(photo.photo_id, photo.stem, f.kind, IssueStatus.MISSING,
                                           "không còn trên ổ đĩa", f.relative_path))
            continue
        st = f.path.stat()
        out.append(_Source(f.asset_id, f.kind, f.path, f.relative_path, SourceIdentity(st.st_size, st.st_mtime_ns),
                           "imported"))
    return out


def _recorded_hashes(conn: sqlite3.Connection, photos: list[Photo], hashes: HashCache) -> dict[int, str]:
    """``assets.sha256`` where the import recorded one: seeds the cache while the file is unchanged."""
    files = {f.asset_id: f for p in photos for f in p.files}
    out: dict[int, str] = {}
    ids = list(files)
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for aid, sha, size, mtime_ns in conn.execute(
                f"SELECT id, sha256, size, mtime_ns FROM assets WHERE sha256 IS NOT NULL AND id IN "
                f"({','.join('?' * len(chunk))})", chunk):
            out[aid] = sha
            hashes.seed(files[aid].path, size, mtime_ns, sha)
    return out


def _resolve_external(conn: sqlite3.Connection, plan: ExportPlan, photos: list[Photo], index: ExternalIndex,
                      fmt: ExportFormat, wanted: frozenset[str], confirmations: dict[tuple[int, str], Path],
                      hashes: HashCache, should_cancel: Callable[[], bool] | None) -> dict[int, list[_Source]]:
    """Each photo's wanted files on the other folder (External mode: nothing comes from the imported folders)."""
    recorded = _recorded_hashes(conn, photos, hashes)
    matches: dict[int, dict[str, Match]] = {}
    for photo in photos:
        if fmt is ExportFormat.RAW_JPEG and not {f.kind for f in photo.files} & set(_KINDS):
            plan.issues.append(ExportIssue(photo.photo_id, photo.stem, None, IssueStatus.MISSING_FORMAT,
                                           "định dạng này chỉ lấy được từ thư mục đã nhập"))
            continue
        matches[photo.photo_id] = {
            kind: match_file(photo, kind, index, hashes=hashes, confirmed=confirmations.get((photo.photo_id, kind)),
                             recorded_sha=recorded, should_cancel=should_cancel)
            for kind in _KINDS if kind in wanted}
    # A capture-time match is evidence for one photo only: a file that is the only valid candidate of several
    # photos (same name, same camera, within 2 s) is not copied for any of them without the user's choice.
    claims: dict[Path, list[tuple[int, str]]] = {}
    for photo_id, by_kind in matches.items():
        for kind, m in by_kind.items():
            if m.method == "time" and m.file is not None:
                claims.setdefault(m.file, []).append((photo_id, kind))
    for owners in claims.values():
        if len(owners) > 1:
            for photo_id, kind in owners:
                m = matches[photo_id][kind]
                matches[photo_id][kind] = Match("ambiguous", None, None, m.candidates, 0, None, m.reference_asset_id,
                                                "file này khớp với nhiều ảnh")
    out: dict[int, list[_Source]] = {}
    for photo in photos:
        by_kind = matches.get(photo.photo_id)
        if by_kind is None:
            continue
        matched = [k for k, m in by_kind.items() if m.status == "matched"]
        for kind, m in by_kind.items():
            if m.status == "matched":
                continue
            detail = f"{_KIND_LABEL[kind]} không có tại nguồn được chọn" if m.status == "missing" and matched \
                else m.detail
            plan.issues.append(ExportIssue(photo.photo_id, photo.stem, kind, _MATCH_ISSUE[m.status], detail, None,
                                           m.candidates))
        out[photo.photo_id] = [
            _Source(m.reference_asset_id, k, m.source.path, m.source.relative, m.identity, m.method)
            for k in matched if (m := by_kind[k]).source is not None and m.identity is not None and m.method]
    return out


def _subject_folders_of(conn: sqlite3.Connection, stats: LayoutStats, photo: Photo,
                        members: dict[int, tuple[int, ...]], names: dict[int, str]) -> list[str]:
    """The subject folders of one photo (each subject's, or "Chưa xác định"), counted in ``stats``."""
    subjects = sorted((names[s] for s in members.get(photo.photo_id, ()) if s in names), key=str.casefold)
    if not subjects:
        if has_suggestion(conn, photo):
            stats.unknown_suggested += 1
        else:
            stats.unknown_other += 1
        return [UNKNOWN_FOLDER]
    if len(subjects) > 1:
        stats.multi_subject += 1
    return subjects


def _plan_folder(plan: ExportPlan, photo: Photo, sources: list[_Source], folder: str, taken: set[str]) -> None:
    """The files of one photo into one folder, under one stem (a pair stays a pair)."""
    stem = PurePosixPath(sources[0].relative).stem
    suffixes = [PurePosixPath(s.relative).suffix for s in sources]
    free, present = _choose_stem(plan.destination, folder, stem,
                                 [(sfx, s.path) for sfx, s in zip(suffixes, sources)], taken)
    for i, (s, suffix) in enumerate(zip(sources, suffixes)):
        rel = str(PurePosixPath(folder, free + suffix)) if folder else free + suffix
        is_present = i in present
        if rel.casefold() in taken:  # two files of one group with the same extension: the later keeps its own name
            own, own_present = _choose_stem(plan.destination, folder, PurePosixPath(s.relative).stem,
                                            [(suffix, s.path)], taken)
            rel = str(PurePosixPath(folder, own + suffix)) if folder else own + suffix
            is_present = 0 in own_present
        taken.add(rel.casefold())
        if len(str(plan.destination / rel)) > MAX_PATH_CHARS:
            plan.issues.append(ExportIssue(photo.photo_id, photo.stem, s.kind, IssueStatus.PATH_TOO_LONG,
                                           f"đường dẫn quá dài (> {MAX_PATH_CHARS} ký tự): {rel}", s.relative))
            continue
        plan.operations.append(ExportOp(
            photo.photo_id, s.asset_id, s.kind, s.path, s.relative, folder, rel, s.identity.size, s.match, s.identity,
            maybe_present=is_present,
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


FAIL_FAST_AFTER = 3  # consecutive "source not reachable" errors before the rest is given up
_GONE_ERRNO = {errno.ENOENT, errno.ENODEV, errno.EIO, errno.ENXIO}
_GONE_WINERROR = {2, 3, 21, 1117}  # file / path not found, device not ready, I/O device error
SOURCE_GONE = "Nguồn không còn truy cập được"
SOURCE_CHANGED = "File nguồn đã thay đổi sau khi xem trước"
NO_SPACE = "Không đủ dung lượng trống ở đích"
VERIFY_FAILED = "bản chép không khớp khi kiểm tra lại (đã xoá bản chép)"
NOTE_RELOCATED = "cặp được chép dưới tên mới vì ở đích đã có file cùng tên khác nội dung"
NOTE_INCOMPLETE = "cặp không đầy đủ ở đích"
_MAX_STEMS = 10_000


class OpStatus(str, Enum):
    COPIED = "copied"
    ALREADY_PRESENT = "already_present"
    FAILED = "failed"
    NOT_STARTED = "not_started"  # cancelled before this file
    SOURCE_CHANGED = "source_changed"


class _SourceGone(OSError):
    """The source cannot be reached (card ejected, drive gone)."""


class _SourceChanged(Exception):
    pass


def _gone(exc: OSError) -> bool:
    return exc.errno in _GONE_ERRNO or getattr(exc, "winerror", None) in _GONE_WINERROR


def _source_error(exc: OSError) -> OSError:
    return _SourceGone(exc.errno, exc.strerror) if _gone(exc) else exc


@dataclass(frozen=True, slots=True)
class _Copied:
    sha256: str  # of the bytes read from the source, as they were written
    size: int
    source_mtime_ns: int  # of the source after reading


class CopyCancelled(ExportError):
    """The user stopped the export inside a file: that file (ours) was removed."""


def _copy_exclusive(src: Path, dest_root: Path, rel: str, *,
                    should_cancel: Callable[[], bool] | None = None) -> _Copied:
    """Copy ``src`` into the new file ``dest_root/rel`` (FileExistsError when the name is taken: never overwritten),
    hashing the bytes from the same stream; ``should_cancel`` is asked between 1 MiB chunks (CopyCancelled). A
    failed or cancelled copy removes only the file it created."""
    target = dest_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    out = open(target, "xb")  # noqa: SIM115 - closed below; 'x' never overwrites
    try:
        digest, size = hashlib.sha256(), 0
        with out:
            try:
                inp = open(src, "rb")  # noqa: SIM115 - closed below
            except OSError as exc:
                raise _source_error(exc) from exc
            with inp:
                while True:
                    try:
                        chunk = inp.read(CHUNK)
                    except OSError as exc:
                        raise _source_error(exc) from exc
                    if not chunk:
                        break
                    digest.update(chunk)
                    out.write(chunk)
                    size += len(chunk)
                    if should_cancel is not None and should_cancel():
                        raise CopyCancelled("đã dừng giữa một file")
                after = os.fstat(inp.fileno())
        shutil.copystat(src, target)
        return _Copied(digest.hexdigest(), size, after.st_mtime_ns)
    except BaseException:
        target.unlink(missing_ok=True)  # only ever our own new file
        raise


def _revalidate(op: ExportOp) -> None:
    """The source is still the file that was planned (regular file, same size and modification time)."""
    try:
        st = os.lstat(op.source)
    except OSError as exc:
        raise _source_error(exc) from exc
    if not stat.S_ISREG(st.st_mode) or (st.st_size, st.st_mtime_ns) != (op.identity.size, op.identity.mtime_ns):
        raise _SourceChanged


def _base_stem(op: ExportOp) -> str:
    return PurePosixPath(op.source_relative).stem


@dataclass(slots=True)
class _Run:
    plan: ExportPlan
    result: ExportResult
    hashes: HashCache
    read_meta: Callable[..., PhotoMetadata]
    should_cancel: Callable[[], bool] | None
    planned: set[str]  # every planned target name (casefold): never taken by a relocated group
    gone_in_a_row: int = 0

    def set(self, op: ExportOp, status: OpStatus, error: str | None = None) -> None:
        self.result.statuses[op.dest_relative] = status.value
        if error:
            self.result.errors[op.dest_relative] = error
            if status is OpStatus.FAILED:
                self.result.failed[op.dest_relative] = error
        if status in (OpStatus.COPIED, OpStatus.ALREADY_PRESENT):
            self.gone_in_a_row = 0

    def gone(self, op: ExportOp) -> None:
        self.set(op, OpStatus.FAILED, SOURCE_GONE)
        self.gone_in_a_row += 1
        if self.gone_in_a_row >= FAIL_FAST_AFTER:
            self.result.source_unavailable = True


def _present(run: _Run, op: ExportOp) -> str | None:
    """The SHA-256 when the existing target holds exactly the source's bytes (full hash of both), else None."""
    target = run.plan.destination / op.dest_relative
    try:
        if target.is_symlink() or not target.is_file() or target.stat().st_size != op.identity.size:
            return None
        source_sha = op.identity.sha256 or run.hashes.sha256(op.source, should_cancel=run.should_cancel)
        target_sha = sha256_file(target, should_cancel=run.should_cancel)
    except HashCancelled:
        raise
    except OSError:
        return None
    return source_sha if target_sha == source_sha else None


def _free_for(run: _Run, ops: list[ExportOp]) -> bool:
    try:
        return free_space(run.plan.destination) >= sum(op.size for op in ops)
    except OSError:
        return True  # unknown: the copy itself reports a full disk


def _write(run: _Run, members: list[tuple[ExportOp, str]]) -> bool:
    """Copy each member to its name. False (after removing what this call created) when a name was taken meanwhile;
    any other failure is reported for that member only."""
    created: list[tuple[ExportOp, str, str]] = []
    for op, rel in members:
        if run.result.source_unavailable:
            run.set(op, OpStatus.FAILED, SOURCE_GONE)
            continue
        try:
            copied = _copy_exclusive(op.source, run.plan.destination, rel, should_cancel=run.should_cancel)
        except (FileExistsError, CopyCancelled) as exc:
            for _op, done_rel, _sha in created:  # one attempt writes a pair whole or not at all
                (run.plan.destination / done_rel).unlink(missing_ok=True)
            if isinstance(exc, CopyCancelled):
                raise
            return False
        except _SourceGone:
            run.gone(op)
            continue
        except OSError as exc:
            run.set(op, OpStatus.FAILED, exc.strerror or str(exc))
            continue
        problem = _check_copy(run, op, rel, copied)
        if problem is not None:
            (run.plan.destination / rel).unlink(missing_ok=True)
            status = OpStatus.FAILED if problem == VERIFY_FAILED else OpStatus.SOURCE_CHANGED
            run.set(op, status, problem)
            continue
        created.append((op, rel, copied.sha256))
    for op, rel, sha in created:
        run.result.copied.append(rel)
        run.result.copied_ids.append(op.asset_id)
        run.result.hashes[op.dest_relative] = sha
        if rel != op.dest_relative:
            run.result.renamed[op.dest_relative] = rel
        run.set(op, OpStatus.COPIED)
    return True


def _check_copy(run: _Run, op: ExportOp, rel: str, copied: _Copied) -> str | None:
    """None when the new file is a faithful copy of the planned source; otherwise why it is not."""
    if copied.size != op.identity.size or copied.source_mtime_ns != op.identity.mtime_ns:
        return SOURCE_CHANGED
    if op.identity.sha256 is not None and copied.sha256 != op.identity.sha256:
        return SOURCE_CHANGED
    target = run.plan.destination / rel
    try:
        if target.stat().st_size != copied.size or sha256_file(target) != copied.sha256:
            return VERIFY_FAILED
    except OSError:
        return VERIFY_FAILED
    if op.match == "time":
        photo = run.plan.photos.get(op.photo_id)
        if photo is None or time_match(photo, run.read_meta(target)) is not True:
            return SOURCE_CHANGED
    return None


def _relocate(run: _Run, ops: list[ExportOp]) -> None:
    """Write the whole group under the smallest new stem free for every member (spec §12 RV-P3-B-01)."""
    if not _free_for(run, ops):
        for op in ops:
            run.set(op, OpStatus.FAILED, NO_SPACE)
        return
    folder = ops[0].folder
    stems, used = [], set()
    for op in ops:  # one stem for the group; a second file with the same extension keeps its own name
        suffix = PurePosixPath(op.dest_relative).suffix.casefold()
        stems.append(_base_stem(ops[0]) if suffix not in used else _base_stem(op))
        used.add(suffix)
    for n in range(1, _MAX_STEMS):
        names, seen = [], set()
        for op, stem in zip(ops, stems):
            name = f"{stem} ({n}){PurePosixPath(op.dest_relative).suffix}"
            while name.casefold() in seen:
                name = f"{PurePosixPath(name).stem}_{len(seen)}{PurePosixPath(name).suffix}"
            seen.add(name.casefold())
            names.append(str(PurePosixPath(folder, name)) if folder else name)
        if any(rel.casefold() in run.planned for rel in names):
            continue
        targets = [run.plan.destination / rel for rel in names]
        if any(t.exists() or t.is_symlink() for t in targets):
            continue
        if any(len(str(t)) > MAX_PATH_CHARS for t in targets):
            for op in ops:
                run.set(op, OpStatus.FAILED, f"đường dẫn quá dài (> {MAX_PATH_CHARS} ký tự)")
            return
        if _write(run, list(zip(ops, names))):
            return
    for op in ops:
        run.set(op, OpStatus.FAILED, "không tìm được tên trống ở đích")


def _run_group(run: _Run, group: list[ExportOp]) -> None:
    live: list[ExportOp] = []
    for op in group:
        try:
            _revalidate(op)
        except _SourceGone:
            run.gone(op)
            continue
        except _SourceChanged:
            run.set(op, OpStatus.SOURCE_CHANGED, SOURCE_CHANGED)
            continue
        except OSError as exc:
            run.set(op, OpStatus.FAILED, exc.strerror or str(exc))
            continue
        live.append(op)
    if not live:
        return
    present: dict[str, str] = {}
    differs = False
    for op in live:
        if op.maybe_present:
            sha = _present(run, op)
            if sha is not None:
                present[op.dest_relative] = sha
            else:
                target = run.plan.destination / op.dest_relative
                differs = differs or target.exists() or target.is_symlink()  # gone since the preview: name is free
    to_write = [op for op in live if op.dest_relative not in present]
    if not differs:
        if to_write and not _free_for(run, to_write):
            for op in to_write:
                run.set(op, OpStatus.FAILED, NO_SPACE)
        elif not _write(run, [(op, op.dest_relative) for op in to_write]):
            _relocate_group(run, live, present)  # a planned name was taken after the preview: the whole group moves
            return
        _mark_present(run, live, present)
        return
    _relocate_group(run, live, present)  # an existing file of the same name differs: the whole group gets a new stem


def _mark_present(run: _Run, ops: list[ExportOp], present: dict[str, str]) -> None:
    for op in ops:
        if op.dest_relative in present:
            run.result.failed.pop(op.dest_relative, None)
            run.result.errors.pop(op.dest_relative, None)
            run.result.already_present.append(op.dest_relative)
            run.result.hashes[op.dest_relative] = present[op.dest_relative]
            run.set(op, OpStatus.ALREADY_PRESENT)


def _relocate_group(run: _Run, ops: list[ExportOp], present: dict[str, str]) -> None:
    _relocate(run, ops)
    if not any(run.result.statuses.get(op.dest_relative) == OpStatus.COPIED.value for op in ops):
        _mark_present(run, ops, present)  # nothing new written: the verified files stay what they are
    _note_relocated(run, ops, present)


def _note_relocated(run: _Run, ops: list[ExportOp], present: dict[str, str]) -> None:
    if len(ops) > 1 and present:
        for op in ops:
            if run.result.statuses.get(op.dest_relative) == OpStatus.COPIED.value:
                run.result.notes[op.dest_relative] = NOTE_RELOCATED


def _note_incomplete(run: _Run, group: list[ExportOp]) -> None:
    """A photo whose files do not all end at the destination under one stem is marked in the manifest."""
    if len(group) < 2:
        return
    final = []
    for op in group:
        status = run.result.statuses.get(op.dest_relative)
        if status == OpStatus.COPIED.value:
            final.append(PurePosixPath(run.result.renamed.get(op.dest_relative, op.dest_relative)).stem)
        elif status == OpStatus.ALREADY_PRESENT.value:
            final.append(PurePosixPath(op.dest_relative).stem)
        else:
            final.append(None)
    if any(s is not None for s in final) and (None in final or len(set(final)) > 1):
        for op in group:
            run.result.notes.setdefault(op.dest_relative, NOTE_INCOMPLETE)


def _groups(ops: list[ExportOp]) -> list[list[ExportOp]]:
    """Consecutive operations of one photo into one folder (a RAW+JPEG pair) form one copy group."""
    out: list[list[ExportOp]] = []
    for op in ops:
        if out and (out[-1][0].photo_id, out[-1][0].folder) == (op.photo_id, op.folder):
            out[-1].append(op)
        else:
            out.append([op])
    return out


def run_export(
    plan: ExportPlan,
    *,
    progress: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    options: Mapping[str, str] | None = None,
    hashes: HashCache | None = None,
    read_meta: Callable[..., PhotoMetadata] = read_metadata,
    should_stop: Callable[[], bool] | None = None,
) -> ExportResult:
    """Copy the plan's files (spec §3.6, §12): sources revalidated, copies verified by SHA-256, existing files never
    overwritten, a pair kept under one stem; a manifest of every operation and issue is written at the end.

    ``should_cancel`` (the user's Dừng) is asked between photos and between 1 MiB chunks: a file being copied is
    removed. ``should_stop`` (closing the app / switching folder) is asked between photos only: the current photo
    is finished first, as the window's question says."""
    result = ExportResult()
    plan.destination.mkdir(parents=True, exist_ok=True)
    run = _Run(plan, result, hashes or HashCache(), read_meta, should_cancel,
               {op.dest_relative.casefold() for op in plan.operations})
    total = len(plan.operations)
    done = 0
    for group in _groups(plan.operations):
        if result.source_unavailable:
            break
        if (should_cancel is not None and should_cancel()) or (should_stop is not None and should_stop()):
            result.cancelled = True
            break
        try:
            _run_group(run, group)
        except (HashCancelled, CopyCancelled):
            result.cancelled = True  # this group's files written by the stopped attempt were removed
            break
        _note_incomplete(run, group)
        done += len(group)
        if progress is not None:
            progress(done, total)
    for op in plan.operations:
        if op.dest_relative not in result.statuses:
            if result.source_unavailable:
                run.set(op, OpStatus.FAILED, SOURCE_GONE)
            else:
                run.set(op, OpStatus.NOT_STARTED)
    try:
        result.manifest_csv, result.manifest_json = _write_manifests(plan, result, dict(options or {}))
    except OSError as exc:
        log.warning("export list not written: %s", type(exc).__name__)
    return result


MANIFEST_COLUMNS = ("status", "exported_as", "folder", "photo", "kind", "source", "match", "size_bytes", "sha256",
                    "flag", "rating", "favorite", "capture_time", "camera", "error", "note")


def _source_label(op: ExportOp) -> str:
    """The source as '<its root folder's name>/<path below it>' — never the full path of the user's drives."""
    root = Path(op.source)
    for _part in PurePosixPath(op.source_relative).parts:
        root = root.parent
    return f"{root.name}/{op.source_relative}" if root.name else op.source_relative


def _photo_fields(photo: Photo | None) -> dict[str, object]:
    return {
        "flag": (photo.flag if photo else None) or "", "rating": photo.rating if photo else 0,
        "favorite": photo.favorite if photo else False,
        "capture_time": photo.capture_time.isoformat() if photo and photo.capture_time else "",
        "camera": (photo.camera if photo else None) or "",
    }


def _manifest_rows(plan: ExportPlan, result: ExportResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for op in plan.operations:
        status = result.statuses[op.dest_relative]
        photo = plan.photos.get(op.photo_id)
        exported = {OpStatus.COPIED.value: result.renamed.get(op.dest_relative, op.dest_relative),
                    OpStatus.ALREADY_PRESENT.value: op.dest_relative}.get(status, "")
        rows.append({
            "status": status, "exported_as": exported, "folder": op.folder, "photo": photo.stem if photo else "",
            "kind": op.kind, "source": _source_label(op), "match": op.match, "size_bytes": op.size,
            "sha256": result.hashes.get(op.dest_relative, ""), **_photo_fields(photo),
            "error": result.errors.get(op.dest_relative, ""), "note": result.notes.get(op.dest_relative, ""),
        })
    for issue in plan.issues:
        rows.append({
            "status": issue.status.value, "exported_as": "", "folder": "", "photo": issue.stem,
            "kind": issue.kind or "", "source": issue.source_relative or "", "match": "", "size_bytes": "",
            "sha256": "", **_photo_fields(plan.photos.get(issue.photo_id)), "error": issue.detail,
            "note": f"{len(issue.candidates)} file ứng viên" if issue.candidates else "",
        })
    return rows


def _write_manifests(plan: ExportPlan, result: ExportResult, options: dict[str, str]) -> tuple[Path, Path]:
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    rows = _manifest_rows(plan, result)
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    folder = plan.destination / MANIFEST_DIR
    folder.mkdir(exist_ok=True)
    name, n = f"kirapick_export_{stamp}", 1
    while (folder / f"{name}.csv").exists() or (folder / f"{name}.json").exists():  # two exports in one second
        n += 1
        name = f"kirapick_export_{stamp}_{n}"
    csv_path = folder / f"{name}.csv"
    json_path = folder / f"{name}.json"
    # utf-8-sig so Excel on Windows opens Vietnamese names correctly
    with open(csv_path, "x", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    header = {"app_version": __version__, "exported_at": now.isoformat(timespec="seconds"),
              "options": {**options, **plan.options}, "counts": counts}
    with open(json_path, "x", encoding="utf-8") as fh:
        json.dump({**header, "rows": rows}, fh, ensure_ascii=False, indent=1)
    return csv_path, json_path


def free_space(path: Path) -> int:
    probe = path
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free


def destination_is_empty(path: Path) -> bool:
    return not path.exists() or not any(os.scandir(path))
