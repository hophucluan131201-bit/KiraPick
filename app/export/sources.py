"""Where the export's files come from: the imported folders or another folder (Part 3 spec §3.3).

The other folder (a memory card, a backup drive) is only read: the scan lists names, sizes and modification times
without opening any file; nothing is created, renamed or changed there."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Literal

from app.export.errors import ExportError
from app.export.formats import file_kind
from app.export.hashing import HashCache
from app.export.photos import Photo, PhotoFile
from app.ingest.fingerprint import quick_fingerprint
from app.ingest.metadata import PhotoMetadata, read_metadata

MANIFEST_DIR = "_kirapick_danh_sach"
_SKIPPED_DIRS = {"$recycle.bin", "system volume information", MANIFEST_DIR}
_HIDDEN = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 4)
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_PROGRESS_EVERY = 256


class ScanCancelled(ExportError):
    pass


MATCH_TOLERANCE_S = Decimal("2.0")  # the import's RAW+JPEG pairing tolerance; never widened


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """A source file as it was when planned or confirmed; checked again before it is copied."""
    size: int
    mtime_ns: int
    sha256: str | None = None  # known when the plan proved the content (content match)


@dataclass(frozen=True, slots=True)
class ExternalFile:
    path: Path
    kind: str  # raw | jpeg
    size: int
    mtime_ns: int
    relative: str  # POSIX path relative to the scanned root


@dataclass(slots=True)
class ExternalIndex:
    root: Path
    by_stem: dict[str, list[ExternalFile]] = field(default_factory=dict)  # stem.casefold() -> files, by path
    files: int = 0  # files indexed
    skipped: int = 0  # entries left out: unsupported, hidden, links, unreadable folders

    def candidates(self, stem: str, kind: str) -> list[ExternalFile]:
        """Files with exactly this base name (case-insensitive) and kind."""
        return [f for f in self.by_stem.get(stem.casefold(), ()) if f.kind == kind]


@dataclass(frozen=True, slots=True)
class SourceSpec:
    mode: Literal["imported", "external"] = "imported"
    root: Path | None = None
    index: ExternalIndex | None = None  # the scan of ``root`` (planning never rescans)


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def check_external_root(root: Path, *, session_folder: Path, destination: Path | None) -> Path:
    """The resolved root, or ExportError when it cannot be a source for this export."""
    if not root.exists():
        raise ExportError("không tìm thấy thư mục nguồn (thẻ nhớ đã rút, hoặc ổ đĩa chưa cắm?)")
    if not root.is_dir():
        raise ExportError("nguồn đã chọn không phải là thư mục")
    resolved = root.resolve()
    if _within(resolved, session_folder.resolve()):
        raise ExportError("không thể lấy ảnh từ thư mục dữ liệu phiên làm việc của KiraPick")
    if destination is not None:
        dest = destination.resolve()
        if _within(dest, resolved):
            raise ExportError("thư mục đích nằm trong thư mục nguồn — hãy chọn thư mục đích ở chỗ khác")
        if _within(resolved, dest):
            raise ExportError("thư mục nguồn nằm trong thư mục đích — hãy chọn thư mục đích ở chỗ khác")
    return resolved


def _is_link(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(entry.path):
        return True
    attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & _REPARSE)


def _is_hidden(entry: os.DirEntry[str]) -> bool:
    if entry.name.startswith("."):
        return True
    attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & _HIDDEN)


def scan_external(
    root: Path,
    *,
    session_folder: Path,
    destination: Path | None,
    progress: Callable[[int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ExternalIndex:
    """Index RAW and JPEG files under ``root`` by base name. Links, junctions and reparse points are never followed;
    hidden / system folders and KiraPick's own lists are skipped; no file is opened."""
    resolved = check_external_root(root, session_folder=session_folder, destination=destination)
    index = ExternalIndex(resolved)
    seen = 0
    pending = [resolved]
    while pending:
        if should_cancel is not None and should_cancel():
            raise ScanCancelled("đã huỷ quét thư mục nguồn")
        folder = pending.pop()
        try:
            with os.scandir(folder) as it:
                entries = list(it)
        except OSError:
            if folder == resolved:
                raise ExportError("không đọc được thư mục nguồn") from None
            index.skipped += 1
            continue
        for entry in entries:
            try:
                if _is_link(entry) or _is_hidden(entry):
                    index.skipped += 1
                    if not entry.is_dir(follow_symlinks=False):
                        seen += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.casefold() in _SKIPPED_DIRS:
                        index.skipped += 1
                    else:
                        pending.append(Path(entry.path))
                    continue
                seen += 1
                kind = file_kind(entry.name)
                if not entry.is_file(follow_symlinks=False) or kind not in ("raw", "jpeg"):
                    index.skipped += 1
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError:
                index.skipped += 1
                continue
            path = Path(entry.path)
            ext = ExternalFile(path, kind, st.st_size, st.st_mtime_ns, path.relative_to(resolved).as_posix())
            index.by_stem.setdefault(PurePosixPath(entry.name).stem.casefold(), []).append(ext)
            index.files += 1
            if progress is not None and seen % _PROGRESS_EVERY == 0:
                progress(seen)
    for files in index.by_stem.values():
        files.sort(key=lambda f: f.relative)  # the same index whatever order the file system lists entries in
    if progress is not None:
        progress(seen)
    return index


