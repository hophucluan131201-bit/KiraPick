# KiraPick Part 3 — Advanced Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export kept photos from the imported folder or another folder (card / drive), as RAW, JPEG or both, into one
folder or one folder per subject, with a full preview, manual confirmation of unsure matches, a complete manifest, and
a "copy file names" utility.

**Architecture:** Approach A: the existing safe copy core (`app/export/copy_export.py`) stays; small new modules
compute, per photo, its files (`photos.py`), the wanted kinds (`formats.py`), where each file comes from
(`sources.py`), and which folders it goes to (`layout.py`); `plan_export` combines them into operations + issues;
`run_export` copies, verifies and writes manifest v2. The dialog gets three independent radio groups and two tabs.

**Tech Stack:** Python 3.12/3.13, PySide6 6.12, SQLite (schema v7, unchanged), pytest + pytest-qt, ExifRead
(`app.ingest.metadata`).

**Spec:** `docs/superpowers/specs/2026-10-30-kirapick-advanced-export-design.md` (rev 2). Plan rev 2 (design
checkpoint 1 corrections CR-P3-D01…D04 and the source-revalidation case). Section numbers below
(§3.3 …) refer to it.

## Global Constraints

- Schema stays v7; no table or column is added (spec D8). Confirmations of ambiguous matches live in memory only.
- Sources (imported folders and the external folder) are never written: no mkdir, no temp file, no rename, no
  metadata change; files opened read-only.
- Never overwrite a destination file; exclusive create; remove only our own partial / failed file.
- Capture-time tolerance is exactly `2.0` s (`MATCH_TOLERANCE_S = 2.0`), never widened; base names compared with
  `str.casefold()`; quick hash = `app.ingest.fingerprint.quick_fingerprint` (size + 64 KiB head + 64 KiB tail) is a
  **filter only**; byte identity is claimed only after equal full SHA-256 (`app/export/hashing.py`, 1 MiB chunks,
  never on the GUI thread, once per file per dialog).
- Every operation carries its source identity (`size`, `mtime_ns`, `sha256 | None`); it is revalidated before and
  during the copy; a mismatch is `source_changed`, never a silent copy.
- Folder names: forbidden `< > : " / \ | ? *` and control chars → `_`; reserved `CON PRN AUX NUL COM1–9 LPT1–9`
  (also with extension) → suffix `_`; max 60 chars; NFC; **no letter and no digit after sanitising → `Chủ thể <id>`**;
  duplicates → ` (#<id>)`; reserved folder `Chưa xác định`; target absolute path ≤ 259 chars.
- Subject membership: `assignment IN ('auto','manual')`; `subject_id` resolved through `subjects.merged_into` to the
  surviving subject (≤ 32 steps; cycle / missing row → unresolved).
- Other rasters (TIFF/PNG/HEIC): copied only by Imported + RAW_JPEG; never indexed / matched externally; not part of
  JPEG; no conversion anywhere.
- Default options: Source = imported, Format = RAW + JPEG, Layout = one folder; QSettings keys `export/source`,
  `export/format`, `export/layout`, `export/external_root`; old `export/include_pairs` (any value) → `raw_jpeg`, then
  removed; `false` sets `export/migration_notice_pending` (one-time notice: a behaviour change, never described as
  preserving the old preference). The old "Giữ cấu trúc thư mục con" box is removed.
- No AI model runs during export; subject assignments only read (`assignment IN ('auto','manual')`,
  `merged_into IS NULL`).
- No network code; the network-import guard test must cover the new modules.
- Vietnamese UI copy as in spec §4; logs never contain photo paths or names.
- Part 2 (Compare) code is not touched; the Gate / shutdown architecture is not changed (one `Work` entry is added).
- Each task: own commit, targeted tests; full suite + GUI suite at each batch checkpoint; no skip / xfail to hide a
  failure; no release, tag, installer or build.

## Review Focus

- The external folder chosen is the imported folder itself (or contains it): every file matches by content; nothing
  is copied twice; the destination must not be inside it — Task 6 test `test_external_root_is_the_imported_folder`.
