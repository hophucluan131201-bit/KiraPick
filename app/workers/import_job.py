"""Resumable folder import: register files, then build metadata + thumbnails.

Phases:
1. **register** (single thread, cheap): scan, fingerprint new/changed files,
   detect duplicates, mark vanished files ``missing`` (never deleted: decisions
   survive), queue the ``ingest`` stage per asset.
2. **ingest** (thread pool): decode the preview, write the thumbnail into the
   project cache, read metadata. Results are committed one by one, so killing
   the app loses at most the in-flight files; the next run resumes from
   ``stage_status``.
3. **pair**: rebuild RAW+JPEG pairs for the source from capture times.

Source photos are only ever opened for reading.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.errors import ImageReadError
from app.ingest.fingerprint import quick_fingerprint
from app.ingest.formats import MediaKind, format_for
from app.ingest.metadata import read_metadata
from app.ingest.preview import load_image
from app.ingest.scanner import PairStatus, ScanEntry, classify_pair, find_pair_candidates, scan_folder
from app.storage.project import Project, utc_now

log = logging.getLogger(__name__)

STAGE = "ingest"
STAGE_VERSION = 1  # bump when thumbnail rendering or metadata extraction changes
THUMB_LONG_SIDE = 400
THUMB_QUALITY = 85
MAX_ATTEMPTS = 2
_BATCH = 200


@dataclass(slots=True)
class ImportProgress:
    phase: str  # "scan" | "register" | "ingest" | "pair"
    done: int
    total: int


@dataclass(slots=True)
class ImportSummary:
    source_id: int
    job_id: int
    found: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    missing: int = 0
    duplicates: int = 0
    ingested: int = 0
    failed: int = 0
    pairs: int = 0
    cancelled: bool = False
    unsupported_extensions: dict[str, int] = field(default_factory=dict)
    skipped_links: int = 0


@dataclass(frozen=True, slots=True)
class _IngestResult:
    asset_id: int
    thumb_name: str | None
    thumb_size: tuple[int, int] | None
    source: str | None
    full_size: tuple[int, int] | None
    metadata: dict | None
    error: str | None


ProgressFn = Callable[[ImportProgress], None]
CancelFn = Callable[[], bool]


def _noop_progress(_: ImportProgress) -> None:
    pass


def _never() -> bool:
    return False


class ImportJob:
    def __init__(self, project: Project, root: Path, *, workers: int = 3) -> None:
        self.project = project
        self.root = root.resolve(strict=True)
        self.workers = max(1, workers)
        self.thumb_dir = project.cache_dir / "thumbs"

    # ---------------------------------------------------------------- run
    def run(self, progress: ProgressFn = _noop_progress, should_cancel: CancelFn = _never) -> ImportSummary:
        conn = self.project.conn
        source_id = self._ensure_source()
        now = utc_now()
        job_id = int(
            conn.execute(
                "INSERT INTO jobs (kind, state, params_json, created_at, updated_at) VALUES ('import', 'running', ?, ?, ?)",
                (json.dumps({"source_id": source_id}), now, now),
            ).lastrowid
        )
        summary = ImportSummary(source_id, job_id)
        try:
            progress(ImportProgress("scan", 0, 0))
            report = scan_folder(
                self.root,
                should_cancel=should_cancel,
                exclude_dirs=(self.project.folder,),
            )
            summary.unsupported_extensions = dict(report.unsupported_extensions)
            summary.skipped_links = report.skipped_links
            if report.cancelled:
                return self._finish(summary, cancelled=True)
            summary.found = len(report.entries)
            self._register(source_id, report.entries, summary, progress, should_cancel)
            if summary.cancelled:
                return self._finish(summary, cancelled=True)
            self._ingest(source_id, summary, progress, should_cancel)
            if summary.cancelled:
                return self._finish(summary, cancelled=True)
            self._pair(source_id, report.entries, summary, progress)
            conn.execute("UPDATE sources SET last_scan_at = ? WHERE id = ?", (utc_now(), source_id))
            return self._finish(summary, cancelled=False)
        except Exception as exc:
            conn.execute(
                "UPDATE jobs SET state = 'failed', error = ?, updated_at = ? WHERE id = ?",
                (f"{type(exc).__name__}: {exc}"[:500], utc_now(), job_id),
            )
            raise

    def _finish(self, summary: ImportSummary, *, cancelled: bool) -> ImportSummary:
        summary.cancelled = cancelled
        self.project.conn.execute(
            "UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?",
            ("paused" if cancelled else "done", utc_now(), summary.job_id),
        )
        return summary

    def _ensure_source(self) -> int:
        conn = self.project.conn
        row = conn.execute("SELECT id FROM sources WHERE root_path = ?", (str(self.root),)).fetchone()
        if row:
            return int(row["id"])
        return int(
            conn.execute(
                "INSERT INTO sources (root_path, added_at) VALUES (?, ?)", (str(self.root), utc_now())
            ).lastrowid
        )

    # ----------------------------------------------------------- register
    def _register(
        self,
        source_id: int,
        entries: list[ScanEntry],
        summary: ImportSummary,
        progress: ProgressFn,
        should_cancel: CancelFn,
    ) -> None:
        conn = self.project.conn
        known = {
            row["relative_path"]: row
            for row in conn.execute(
                "SELECT id, relative_path, size, mtime_ns, status FROM assets WHERE source_id = ?", (source_id,)
            )
        }
        seen: set[str] = set()
        for start in range(0, len(entries), _BATCH):
            if should_cancel():
                summary.cancelled = True
                return
            with self.project.transaction():
                for entry in entries[start : start + _BATCH]:
                    seen.add(entry.relative_path)
                    self._register_one(source_id, entry, known.get(entry.relative_path), summary)
            progress(ImportProgress("register", min(start + _BATCH, len(entries)), len(entries)))

        vanished = [row["id"] for rel, row in known.items() if rel not in seen and row["status"] != "missing"]
        with self.project.transaction() as tx:
            tx.executemany(
                "UPDATE assets SET status = 'missing', updated_at = ? WHERE id = ?",
                [(utc_now(), asset_id) for asset_id in vanished],
            )
        summary.missing = len(vanished)

    def _register_one(
        self, source_id: int, entry: ScanEntry, existing: sqlite3.Row | None, summary: ImportSummary
    ) -> None:
        conn = self.project.conn
        now = utc_now()
        try:
            st = os.stat(entry.path)
        except OSError:
            return  # vanished between scan and stat; next scan marks it missing
        if existing is not None:
            row = existing
            if row["size"] == st.st_size and row["mtime_ns"] == st.st_mtime_ns:
                summary.unchanged += 1
                if row["status"] == "missing":  # came back unchanged
                    conn.execute("UPDATE assets SET status = 'pending', updated_at = ? WHERE id = ?", (now, row["id"]))
                    self._queue(row["id"], now)
                return
            fp = quick_fingerprint(entry.path)
            conn.execute(
                """UPDATE assets SET size = ?, mtime_ns = ?, quick_hash = ?, sha256 = NULL, status = 'pending',
                   error = NULL, duplicate_of = NULL, updated_at = ? WHERE id = ?""",
                (fp.size, fp.mtime_ns, fp.quick_hash, now, row["id"]),
            )
            conn.execute("DELETE FROM previews WHERE asset_id = ?", (row["id"],))
            self._queue(row["id"], now)
            summary.changed += 1
            return

        fp = quick_fingerprint(entry.path)
        info = entry.format
        dup = conn.execute(
            "SELECT id FROM assets WHERE size = ? AND quick_hash = ? AND status NOT IN ('missing', 'duplicate') LIMIT 1",
            (fp.size, fp.quick_hash),
        ).fetchone()
        status = "duplicate" if dup else "pending"
        asset_id = conn.execute(
            """INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, duplicate_of, added_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id, entry.relative_path, info.extension, info.kind.value,
                "raster" if info.kind is MediaKind.RASTER else info.level.value,
                fp.size, fp.mtime_ns, fp.quick_hash, status, dup["id"] if dup else None, now, now,
            ),
        ).lastrowid
        if dup:
            summary.duplicates += 1
        else:
            self._queue(int(asset_id), now)
            summary.new += 1

    def _queue(self, asset_id: int, now: str) -> None:
        self.project.conn.execute(
            """INSERT INTO stage_status (asset_id, stage, stage_version, state, attempts, updated_at)
               VALUES (?, ?, ?, 'pending', 0, ?)
               ON CONFLICT (asset_id, stage) DO UPDATE SET stage_version = excluded.stage_version,
               state = 'pending', attempts = 0, error = NULL, updated_at = excluded.updated_at""",
            (asset_id, STAGE, STAGE_VERSION, now),
        )

    # ------------------------------------------------------------- ingest
    def _pending(self, source_id: int) -> list[tuple[int, Path]]:
        rows = self.project.conn.execute(
            """SELECT a.id, a.relative_path FROM stage_status st JOIN assets a ON a.id = st.asset_id
               WHERE a.source_id = ? AND st.stage = ? AND a.status NOT IN ('missing', 'duplicate')
                 AND (st.state = 'pending' OR st.stage_version < ?
                      OR (st.state = 'failed' AND st.attempts < ?))
               ORDER BY a.relative_path""",
            (source_id, STAGE, STAGE_VERSION, MAX_ATTEMPTS),
        ).fetchall()
        return [(int(r["id"]), self.root / Path(r["relative_path"])) for r in rows]

    def _ingest(self, source_id: int, summary: ImportSummary, progress: ProgressFn, should_cancel: CancelFn) -> None:
        todo = self._pending(source_id)
        total = len(todo)
        if not total:
            return
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
        done = 0
        progress(ImportProgress("ingest", 0, total))
        queue = iter(todo)
        in_flight: set[Future[_IngestResult]] = set()
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="ingest") as pool:
            while True:
                while len(in_flight) < self.workers * 2 and not summary.cancelled:
                    if should_cancel():
                        summary.cancelled = True
                        break
                    item = next(queue, None)
                    if item is None:
                        break
                    in_flight.add(pool.submit(self._ingest_one, *item))
                if not in_flight:
                    break
                finished, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
                for fut in finished:
                    self._store(fut.result(), summary)
                    done += 1
                progress(ImportProgress("ingest", done, total))

    def _ingest_one(self, asset_id: int, path: Path) -> _IngestResult:
        """Runs in a worker thread: no database access here."""
        try:
            loaded = load_image(path, max_long_side=THUMB_LONG_SIDE, min_long_side=THUMB_LONG_SIDE, with_metadata=True)
        except ImageReadError as exc:
            # Metadata is still useful for a file whose pixels cannot be decoded.
            meta = read_metadata(path).to_json_dict() if format_for(path) else None
            return _IngestResult(asset_id, None, None, None, None, meta, f"{exc.reason}: {exc.detail}"[:300])
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the import
            log.warning("unexpected ingest failure (%s)", type(exc).__name__)
            return _IngestResult(asset_id, None, None, None, None, None, f"internal_error: {type(exc).__name__}")

        name = f"thumbs/{asset_id:08d}.jpg"
        target = self.project.cache_dir / name
        tmp = target.with_suffix(".tmp")
        loaded.image.save(tmp, "JPEG", quality=THUMB_QUALITY, optimize=True)
        os.replace(tmp, target)  # atomic: a crash never leaves a half-written thumbnail
        meta = loaded.metadata.to_json_dict() if loaded.metadata else None
        return _IngestResult(asset_id, name, loaded.image.size, loaded.source.value, loaded.full_size, meta, None)

    def _store(self, r: _IngestResult, summary: ImportSummary) -> None:
        now = utc_now()
        meta = r.metadata or {}
        with self.project.transaction() as tx:
            tx.execute(
                """UPDATE assets SET status = ?, error = ?, width = COALESCE(?, width), height = COALESCE(?, height),
                   orientation = ?, capture_time = ?, subsec = ?, make = ?, model = ?, lens = ?, exif_json = ?,
                   updated_at = ? WHERE id = ?""",
                (
                    "error" if r.error else "ok", r.error,
                    r.full_size[0] if r.full_size else None, r.full_size[1] if r.full_size else None,
                    meta.get("orientation"), meta.get("datetime_original"), meta.get("subsec"),
                    meta.get("make"), meta.get("model"), meta.get("lens"),
                    json.dumps(meta, ensure_ascii=False) if meta else None, now, r.asset_id,
                ),
            )
            if r.thumb_name and r.thumb_size and r.source:
                tx.execute(
                    """INSERT INTO previews (asset_id, kind, file_name, width, height, source, render_version)
                       VALUES (?, 'thumb', ?, ?, ?, ?, ?)
                       ON CONFLICT (asset_id, kind) DO UPDATE SET file_name = excluded.file_name, width = excluded.width,
                       height = excluded.height, source = excluded.source, render_version = excluded.render_version""",
                    (r.asset_id, r.thumb_name, r.thumb_size[0], r.thumb_size[1], r.source, STAGE_VERSION),
                )
            tx.execute(
                """UPDATE stage_status SET state = ?, stage_version = ?, attempts = attempts + 1, error = ?, updated_at = ?
                   WHERE asset_id = ? AND stage = ?""",
                ("failed" if r.error else "done", STAGE_VERSION, r.error, now, r.asset_id, STAGE),
            )
        if r.error:
            summary.failed += 1
        else:
            summary.ingested += 1

    # --------------------------------------------------------------- pair
    def _pair(self, source_id: int, entries: list[ScanEntry], summary: ImportSummary, progress: ProgressFn) -> None:
        conn = self.project.conn
        rows = {
            r["relative_path"]: r
            for r in conn.execute(
                "SELECT id, relative_path, capture_time, status FROM assets WHERE source_id = ?", (source_id,)
            )
        }
        def when(rel: str) -> datetime | None:
            value = rows[rel]["capture_time"] if rel in rows else None
            return datetime.fromisoformat(value) if value else None

        with self.project.transaction() as tx:
            old = [r[0] for r in tx.execute(
                "SELECT DISTINCT pair_group_id FROM assets WHERE source_id = ? AND pair_group_id IS NOT NULL", (source_id,)
            )]
            tx.execute("UPDATE assets SET pair_group_id = NULL WHERE source_id = ?", (source_id,))
            tx.executemany("DELETE FROM pair_groups WHERE id = ?", [(g,) for g in old])
            for cand in find_pair_candidates(entries):
                raw, jpeg = cand.raw.relative_path, cand.jpeg.relative_path
                # Only files whose metadata was read can be paired: a duplicate or
                # undecodable file has no capture time and would pair by name alone.
                if raw not in rows or jpeg not in rows or {rows[raw]["status"], rows[jpeg]["status"]} != {"ok"}:
                    continue
                status = classify_pair(when(raw), when(jpeg))
                if status is PairStatus.TIME_MISMATCH:
                    continue
                group = tx.execute("INSERT INTO pair_groups (status) VALUES (?)", (status.value,)).lastrowid
                tx.executemany(
                    "UPDATE assets SET pair_group_id = ? WHERE id = ?",
                    [(group, rows[raw]["id"]), (group, rows[jpeg]["id"])],
                )
                summary.pairs += 1
        progress(ImportProgress("pair", summary.pairs, summary.pairs))