# --- matching (spec §3.3 points 2–6, §12 RV-P3-B-03) -----------------------------------------------------------

MatchStatus = Literal["matched", "missing", "not_matched", "content_differs", "ambiguous"]
MatchMethod = Literal["content", "time", "manual"]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A file of the other folder with the photo's base name and the wanted kind, as shown for review."""
    path: Path
    relative: str
    size: int
    capture_time: datetime | None  # read for cross-format candidates only
    camera: str | None


@dataclass(frozen=True, slots=True)
class Match:
    status: MatchStatus
    source: ExternalFile | None  # the chosen file (status "matched")
    method: MatchMethod | None
    candidates: tuple[Candidate, ...]
    duplicates: int  # other candidates proven identical to the chosen one (full SHA-256)
    identity: SourceIdentity | None
    reference_asset_id: int  # what the file was matched against: the imported file of that kind, else the photo
    detail: str = ""

    @property
    def file(self) -> Path | None:
        return self.source.path if self.source is not None else None


def _camera(make: str | None, model: str | None) -> str | None:
    return " ".join(filter(None, [make, model])) or None


def _same_camera(a: str | None, b: str | None) -> bool | None:
    if not a or not b:
        return None
    return " ".join(a.casefold().split()) == " ".join(b.casefold().split())


def _fraction(subsec: str | None) -> Decimal | None:
    digits = (subsec or "").strip()
    return Decimal("0." + digits) if digits.isdigit() else None


def time_difference(a: datetime | None, a_subsec: str | None, b: datetime | None, b_subsec: str | None) -> Decimal | None:
    """|a − b| in seconds, exact; subseconds used only when both sides have them; None when a time is unknown."""
    if a is None or b is None:
        return None
    delta = (a - b).days * 86_400 + (a - b).seconds  # whole seconds (capture times carry none below)
    diff = Decimal(delta)
    fa, fb = _fraction(a_subsec), _fraction(b_subsec)
    if fa is not None and fb is not None:
        diff += fa - fb
    return abs(diff)


def _meta_time(meta: PhotoMetadata) -> datetime | None:
    try:
        return datetime.fromisoformat(meta.datetime_original) if meta.datetime_original else None
    except ValueError:
        return None


def time_match(photo: Photo, meta: PhotoMetadata) -> bool | None:
    """True: same shot by capture time (≤ 2.0 s) and camera; False: proven different; None: unknown."""
    if _same_camera(photo.camera, _camera(meta.make, meta.model)) is False:
        return False
    diff = time_difference(photo.capture_time, photo.subsec, _meta_time(meta), meta.subsec)
    if diff is None:
        return None
    return diff <= MATCH_TOLERANCE_S


def _shortest(files: list[ExternalFile]) -> ExternalFile:
    return min(files, key=lambda f: (len(f.relative), f.relative))


def _reference(photo: Photo, kind: str) -> PhotoFile | None:
    return next((f for f in photo.files if f.kind == kind), None)