- A card holding the same stem several times after counter restarts (`DSC_0001` from three shoots): only the one
  within 2 s matches, the others are "Không khớp", never "Không chắc" — Task 6 test `test_counter_restart_three_times`.
- A subject renamed between two exports: the second export creates the new folder name and copies there; the old
  folder is left untouched — Task 4 test `test_rename_between_exports_uses_new_folder`.
- The user changes scope / format / source while a scan or plan runs: the late result is dropped, the preview shows
  the newest choice only — Task 9 test `test_late_plan_result_is_dropped`.
- The card is ejected between preview and copy: the copy reports "Nguồn không còn truy cập được", keeps copied
  files, manifest lists `failed` / `not_started` — Task 7 test `test_source_vanishes_after_preview`.

---

## Batch A — core pipeline on the imported source (review checkpoint after Task 4)

### Task 1: Compatibility baseline (golden tests of today's export) — risk: low

**Files:**
- Create: `tests/unit/test_export_compat.py`
- Create: `tests/fixtures_export.py` (shared fixture builder)

**Interfaces:**
- Produces: `make_export_session(tmp_path) -> ExportFixture` with fields `project, ids: dict[str, int]` (keys
  `pair`, `pair_missing_jpeg`, `raw_only`, `jpeg_only`, `tiff`, `png`, `rejected`, `undecided`, `fav`, `rated3`,
  `collected`), `dest: Path`; `snapshot(plan) -> list[tuple[str, str]]` = sorted `(source name, dest_relative)` plus
  `already_present`, `missing`.

- [ ] **Step 1:** Write `test_today_plan_matches_golden[scope]` for scopes KEEP, FAVORITE, RATED(3), IDS, COLLECTION
  against today's `plan_export(include_pairs=True)` (the equivalence claim is for `include_pairs=True` only; also
  record `golden_include_pairs_false` — today's `include_pairs=False` result: pair → NEF only — used by Task 3 to
  document the difference): golden lists written inline (pair → `DSC_0001.NEF`,
  `DSC_0001.JPG` same stem; missing JPEG reported in `missing`; RAW-only, JPEG-only, TIFF, PNG one file each;
  rejected / undecided never in KEEP); plus a pre-created different `DSC_0001.NEF` at the destination → ` (1)` for both
  files of the pair; an identical pre-copied file → `already_present`.
- [ ] **Step 2:** `test_export_changes_nothing_but_destination`: snapshot of tables `decisions, occurrences,
  view_rotation, assets, subjects` and SHA-256 of every source file before/after `run_export` — equal.
- [ ] **Step 3:** Run `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/unit/test_export_compat.py` —
  Expected: PASS on today's code (this is the baseline Task 3 must keep).
- [ ] **Step 4:** Commit `"Export: compatibility baseline of today's plans (part 3 task 1)"`.

### Task 2: Photos and formats — risk: low

**Files:**
- Create: `app/export/formats.py`, `app/export/photos.py`
- Test: `tests/unit/test_export_photos.py`

**Interfaces:**
- Produces:
  - `class ExportFormat(str, Enum): RAW_JPEG = "raw_jpeg"; RAW = "raw"; JPEG = "jpeg"`
  - `def file_kind(path: Path | str) -> Literal["raw", "jpeg", "other"] | None` (None = unsupported)
  - `def wanted_kinds(fmt: ExportFormat, *, external: bool) -> frozenset[str]` — imported RAW_JPEG =
    `{"raw","jpeg","other"}`; external RAW_JPEG = `{"raw","jpeg"}`; RAW = `{"raw"}`; JPEG = `{"jpeg"}`
  - `@dataclass(frozen=True) PhotoFile(asset_id: int, kind: str, path: Path, relative_path: str, source_root: Path,
    size: int, quick_hash: str)`
  - `@dataclass(frozen=True) Photo(photo_id: int, stem: str, files: tuple[PhotoFile, ...], capture_time: datetime |
    None, subsec: str | None, camera: str | None, flag: str | None, rating: int, favorite: bool)`
  - `def load_photos(conn, photo_ids: list[int]) -> list[Photo]` — order of `photo_ids`; files of the pair group with
    `status = 'ok'`, primary first; decisions from the primary (subject_id NULL).