def match_file(
    photo: Photo,
    kind: str,
    index: ExternalIndex,
    *,
    hashes: HashCache,
    read_meta: Callable[..., PhotoMetadata] = read_metadata,
    fingerprint: Callable[[Path], object] = quick_fingerprint,
    confirmed: Path | None = None,
    recorded_sha: dict[int, str] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Match:
    """The file of ``kind`` for ``photo`` on the other folder. With an imported file of that kind the candidate must
    hold the same bytes (full SHA-256); without one, the same capture time (≤ 2.0 s) and camera. ``confirmed`` (the
    user's choice for an ambiguous case) counts only when it is one of the candidates."""
    ref = _reference(photo, kind)
    ref_id = ref.asset_id if ref is not None else photo.photo_id
    stem = PurePosixPath(ref.relative_path).stem if ref is not None else photo.stem
    files = index.candidates(stem, kind)
    if not files:
        return Match("missing", None, None, (), 0, None, ref_id, "Không tìm thấy")
    if ref is not None:
        return _match_content(ref, files, hashes, fingerprint, confirmed, recorded_sha or {}, should_cancel)
    return _match_time(photo, files, read_meta, confirmed)


def _plain(files: list[ExternalFile]) -> tuple[Candidate, ...]:
    return tuple(Candidate(f.path, f.relative, f.size, None, None) for f in files)


def _confirmed(files: list[ExternalFile], confirmed: Path | None) -> ExternalFile | None:
    if confirmed is None:
        return None
    return next((f for f in files if f.path == confirmed), None)


def _match_content(ref: PhotoFile, files: list[ExternalFile], hashes: HashCache, fingerprint: Callable[[Path], object],
                   confirmed: Path | None, recorded: dict[int, str],
                   should_cancel: Callable[[], bool] | None) -> Match:
    passed = []
    for f in files:
        if f.size != ref.size:
            continue
        try:
            if fingerprint(f.path).quick_hash == ref.quick_hash:  # type: ignore[attr-defined]
                passed.append(f)
        except OSError:
            continue
    if not passed:
        return Match("content_differs", None, None, _plain(files), 0, None, ref.asset_id, "Khác nội dung")
    try:
        ref_sha = hashes.sha256(ref.path, should_cancel=should_cancel)
    except FileNotFoundError:
        ref_sha = recorded.get(ref.asset_id)
    except OSError:
        ref_sha = None
    if ref_sha is None:
        chosen = _confirmed(passed, confirmed)
        if chosen is not None:
            return Match("matched", chosen, "manual", _plain(passed), 0, SourceIdentity(chosen.size, chosen.mtime_ns),
                         ref.asset_id)
        return Match("ambiguous", None, None, _plain(passed), 0, None, ref.asset_id,
                     "file đã nhập không còn trên ổ đĩa — không so được toàn bộ nội dung")
    proven = []
    for f in passed:
        try:
            if hashes.sha256(f.path, should_cancel=should_cancel) == ref_sha:
                proven.append(f)
        except OSError:
            continue
    if not proven:
        return Match("content_differs", None, None, _plain(files), 0, None, ref.asset_id, "Khác nội dung")
    chosen = _shortest(proven)
    return Match("matched", chosen, "content", _plain(proven), len(proven) - 1,
                 SourceIdentity(chosen.size, chosen.mtime_ns, ref_sha), ref.asset_id,
                 f"{len(proven) - 1} bản giống hệt" if len(proven) > 1 else "")


def _match_time(photo: Photo, files: list[ExternalFile], read_meta: Callable[..., PhotoMetadata],
                confirmed: Path | None) -> Match:
    valid, unknown, shown = [], [], []
    for f in files:
        meta = read_meta(f.path)
        verdict = time_match(photo, meta)
        candidate = Candidate(f.path, f.relative, f.size, _meta_time(meta), _camera(meta.make, meta.model))
        if verdict is True:
            valid.append(f)
        elif verdict is None:
            unknown.append(f)
        if verdict is not False:
            shown.append(candidate)
    if len(valid) == 1 and not unknown:
        f = valid[0]
        return Match("matched", f, "time", tuple(shown), 0, SourceIdentity(f.size, f.mtime_ns), photo.photo_id)
    if not valid and not unknown:
        return Match("not_matched", None, None, (), 0, None, photo.photo_id, "Không khớp giờ chụp hoặc máy ảnh")
    chosen = _confirmed(valid + unknown, confirmed)
    if chosen is not None:
        return Match("matched", chosen, "manual", tuple(shown), 0, SourceIdentity(chosen.size, chosen.mtime_ns),
                     photo.photo_id)
    return Match("ambiguous", None, None, tuple(shown), 0, None, photo.photo_id,
                 "không đọc được giờ chụp" if unknown and len(valid) < 2 else "nhiều file cùng khớp")