- [ ] **Step 1:** Tests: `test_file_kind` (`.NEF`/`.cr3` raw, `.JPG`/`.jpeg` jpeg, `.tif`/`.png`/`.heic` other,
  `.txt` None); `test_wanted_kinds` (the table above); `test_load_photos_pair_and_singles` on the Task 1 fixture (pair →
  2 files, NEF first; stem `DSC_0001`; capture_time / camera of the primary; missing-on-disk JPEG still listed —
  existence is checked by the planner); `test_load_photos_fallback_time` (primary without capture_time takes the
  partner's).
- [ ] **Step 2:** Run — FAIL (modules missing).
- [ ] **Step 3:** Implement both modules (batched `IN` queries of ≤ 500 ids like `exports.photo_count`).
- [ ] **Step 4:** Run — PASS. Commit `"Export: photos and formats (part 3 task 2)"`.

### Task 3: Planner with operations, issues and formats (imported source) — risk: high

**Files:**
- Modify: `app/export/copy_export.py` (`ExportPlan`, `plan_export`, `export_groups`, `estimated_bytes`)
- Modify: `app/storage/stats.py` (`counts(conn, fmt: ExportFormat)`), `app/ui/main_window.py` (`_update_counts` reads
  `export/format`), `app/ui/bottom_bar.py` (text "gồm JPEG kèm" only for RAW_JPEG; tooltip per spec §7)
- Test: `tests/unit/test_export_plan.py`, update `tests/unit/test_stats_vs_export.py`

**Interfaces:**
- Consumes: Task 2.
- Produces:
  - `@dataclass(frozen=True) SourceIdentity(size: int, mtime_ns: int, sha256: str | None)`
  - `@dataclass(frozen=True) ExportOp(photo_id: int, asset_id: int, kind: str, source: Path, source_relative: str,
    folder: str, dest_relative: str, size: int, match: Literal["imported","content","time","manual"],
    identity: SourceIdentity, maybe_present: bool)` — `maybe_present` = the target exists with equal size + quick
    fingerprint (full check at copy time, Task 7); `ExportPlan.already_present` becomes the list of
    `dest_relative` with `maybe_present` (preview label "có vẻ đã có sẵn")
  - `class IssueStatus(str, Enum): MISSING, MISSING_FORMAT, NOT_MATCHED, CONTENT_DIFFERS, AMBIGUOUS, PATH_TOO_LONG`
  - `@dataclass(frozen=True) ExportIssue(photo_id: int, stem: str, kind: str | None, status: IssueStatus, detail: str,
    candidates: tuple[Candidate, ...] = ())` (`Candidate` from Task 6; empty tuple until then)
  - `ExportPlan(destination, operations: list[ExportOp], issues: list[ExportIssue], already_present: list[str])` with
    properties `items` (alias of operations, kept for callers), `missing` (stems of MISSING issues), `total_bytes`,
    `photos_planned`, `counts() -> dict[IssueStatus, int]`
  - `plan_export(project, photo_ids, destination, *, source: SourceSpec | None = None, fmt: ExportFormat =
    ExportFormat.RAW_JPEG, layout: Layout = Layout.SINGLE, confirmations: Mapping[tuple[int, str], Path] | None = None)
    -> ExportPlan` (`source=None` = imported; `Layout` from Task 4 — this task accepts only SINGLE)
  - `estimated_bytes(conn, photo_ids, *, fmt: ExportFormat) -> int`
- The old keywords `include_pairs` and `keep_folders` are removed; `ExportItem` is replaced by `ExportOp` (update
  `jobs.py`, `export_dialog.py`, manifests minimally so the app still runs).

- [ ] **Step 1:** Port Task 1's golden tests to the new call `plan_export(..., fmt=RAW_JPEG)` and assert the same
  snapshot (CR-P3-02 proof, `include_pairs=True` only); `test_include_pairs_false_differs_and_is_documented`: the new
  RAW_JPEG plan differs from `golden_include_pairs_false` exactly by the pairs' JPEGs. Add `test_formats[fmt]`: RAW →
  pair copies NEF only, JPEG-only photo → `MISSING_FORMAT` issue "Thiếu RAW"; JPEG → pair copies JPG only (stem kept),
  RAW-only → "Thiếu JPEG", TIFF/PNG → MISSING_FORMAT; RAW_JPEG → TIFF/PNG copied (legacy); `test_identity_recorded`
  (size, mtime_ns of each source at planning; sha256 None for imported);
  `test_missing_on_disk_is_an_issue`; `test_estimated_bytes_per_format` equals the sum of the plan's operation sizes on
  the imported source for all three formats; `test_bottom_bar_follows_format` (stats.counts).
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement. Stems per folder via the existing `_choose_stem`; the members of one photo in one folder
  are the wanted kinds it has.
- [ ] **Step 4:** Run the new tests, `tests/unit/test_export*.py`, `tests/integration/test_export_runs.py`,
  `tests/gui/test_review_notes_t15.py`, `tests/gui/test_shutdown_callbacks.py` — PASS.
- [ ] **Step 5:** Commit `"Export: planner with operations, issues and formats (part 3 task 3)"`.

### Task 4: Subject layout — risk: high

**Files:**
- Create: `app/export/layout.py`
- Modify: `app/export/copy_export.py` (`plan_export` handles `Layout.SUBJECTS`, path length check)
- Test: `tests/unit/test_export_layout.py`

**Interfaces:**
- Produces:
  - `class Layout(str, Enum): SINGLE = "single"; SUBJECTS = "subjects"`
  - `UNKNOWN_FOLDER = "Chưa xác định"`; `MAX_FOLDER_CHARS = 60`; `MAX_PATH_CHARS = 259`
  - `def safe_folder_name(name: str, fallback: str) -> str`
  - `def subject_folders(conn) -> dict[int, str]` (subject id → unique folder name, `(#id)` rule)
  - `def resolve_subject(conn, subject_id: int) -> int | None` (follows `merged_into`, ≤ 32 steps; cycle / missing
    row → None)
  - `def photo_subjects(conn, photos: list[Photo]) -> dict[int, tuple[int, ...]]` (photo id → resolved subject ids,
    sorted, unique; empty = unknown)
  - `@dataclass(frozen=True) LayoutStats(per_folder: dict[str, int], multi_subject: int, unknown_suggested: int,
    unknown_other: int, analysed: bool)` exposed as `ExportPlan.layout_stats`

- [ ] **Step 1:** Tests: `test_membership_auto_manual_only` (suggested ignored; `none` ignored);
  `test_merged_subject_resolves_to_survivor` (an occurrence left on subject 5 with `merged_into = 9` → folder of 9;
  chain 5 → 9 → 12 → 12; same photo through 5 and 12 → one folder; cycle 5 ↔ 9 and a missing row → unresolved →
  `Chưa xác định` when it is the only assignment); `test_merge_subjects_leaves_no_stale_reference` (after
  `actions.merge_subjects` no occurrence references the dropped id — documents why resolution is only defensive); `test_multi_subject_photo_in_each_folder` (one photo, subjects A and B → 2 × its files, same stem in
  both folders); `test_unknown_and_suggested_go_to_unknown_folder` (+ `LayoutStats` counts);
  `test_safe_folder_name` parametrized: `'Mai/Lan?'`→`'Mai_Lan_'`, `'CON'`→`'CON_'`, `'aux.txt'`→`'aux.txt_'`,
  `'  Ren. '`→`'Ren'`, `'???'` / `'...'` / `'   '` / `'<>|'` → fallback `'Chủ thể 7'` (no letter and no digit after
  sanitising), `'Mai/Lan?'` → `'Mai_Lan_'` (has letters: kept), `'#1'` → `'#1'`, 70-char name → 60 chars, NFC
  normalisation of a decomposed Vietnamese name; `test_duplicate_names_get_ids` (`Mai`, `mai` → `Mai (#3)`, `mai (#9)`; subject named
  `Chưa xác định` → `Chưa xác định (#4)`); `test_path_too_long_is_an_issue` (destination of 230 chars + long name →
  PATH_TOO_LONG, nothing shortened); `test_rename_between_exports_uses_new_folder` (Review Focus);
  `test_planning_never_writes_db` (table snapshot equal); `test_never_analysed_flag` (`analysed` False when no
  occurrences exist).
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement. **Step 4:** Run — PASS.
- [ ] **Step 5:** Commit `"Export: one folder per subject (part 3 task 4)"`.

**Checkpoint A:** full suite ×1 + GUI suite offscreen; review package `review_p3_batchA.txt` (diff, tests, the
compatibility proof); STOP for external review.

---

## Batch B — external source, copy safety, names (review checkpoint after Task 8)

### Task 5: External scan (read-only index) and hashing — risk: medium

**Files:**
- Create: `app/export/sources.py` (scan part), `app/export/hashing.py`
- Test: `tests/unit/test_export_scan.py`, `tests/unit/test_export_hashing.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) SourceSpec(mode: Literal["imported","external"], root: Path | None = None)`
  - `@dataclass(frozen=True) ExternalFile(path: Path, kind: str, size: int)`
  - `@dataclass ExternalIndex(root: Path, by_stem: dict[str, list[ExternalFile]], files: int, skipped: int)`
  - `def scan_external(root: Path, *, session_folder: Path, destination: Path | None, progress:
    Callable[[int], None] | None = None, should_cancel: Callable[[], bool] | None = None) -> ExternalIndex`
  - `class ScanCancelled(ExportError)`; `ExportError` messages (Vietnamese) for: root missing, root = session folder
    or inside it, destination inside root, root inside destination.
  - `hashing.py`: `CHUNK = 1 << 20`; `class HashCancelled(ExportError)`; `def sha256_file(path: Path, *,
    should_cancel: Callable[[], bool] | None = None) -> str`; `class HashCache` with `def sha256(self, path: Path, *,
    should_cancel=None) -> str` keyed by `(resolved path, size, mtime_ns)`, `def known(self, path) -> str | None`,
    `hits` / `reads` counters, `def seed(self, path, size, mtime_ns, sha256)` (imported `assets.sha256` when size and
    mtime still match).

- [ ] **Step 1:** Tests: `test_index_by_stem_casefold_and_kind`; `test_unsupported_and_hidden_skipped` (`.txt`,
  `.hidden/`, `_kirapick_danh_sach/`); `test_symlink_not_followed` (POSIX symlink dir / file; skip on Windows without
  privilege); `test_scan_reads_no_file_content` (monkeypatch `open` / `Path.open` to fail → scan still succeeds);
  `test_scan_is_read_only` (mtimes of every dir and file, sizes, SHA-256 equal before/after);
  `test_cancel_raises_scan_cancelled`; `test_root_rules[case]` for the four validation errors.
  Hashing: `test_sha256_matches_hashlib`; `test_cache_reads_each_file_once` (3 lookups → `reads == 1`); `test_cache_
  invalidated_by_mtime_or_size`; `test_cancel_between_chunks` (3 MiB file, cancel after first chunk →
  `HashCancelled`); `test_hash_opens_read_only` (file mode 0o444 on POSIX; still hashed);
  `test_not_called_on_gui_thread` is enforced in Tasks 9/10 (assert `QThread.currentThread() is not
  QApplication.instance().thread()` inside a monkeypatched `sha256_file` during GUI tests).
- [ ] **Step 2:** FAIL. **Step 3:** Implement with `os.scandir(follow_symlinks=False)`, iterative stack.
  **Step 4:** PASS. **Step 5:** Commit `"Export: read-only scan of another folder (part 3 task 5)"`.

### Task 6: External matching and manual confirmation — risk: high

**Files:**
- Modify: `app/export/sources.py` (matching), `app/export/copy_export.py` (`plan_export` with `SourceSpec("external")`)
- Test: `tests/unit/test_export_match.py`

**Interfaces:**
- Consumes: Tasks 2, 3, 5.
- Produces:
  - `MATCH_TOLERANCE_S = 2.0`
  - `@dataclass(frozen=True) Candidate(path: Path, relative: str, size: int, capture_time: datetime | None,
    camera: str | None)`
  - `@dataclass(frozen=True) Match(status: Literal["matched","missing","not_matched","content_differs","ambiguous"],
    file: Path | None, method: Literal["content","time","manual"] | None, candidates: tuple[Candidate, ...],
    duplicates: int)`
  - `def match_file(photo: Photo, kind: str, index: ExternalIndex, *, hashes: HashCache, read_meta=read_metadata,
    fingerprint=quick_fingerprint, confirmed: Path | None = None, should_cancel=None) -> Match` — rules of spec §3.3
    points 2–6, in that order; `confirmed` must be one of the candidates, else ignored; `Match` gains
    `identity: SourceIdentity | None` (size, mtime_ns, sha256 for content matches).
  - `plan_export(..., source=SourceSpec("external", root), confirmations=...)` uses an `ExternalIndex` passed via
    `SourceSpec` (`index: ExternalIndex | None` field) so planning never rescans.

- [ ] **Step 1:** Tests (synthetic JPEGs with EXIF written by the test; RAW stand-ins = TIFF-based files with a `.NEF`
  extension and EXIF, readable by ExifRead):
  `test_same_format_content_match` (full SHA-256 equal; `match.method == "content"`);
  `test_same_format_content_differs`; `test_middle_byte_differs_is_not_a_match` (same size, same head/tail, one
  byte changed in the middle → `content_differs`); `test_identical_duplicates_resolved` (two copies equal by full
  SHA-256 → `duplicates == 1`, shortest path chosen); `test_head_tail_equal_duplicates_not_resolved` (two candidates
  equal only in head/tail, one equal to the imported file by full SHA-256 → that one matched; neither equal → 
  `content_differs`); `test_each_file_hashed_once` (`HashCache.reads` == number of distinct files); `test_cross_format_within_tolerance` (Δ = 2.0 s → matched, method time);
  `test_cross_format_just_outside` (Δ = 2.01 s → not_matched); `test_subseconds_used`;
  `test_unknown_time_is_ambiguous` (candidate without EXIF; also photo without capture time);
  `test_two_valid_is_ambiguous`; `test_camera_mismatch_not_matched`; `test_stem_variants_not_candidates`
  (`DSC_0001 (1).NEF`, `DSC_0001-Edit.NEF`); `test_counter_restart_three_times` (Review Focus);
  `test_manual_confirmation` (ambiguous + confirmed path → matched / manual; a path not among candidates ignored);
  `test_external_root_is_the_imported_folder` (Review Focus); `test_metadata_read_only_for_candidates` (counting
  `read_meta` calls = number of cross-format candidates); `test_plan_external_twelve_shapes_smoke` (RAW_JPEG external:
  JPEG imported + RAW on card → both copied; RAW absent → only JPEG, note "chỉ có JPEG").
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `"Export: matching files on another folder (part 3 task 6)"`.

### Task 7: Copy verification, manifest v2, retry — risk: high

**Files:**
- Modify: `app/export/copy_export.py` (`run_export`, `_copy_exclusive`, `_write_manifests`, `ExportResult`)
- Test: `tests/unit/test_export_run.py`

**Interfaces:**
- Produces:
  - `ExportResult` adds `statuses: dict[str, str]` (dest_relative →
    `copied|already_present|failed|not_started|source_changed`), `hashes: dict[str, str]` (dest_relative → sha256),
    `source_unavailable: bool`; keeps `copied`, `renamed`, `failed`, `cancelled`, `manifest_csv`, `manifest_json`,
    `copied_ids`.
  - `run_export(plan, *, progress=None, should_cancel=None, options: Mapping[str, str] | None = None) -> ExportResult`
  - `FAIL_FAST_AFTER = 3` consecutive `FileNotFoundError` / device-not-ready (`errno ENOENT, ENODEV, EIO`, Windows
    `winerror 21`) on sources.
  - Manifest columns (spec §3.7): `status, exported_as, folder, photo, kind, source, match, size_bytes, sha256, flag,
    rating, favorite, capture_time, camera, error`; JSON header `{"app_version", "exported_at", "options", "counts"}`.

- [ ] **Step 1:** Tests: `test_verify_failure_removes_only_our_file` (monkeypatch the target's SHA-256);
  `test_copy_hash_streamed_once` (source opened once per copy: the SHA-256 comes from the copy stream);
  `test_already_present_requires_full_hash` (target with same size + head/tail but a different middle byte → copied
  as ` (1)`, original untouched; identical target → `already_present` with its sha256 in the manifest);
  `test_already_present_reverified` (target modified after planning → copied as ` (1)`, original untouched);
  `test_source_changed_before_copy[imported|content|time|manual]` (size or mtime changed after planning or after the
  confirmation → `source_changed`, nothing written); `test_source_replaced_same_size_and_mtime` (content-matched
  source rewritten with `os.utime` restoring mtime → streamed SHA-256 differs → our target removed,
  `source_changed`); `test_time_match_revalidated_on_copy` (time-matched RAW replaced by a same-name file 30 s later →
  `source_changed`);
  `test_cancel_writes_not_started`; `test_partial_failure_continues_and_retry_copies_only_missing` (run, make one
  source unreadable, run again after restoring: second run copies exactly the failed one);
  `test_source_vanishes_after_preview` (Review Focus: after 3 failures the rest `failed` with one
  "Nguồn không còn truy cập được", `source_unavailable` True); `test_never_overwrites_different_file`;
  `test_manifest_rows_cover_ops_and_issues` (every op and every issue has a row; external root written as folder
  name only); `test_export_runs_counts_subject_duplicates` (files count includes duplicates, photos distinct).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `"Export: verified copies, manifest v2 and retry (part 3 task 7)"`.

### Task 8: Copy file names — risk: low

**Files:**
- Create: `app/export/names.py`
- Test: `tests/unit/test_export_names.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) NameList(lines: list[str], photos: int, shared_stems: dict[str, int])`;
  `def keep_names(conn, photo_ids: list[int], *, with_extension: bool) -> NameList`.

- [ ] **Step 1:** Tests: `test_one_line_per_photo_with_pairs` (pair → one line `DSC_0001` / `DSC_0001.NEF`);
  `test_scope_intersect_keep` (scope FAVORITE: only kept favourites); `test_order_capture_time_then_name`;
  `test_shared_stem_listed_once_with_note` (`shared_stems == {"DSC_0001": 2}`); `test_independent_of_subjects` (a
  two-subject photo → one line); `test_works_without_disk` (sources renamed away → same lines).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit
  `"Export: list of kept file names (part 3 task 8)"`.

**Checkpoint B:** full suite ×1 + GUI suite; `review_p3_batchB.txt`; STOP for external review.

---

## Batch C — UI, threads, end-to-end (final checkpoint after Task 11)

### Task 9: Plan thread and shutdown — risk: medium

**Files:**
- Modify: `app/ui/jobs.py` (`ExportPlanThread`), `app/ui/main_window.py` (`_session_work` / `_all_work` include the
  dialog's plan thread as `Work("quét nguồn xuất ảnh", …)`)
- Test: `tests/gui/test_export_plan_thread.py`

**Interfaces:**
- Produces: `class ExportPlanThread(QThread)` with signals `progress(int)`, `planned(int, object)` (generation,
  `ExportPlan`), `failed(int, str)`; `__init__(project_folder: Path, request: PlanRequest, generation: int)`;
  `cancel()`. `@dataclass(frozen=True) PlanRequest(photo_ids, destination, source: SourceSpec, fmt, layout,
  confirmations)`. The thread opens its own SQLite connection (as `ImportThread`), scans when `source.index` is None.

- [ ] **Step 1:** Tests: `test_plan_thread_emits_plan`; `test_late_plan_result_is_dropped` (Review Focus: generation
  1 slow scan, generation 2 fast → only 2 shown); `test_close_during_scan_waits_then_closes` (shutdown contract,
  database closed last, like `test_shutdown_callbacks`); `test_switch_folder_during_scan`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit
  `"Export: background planning in the shutdown contract (part 3 task 9)"`.

### Task 10: Export dialog — three groups, preview, confirmations, names tab — risk: high

**Files:**
- Modify: `app/ui/export_dialog.py` (rewrite of the layout; copy / progress / record logic kept),
  `app/ui/main_window.py` (`open_export_dialog`, settings migration), `README.md` (Xuất ảnh section)
- Test: `tests/gui/test_export_dialog_p3.py`; update existing export GUI tests to the new widgets

**Interfaces:**
- Consumes: Tasks 3–9.
- Produces (widgets tests use): `dialog.source_imported`, `dialog.source_external`, `dialog.external_path`,
  `dialog.format_buttons: dict[ExportFormat, QRadioButton]`, `dialog.layout_buttons: dict[Layout, QRadioButton]`,
  `dialog.plan_table`, `dialog.issue_table`, `dialog.use_candidate(row: int, candidate: int)`,
  `dialog.names_tab`, `dialog.names_with_ext`, `dialog.copy_names_button`, `dialog.copy_button`;
  `migrate_export_settings(settings: QSettings) -> None` in `export_dialog.py`.
- Copy (Vietnamese) exactly as spec §4.

- [ ] **Step 1:** Tests: `test_three_groups_independent` (all 12 combinations selectable; each change re-plans once);
  `test_defaults_and_migration` (`export/include_pairs=true` → RAW+JPEG, no notice; `false` → RAW+JPEG and the
  one-time notice text of spec §4 shown, gone after a format change or closing it, not shown on the next opening;
  old key removed; "Giữ cấu trúc thư mục con" box gone); `test_no_hashing_on_gui_thread` (see Task 5); `test_preview_counts_and_tabs`;
  `test_ambiguous_confirm_flow` (issue row → "Dùng file này" → moves to plan table with ✋, copy button count +1);
  `test_copy_disabled_while_scanning`; `test_names_tab_copies_to_clipboard` (`QGuiApplication.clipboard().text()`;
  with / without extension; works with external source chosen but folder missing);
  `test_dialog_fits_tiny_and_short` (560 × 400, 1280 × 323: buttons visible, no horizontal scroll);
  `test_confirm_text_lists_skipped`; `test_retry_button_after_partial_failure`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; existing export GUI tests PASS.
- [ ] **Step 5:** Commit `"Export dialog: source, format, layout, preview and names (part 3 task 10)"`.

### Task 11: End-to-end, performance, Windows CI, docs — risk: medium

**Files:**
- Create: `tests/integration/test_export_combinations.py`, `tests/perf/test_export_perf.py`
- Modify: `.github/workflows/build-windows.yml` (add `tests/gui/test_export_dialog_p3.py`,
  `tests/gui/test_export_plan_thread.py` to the real-platform file list), `docs/IMPLEMENTATION_STATUS.md`,
  `docs/beta-release-checklist.md` (section 3 step "Xuất nâng cao", known issues), `scripts/ui_screenshots.py`
  (`--export`)
- Test: the two new files

- [ ] **Step 1:** `test_twelve_combinations[source,fmt,layout]` (parametrized 2 × 3 × 2) on one fixture (pairs, JPEG-only,
  RAW-only, two subjects, unknown, external folder with RAWs + a counter-restart duplicate): plan + run + manifest;
  asserts per combination the expected file set per folder (table in the test), issues, and that sources and the
  external folder are byte-identical afterwards; `test_network_free` (guard test covers `app/export/*`).
- [ ] **Step 2:** Perf (`-m perf`): plan imported 1 000 photos on the GUI thread ≤ 100 ms (else Task 9's thread plans it too, spec §5), 10 000 recorded, external scan of 5 000
  files, matching 1 000 cross-format photos (EXIF reads = candidates), Qt thread worst block during scan ≤ 100 ms.
- [ ] **Step 3:** Screenshots of the dialog at WIDE / MEDIUM / NARROW / SHORT / TINY.
- [ ] **Step 4:** Full suite ×3, GUI suite, perf; push with `[perf]`; read every Windows CI notice.
- [ ] **Step 5:** Commit `"Export: end-to-end combinations, performance, docs (part 3 task 11)"`; write
  `review_out/review_p3_final.txt`; STOP for external review.

---

## Risk summary

| Task | Risk | Why |
|---|---|---|
| 3 | high | replaces the planner every export uses; guarded by Task 1 golden tests |
| 4 | high | folder names on Windows, duplication of files |
| 6 | high | wrong external file = wrong photo delivered |
| 7 | high | the copy / verification core |
| 10 | high | the user-facing flow, settings migration |
| 5, 9, 11 | medium | IO on slow media; threads and shutdown |
| 1, 2, 8 | low | read-only helpers and tests |
