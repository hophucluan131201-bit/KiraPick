# KiraPick Part 3 — Advanced Export: technical design

Status: **design checkpoint** (rev 2, 2026-10-30; rev 1 → rev 2 delta in §10) — for external review. No code is written before this specification
and its plan (`docs/superpowers/plans/2026-10-30-kirapick-advanced-export.md`) are approved. Nothing is released.

Inputs: owner answers (2026-10-30), external review "Part 3 — Architecture Review: APPROVED WITH CHANGES"
(approach A; CR-P3-01 … CR-P3-04 and the safety contracts), CLAUDE.md invariants (offline, non-destructive, never fake
results, stable IDs, schema migrations only when necessary).

---

## 1. Purpose and decisions

The owner culls a cosplay shoot in KiraPick and then hands photos over. Today Export copies the kept photos (and their
RAW+JPEG partners) from the imported folders into one folder. Part 3 lets the owner:

- take the files from **another place** than the imported folder — a memory card or an archive drive — for example
  import only the JPEGs for a fast cull and take the RAWs from the card (owner: "nhập cả RAW và JPG tuỳ thích … lấy
  file từ nguồn lưu trữ khác như thẻ nhớ hoặc ổ cứng"; "Nhập JPEG, lấy RAW từ thẻ"; "Lấy từ thẻ nhớ gốc");
- choose the **format**: RAW only, JPEG only, or RAW + JPEG;
- put each **subject** (cosplayer) in its own folder;
- copy the **file names** of the kept photos to the clipboard (to send a client a list) without exporting anything.

Decisions (owner + review):

| # | Decision | By |
|---|---|---|
| D1 | Approach A: extend the current export with a pipeline (scope → source files → format → destination layout → preview → copy); the existing safe copy core stays | review |
| D2 | Exactly three independent option groups — Source, Format, Destination layout — 12 valid combinations | review |
| D3 | "JPEG only" when a photo has no JPEG anywhere: skip it and report it ("Thiếu"); KiraPick never creates or extracts a JPEG | owner |
| D4 | A photo with several subjects is copied into **each** subject's folder | owner (changed from "Ảnh nhóm" to match CR-P3-03) |
| D5 | Photos whose subject is only suggested (not confirmed) or unknown, and photos without a person, go to "Chưa xác định"; the preview says how many and suggests reviewing first | owner |
| D6 | External matching: same base name + capture time within 2 s; never widened; anything unsure is "ambiguous" and is copied only after the user confirms one candidate | review CR-P3-01 |
| D7 | Default: imported source + RAW+JPEG + one folder, proven equal to today's export by regression tests (pairs, RAW-only, JPEG-only, standalone files) | review CR-P3-02 |
| D8 | Database schema unchanged; Part 2 (Compare) unchanged | review |
| D9 | Byte identity is claimed only after a full SHA-256 comparison; the quick fingerprint (size + head/tail 64 KiB) only filters candidates | review CR-P3-D01 |
| D10 | Other rasters (TIFF / PNG / HEIC): kept from the imported source under RAW_JPEG (legacy); never matched on an external source in rev 2; not part of "JPEG only"; no conversion of any kind | review CR-P3-D02, Q3 |
| D11 | The old "Giữ cấu trúc thư mục con" box is removed; `export/include_pairs = false` users get RAW + JPEG and are told once (§4) | review Q1, CR-P3-D03 |
| D12 | Every source file is revalidated when it is copied; changed content is never copied silently (§3.6) | review (additional safety case) |

## 2. Current export architecture (audit)

Files: `app/export/copy_export.py` (352 lines), `app/ui/export_dialog.py` (287), `app/ui/jobs.py` `ExportThread`,
`app/storage/exports.py` (run records), `app/storage/stats.py` (bottom-bar size), `MainWindow.open_export_dialog`.

| Concern | Today |
|---|---|
| Scope ("which photos") | `Selection` KEEP / FAVORITE / RATED (≥ n stars) / IDS (marked) / COLLECTION (client list); `select_ids` returns photo ids (`status = 'ok'`); a pair's decisions live on its primary asset (the RAW: the JPEG half of a pair is never shown, `SHOWN_PHOTO_SQL`) |
| Which files | `export_groups(conn, ids, include_pairs)`: the photo's asset, plus the other `ok` files of its `pair_group_id` when "Kèm file JPEG của cặp RAW+JPEG" is on. Single source of truth for the copy and the bottom-bar size estimate |
| Destination names | `plan_export`: one folder (or `<source folder name>/<sub folders>` with "Giữ cấu trúc thư mục con"); all files of a pair share one stem; `_choose_stem` picks `stem`, `stem (1)`, … free on disk and in the plan; a target already holding identical bytes (size + head/tail hash) is `already_present` and skipped |
| Validation | destination ≠ an imported source root, not inside the session folder, a directory |
| Copy | `run_export` in `ExportThread`: `open(…, "xb")` (never overwrites), copies, `copystat`, checks size; on failure removes only its own partial file; cancel between files; per-file failures continue |
| Manifest | `_kirapick_danh_sach/kirapick_export_<stamp>.csv/.json`: copied files only (exported_as, source_path, flag, rating, favorite, capture_time, camera, size) |
| Records | `export_runs` (photos, files) for the ✓ "Xuất ảnh" step — never the destination path |
| UI | modal-less dialog: scope radios, 2 check boxes, destination, preview table (≤ 300 rows), summary (bytes, free space, missing, already present), confirm box, progress dialog with "Dừng" |
| Shutdown | closing / switching folders asks before stopping a running export (`_export_may_stop`); the window waits for the thread (shutdown contract) |
| Tests | `tests/unit/test_export.py`, `test_export_run_mapping.py`, `test_stats_vs_export.py`, `tests/integration/test_export_runs.py`, `test_view_and_exports.py`, GUI tests in `test_review_notes_t15.py` / `test_shutdown_callbacks.py` |

Gaps for Part 3: files can only come from the imported folders; the format choice is a single check box whose "off"
state means "the photo's own file"; no subject folders; the manifest lists only what was copied; already-present files
are checked at plan time only; the preview has no "needs a look" list.

## 3. Pipeline

```
Scope (Selection)          → photo ids                 copy_export.select_ids (unchanged)
Photos                     → PhotoFiles per photo      export/photos.py      (DB only)
Source resolution          → SourceFile per wanted file  export/sources.py   (imported | external, read-only)
Format filter              → wanted kinds per photo     export/formats.py
Destination layout         → target folders per photo   export/layout.py     (one folder | subjects)
Planning                   → ExportPlan (operations + issues)  copy_export.plan_export (extended)
Preview                    → dialog tables + summary
Copy                       → run_export (extended verification, manifest v2)
```

Each stage is a pure function of its inputs plus read-only disk access, testable without Qt.

### 3.1 Photos (`app/export/photos.py`, new)

`PhotoFiles(photo_id, stem, primary, files, capture_time, subsec, camera)` for each photo in scope:
- `files`: the photo's `ok` assets of its pair group (or itself), each with `asset_id, kind, path, size, quick_hash,
  relative_path, source_root`.
- `kind` (`app/export/formats.py`): `raw` (`media_kind = 'raw'`), `jpeg` (extension in
  `PAIRABLE_RASTER_EXTENSIONS` = `.jpg`, `.jpeg`), `other` (other rasters: TIFF, PNG, HEIC…).
- `stem`: the primary asset's file stem (the name the grid shows); `capture_time`, `subsec`, `camera` (make + model)
  of the primary, falling back to any file of the group that has them.

### 3.2 Format (`app/export/formats.py`, new)

`ExportFormat`: `RAW_JPEG` (default), `RAW`, `JPEG`.

| Format | Wanted kinds | A photo lacking every wanted kind |
|---|---|---|
| RAW_JPEG | every file of the photo (raw, jpeg **and other**) — exactly today's "Kèm JPEG" on | — (it always has a file) |
| RAW | `raw` | "Thiếu RAW" issue, nothing copied |
| JPEG | `jpeg` | "Thiếu JPEG" issue, nothing copied (D3: never converted or extracted) |

With an imported source the wanted files are the photo's own files of those kinds. With an external source (3.3) the
wanted files are the kinds selected, looked up on the external source — **including kinds that were not imported**
(import JPEG, take RAW from the card). For RAW_JPEG with an external source: wanted kinds = `raw` and `jpeg`; a photo
needs at least one of them matched; the other, when absent, is noted "chỉ có RAW" / "chỉ có JPEG" (informational,
not an error). `other` files are only ever copied from the imported source (documented limitation).

Other rasters, explicitly (D10):
- Imported + RAW_JPEG copies standalone TIFF / PNG / HEIC photos and `other` files of a pair group, as today
  (legacy compatibility, `include_pairs = true`).
- Imported + RAW or JPEG: `other` files are never copied; a TIFF / PNG / HEIC-only photo gets "Thiếu RAW" /
  "Thiếu JPEG" (`missing_format`).
- External source (any format): only `raw` and `jpeg` files are indexed and matched; a photo whose wanted kind is
  `other` is not looked up there. Under External + RAW_JPEG a TIFF / PNG / HEIC-only photo therefore gets
  `missing_format` with detail "định dạng này chỉ lấy được từ thư mục đã nhập".
- KiraPick performs no conversion, extraction or re-encoding in any combination.

### 3.3 Source resolution (`app/export/sources.py`, new) — CR-P3-01

`SourceMode.IMPORTED` (default): the wanted file is the imported asset at `source_root / relative_path`; checked with
`is_file()` and `not is_symlink()` at plan time; absent → "Thiếu (không còn trên ổ đĩa)" (today's `missing`).

`SourceMode.EXTERNAL`: the user picks one folder (card, drive). Contract:

1. **Scan** (worker thread, read-only, cancellable, progress): recursive `os.scandir`; does not follow symlinks or
   junctions; skips hidden/system folders and `_kirapick_danh_sach`; refuses a root that is the session folder or is
   inside the export destination (and the destination may not be inside the external root — no copying a card into
   itself). Index: `stem.casefold() → [ExternalFile(path, kind, size)]` for supported extensions only. No file is
   opened during the scan.
2. **Candidates** for photo P and wanted kind K: external files with `stem.casefold() == P.stem.casefold()` and kind K.
   The base name must match exactly (case-insensitive); `DSC_0123 (1)`, `DSC_0123-Edit` are not candidates.
3. **Same-format verification** (an imported file R of kind K exists), in two stages (D9):
   - *filter*: `C.size == R.size` and C's head/tail hash (`quick_fingerprint`) equals `R.quick_hash`; a candidate
     failing the filter cannot be identical;
   - *proof*: full SHA-256 of C equals the full SHA-256 of R (`assets.sha256` when recorded, otherwise R is hashed
     once, read-only, §3.9). Only then is C a **content match**.
   Same name and the filter or the proof fails → "Khác nội dung" (not copied; e.g. an edited or re-saved file).
   Several candidates proven identical by full SHA-256 are the same bytes: one is used (shortest path, then
   alphabetical), the others are listed as "bản giống hệt" — the only multi-candidate case resolved automatically
   (review Q2). Candidates that pass the filter but not the proof never count as duplicates.
4. **Cross-format verification** (no imported file of kind K, e.g. imported JPEG → card RAW): read C's capture time
   (`app.ingest.metadata.read_metadata`, DateTimeOriginal + SubSecTimeOriginal, camera make/model; read only for
   candidates, never for the whole card). C is **valid** when:
   - both capture times are known and `|t_C − t_P| ≤ 2.0 s` (subseconds used when both sides have them; the 2 s
     constant is the import's pairing tolerance and is never widened), **and**
   - when both cameras are known, they are equal (guards against a second camera with the same file counter).
5. **Outcome per (photo, kind)**:

   | Situation | Status | Copied? |
   |---|---|---|
   | exactly one content match (3, full SHA-256), or ≥ 2 candidates all proven identical (3), or exactly one valid candidate (4) | `matched` | yes |
   | no candidate | `missing` ("Không tìm thấy") | no |
   | candidates exist, all with a known, different capture time or camera | `not_matched` ("Không khớp" — e.g. the camera counter restarted) | no |
   | same-format candidates, none proven identical (filter or full SHA-256 differs) | `content_differs` ("Khác nội dung") | no |
   | ≥ 2 valid candidates; or a candidate whose (or the photo's) capture time is unknown | `ambiguous` ("Không chắc") | only after manual confirmation |

6. **Manual confirmation**: the preview's "Cần xem lại" list shows each ambiguous (photo, kind) with its candidates
   (path relative to the external root, size, capture time or "không đọc được", camera). The user picks one candidate
   ("Dùng file này") or leaves it. The confirmation stores the candidate's identity (path, size, `mtime_ns`, §3.9).
   A confirmed choice becomes `matched_manual` for this dialog only (kept in memory,
   not in the database — D8), shown with a "✋ xác nhận tay" mark and written as `match = manual` in the manifest.
   Choosing a source folder again or closing the dialog forgets the confirmations.
7. The external source is never written: no `mkdir`, no temp file, no metadata update; files are opened read-only and
   only for hashing, EXIF and copying.

### 3.4 Destination layout (`app/export/layout.py`, new) — CR-P3-03

`Layout.SINGLE` (default): every operation goes to the destination root (today). `Layout.SUBJECTS`:

- **Membership** (read-only, no AI run, assignments never changed): photo P belongs to subject S when an occurrence of
  any file of P's pair group has `assignment IN ('auto', 'manual')` and its `subject_id` **resolves** to S.
  `suggested` and `none` do not count (D5).
- **Merged subjects — resolution**: `merge_subjects` (app/identity/actions.py) moves every occurrence of the dropped
  subject to the kept one and deletes the dropped row, so occurrences normally reference surviving subjects only.
  Defensively (older sessions, an interrupted merge), `resolve(subject_id)` follows `subjects.merged_into` until a row
  with `merged_into IS NULL` (at most 32 steps; a cycle or a missing row → unresolved). An unresolved occurrence does
  not make the photo a member of anything; if it was the photo's only assignment the photo goes to `Chưa xác định`.
  A photo whose occurrences resolve to the same subject twice gets one folder (set semantics).
- A photo with one or more subjects is placed in **each** subject's folder (D4) — one operation per (file, subject).
- A photo with no subject (no person, never analysed, only `suggested`, or `none`) goes to `Chưa xác định`.
- **Folder names**: `display_name`, or `Chủ thể <id>` when unnamed. Sanitised for Windows: characters
  `< > : " / \ | ? *` and control characters → `_`; leading/trailing spaces and trailing dots removed; reserved names
  (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`, also with an extension) get a `_` suffix; length ≤ 60
  characters (cut at a character boundary); Unicode (Vietnamese) kept, normalised to NFC.
  **Fallback rule (single definition):** if the sanitised name contains no letter and no digit (Unicode categories
  L* and N*) — e.g. `???` → `___`, `...`, `  ` — the folder is `Chủ thể <id>`. Otherwise the sanitised name is
  used, replacement characters included (`Mai/Lan?` → `Mai_Lan_`).
- **Duplicate folder names** (two subjects both named "Mai", or sanitising makes two names equal, compared
  case-insensitively): every such subject gets ` (#<id>)` appended — `Mai (#12)`, `Mai (#31)` — stable across runs.
  `Chưa xác định` is reserved: a subject named so becomes `Chưa xác định (#<id>)`.
- **Path length**: each planned target's absolute path is checked against 259 characters (Windows MAX_PATH without
  long-path support). Longer → `path_too_long` issue for that operation (not copied, shown in "Cần xem lại"), never
  silently shortened.
- The preview reports: photos per folder, photos in several folders, photos in "Chưa xác định" split into "AI chưa
  chắc", "chưa có người / chưa phân tích", and a hint "Nên xem lại mục Cần xem lại (Nhận diện chủ thể) trước khi xuất"
  when suggested photos exist. If no subject analysis has ever run, choosing "Theo chủ thể" shows "Chưa nhận diện chủ
  thể — mọi ảnh sẽ vào Chưa xác định".

### 3.5 Planning (`copy_export.plan_export`, extended)

```python
plan_export(project, photo_ids, destination, *, source: SourceSpec = IMPORTED, fmt: ExportFormat = RAW_JPEG,
            layout: Layout = SINGLE, confirmations: dict[(photo_id, kind), Path] | None = None) -> ExportPlan
```

- `ExportPlan.operations: list[ExportOp]` — one per file copy: `photo_id, asset_id (imported file of that kind or the
  photo's primary for external-only kinds), kind, source path, folder, dest_relative, size, match (imported | content |
  time | manual)`.
- `ExportPlan.issues: list[ExportIssue]` — `photo_id, kind, status` (`missing`, `missing_format`, `not_matched`,
  `content_differs`, `ambiguous`, `path_too_long`, `invalid_destination`), detail, candidates.
- `already_present` — as today, per folder.
- Naming: within one folder, all files of one photo share a stem (`_choose_stem`, unchanged); the same photo in two
  subject folders is planned independently per folder; collision suffixes ` (n)` only within a folder.
- Totals: `photos_in_scope`, `photos_planned`, `operations`, `bytes` (sum over operations, so a photo in two folders
  counts twice), `already_present`, issue counts by status.
- Validation as today, plus: destination not inside the external root and vice versa; the external root not inside
  the session folder.
- The default call (`IMPORTED, RAW_JPEG, SINGLE`) must give the same `items` / `already_present` / `missing` as
  today's `plan_export(include_pairs=True, keep_folders=False)` — proven by the regression tests of 6.1.

### 3.6 Copy (`run_export`, extended)

- Unchanged: exclusive create, never overwrite, `copystat`, partial file of a failed or cancelled copy removed (only
  our own), cancel between files, per-file failure continues.
- **Source revalidation (D12)** — every operation carries the source identity taken when it was planned or confirmed:
  `size`, `mtime_ns`, and `sha256` when the plan computed one (content matches, duplicates). Just before copying:
  `lstat` the source; not a regular file, a symlink, or `size` / `mtime_ns` different → the operation is
  `source_changed` ("File nguồn đã thay đổi sau khi xem trước"), nothing copied. While copying, the source bytes are
  hashed (SHA-256) from the same stream (no extra read); if the plan had a `sha256` and it differs → the new target
  is removed, `source_changed`. For a time match (§3.3 point 4) the copied target's capture time and camera are read
  back and must still satisfy the match; otherwise the target is removed, `source_changed`. The user can re-plan
  ("Xem trước lại") after any `source_changed`.
- **Copy verification**: after the copy the target is read once and its SHA-256 must equal the streamed source
  SHA-256 (and the sizes equal); otherwise the target (our own new file) is removed and the operation is
  `failed: verify`. (Replaces rev 1's size + head/tail check.)
- **Already-present targets** (D9): at planning time the size + quick fingerprint only *suggests* that a target holds
  the same file; the preview says "có vẻ đã có sẵn — sẽ kiểm tra đầy đủ khi chép". At run time, in the copy thread,
  the target and the source are compared by full SHA-256 (the source hash reused if known) before the operation is
  reported `already_present`. If they differ, the operation is copied to the next free ` (n)` name; the existing file
  is never overwritten.
- External source removed mid-copy (card ejected): the current file fails (`OSError`), later operations fail fast
  after 3 consecutive "device not ready / not found" errors with one message "Nguồn không còn truy cập được"; copied
  files stay.

### 3.7 Manifest v2 — safety contract

Written into `<destination>/_kirapick_danh_sach/` (as today) at the end of every run that started, also when
cancelled or partly failed, as CSV (UTF-8 with BOM) and JSON, file name `kirapick_export_<stamp>`:

- header (JSON) / first rows (CSV): app version, options (scope, source mode — the external root's folder **name**
  only, format, layout), counts;
- one row per planned operation and per issue: `status` (`copied`, `already_present`, `failed`, `not_started`
  (cancelled), `source_changed`, `missing`, `missing_format`, `not_matched`, `content_differs`, `ambiguous`,
  `path_too_long`), `exported_as`, `folder`, `photo` (stem), `kind`, `source` (path relative to its root), `match`,
  `size_bytes`, `sha256` (of the copied / verified file, empty otherwise), `flag`, `rating`, `favorite`,
  `capture_time`, `camera`, `error`.
- **Retry**: exporting again with the same options into the same destination re-plans; files present with identical
  content are skipped (`already_present`), so only missing / failed operations are copied. The dialog offers
  "Thử lại các file chưa chép" after a cancelled or partly failed run (same plan, refreshed). The manifest is a record
  for the user, not an input (no parsing of old manifests).
- `export_runs` keeps recording (photos = distinct photos copied, files = files copied) only for runs that copied at
  least one file (today's rule).

### 3.8 Copy file names (`app/export/names.py`, new) — CR-P3-04

`keep_names(conn, photo_ids, *, with_extension) -> NameList`:
- photos = scope ∩ Keep (`decisions.flag = 'keep'` on the photo, subject_id NULL): with scope "Ảnh đã Giữ" that is
  every kept photo; with another scope, the kept photos within it;
- one line per **photo** (a RAW+JPEG pair is one photo; subject folders do not repeat it): the primary file's name —
  `DSC_0123` without extension, `DSC_0123.NEF` with (the RAW for a pair, as the grid shows);
- ordered by capture time, then name; identical lines appear once; when two different photos share a stem (two
  folders, counter restart) the list shows the line once and a note "2 ảnh trùng tên DSC_0001";
- database only: works with no destination, no external source, a disconnected card, and does not depend on the
  Source / Format / Layout choices;
- clipboard: `QGuiApplication.clipboard().setText("\n".join(lines))`; local only, nothing leaves the PC.

### 3.9 Hashing and source identity (`app/export/hashing.py`, new) — CR-P3-D01

- `sha256_file(path, *, should_cancel) -> str`: 1 MiB chunks, `should_cancel` checked between chunks
  (`HashCancelled`), file opened read-only. Never called on the GUI thread (plan thread or copy thread only).
- `HashCache` for one dialog: key `(resolved path, size, mtime_ns)` → sha256; a file is hashed at most once per
  dialog however many previews, duplicates or retries need it. Imported files reuse `assets.sha256` when the import
  recorded it and the file's `size` / `mtime_ns` still equal the asset row; `assets` is never written by export.
- Where full hashes are computed: external same-format candidates that pass the quick filter (§3.3 point 3) and the
  imported file they are compared with; already-present targets and their sources (at run time, §3.6); every copied
  file (streamed source + one read of the target).
- Cost: a same-format external export reads each matched source once at planning and once while copying (the copy
  stream). The preview shows "Đang kiểm tra nội dung … n / m file" with the scan progress; cancel stops it.

## 4. UX — Export dialog

Title "Xuất ảnh (sao chép)". Two tabs so it fits the TINY / SHORT layouts of Part 1 (minimum 560 × 400): the dialog
scrolls inside each tab; buttons stay visible.

**Tab 1 "Sao chép file"** (top to bottom):

1. **Ảnh nào** — the existing scope radios (Giữ / Yêu thích / Từ n sao / Đang đánh dấu / Danh sách khách).
2. **① Nguồn lấy ảnh** — ( ) Thư mục đã nhập vào KiraPick · ( ) Nguồn khác: [path] [Chọn…] — status line: "Đang quét
   … 1 234 file" / "Đã quét 2 431 file" / "Chưa chọn thư mục". Scanning runs in the background; the rest of the dialog
   stays usable; "Dừng quét" while it runs.
3. **② Định dạng** — ( ) RAW + JPEG · ( ) Chỉ RAW · ( ) Chỉ JPEG/JPG.
4. **③ Thư mục đích** — ( ) Tất cả vào một thư mục · ( ) Mỗi chủ thể một thư mục — and the destination row
   [path] [Chọn…].
5. **Xem trước** — sub-tabs "Sẽ chép (n)" (photo, from, to folder / name; renamed targets in yellow; manual matches
   marked ✋) and "Cần xem lại (n)" (status, photo, kind, detail; for `ambiguous`: candidates + "Dùng file này").
6. **Tóm tắt** — "n ảnh → m file (x GB) vào k thư mục · dung lượng trống y GB · có vẻ đã có sẵn a (kiểm tra đầy
   đủ khi chép) · thiếu b · không khớp c · không chắc d · …" (each count only when non-zero), hints of 3.4.
7. Buttons: **Sao chép m file** (disabled while scanning, while nothing is planned or space is short) · Đóng.

The three groups are independent radios; every combination is valid (12). The choices are remembered
(`export/source`, `export/format`, `export/layout`, `export/external_root` in QSettings); the external folder is
remembered but re-scanned on each opening (a card may have changed). Default for a first run: Thư mục đã nhập · RAW +
JPEG · Một thư mục.

Migration (CR-P3-D03, D11): the old key `export/include_pairs` is read once and then removed.
- `true` (the default before Part 3) → RAW + JPEG: the same files as before (proven by §6.1).
- `false` → RAW + JPEG as well, which **changes the previous behaviour**: before, a RAW+JPEG pair exported only its
  primary file (the RAW) and a standalone photo its own file; now the pair's JPEG is copied too. The dialog shows once,
  above ② Định dạng: "Trước đây bạn tắt 'Kèm JPEG của cặp RAW+JPEG'. Bản mới mặc định chép RAW + JPEG — chọn 'Chỉ RAW'
  nếu chỉ muốn file RAW (ảnh chỉ có JPEG khi đó sẽ được báo thiếu)." The notice is dismissed by any change of ② or by
  closing it (`export/migration_notice_shown`). No setting claims to preserve the old "off" preference: neither new
  option equals it (Chỉ RAW skips JPEG-only photos, which the old option copied).
- "Giữ cấu trúc thư mục con" (Q1: removed): it was off by default. Users who turned it on now get one folder (or
  subject folders); sub-folder structure of the source is not reproduced. Documented in README and the release
  notes.

**Tab 2 "📋 Tên ảnh đã Chọn"**: count ("128 ảnh đã Chọn trong phạm vi này"), [✓] Kèm đuôi file, a read-only list (one
name per line), big button **📋 Sao chép tên ảnh** → status "Đã sao chép 128 tên vào bộ nhớ tạm". Uses the scope of
tab 1 only.

Confirmation box (unchanged wording, extended): "Sao chép m file (x GB) của n ảnh vào … Ảnh gốc giữ nguyên (cả trên
thẻ nhớ). File trùng tên ở đích sẽ không bị ghi đè."; d ambiguous not confirmed and other issues are listed as "sẽ bỏ
qua". Progress dialog and finish message as today, plus "Danh sách đầy đủ (cả file bỏ qua): thư mục con
_kirapick_danh_sach" and "Thử lại các file chưa chép" when some failed or were not started.

## 5. Threading, shutdown, offline

- External scan, EXIF reads, full SHA-256 hashing and planning with an external source run in a `QThread`
  (`ExportPlanThread`), cancellable (between files and between 1 MiB hash chunks), with a generation token: a result
  for an older choice (source / format / layout / scope changed meanwhile) is dropped. No hashing on the GUI thread:
  imported-source planning uses only `stat` and the quick fingerprint of existing targets; full verification of
  already-present targets happens in the copy thread (§3.6).
  Imported-source planning stays on the GUI thread as today (stat per file; measured in 6.4, moved to the thread if
  it exceeds 100 ms for 1 000 photos).
- The plan thread joins the window's shutdown contract as one more `Work` entry ("quét nguồn xuất ảnh"), like the
  existing export thread (no change to the Gate / shutdown architecture). Closing during a scan stops it.
- Offline: no network code; clipboard and file system only. The network-import guard test covers the new modules.

## 6. Tests

6.1 **Compatibility (CR-P3-02)** — table-driven, imported source, before the old options are removed: for
fixtures {RAW+JPEG pairs, RAW-only, JPEG-only, standalone TIFF/PNG, a pair whose JPEG is missing on disk, name
collisions at the destination, an identical copy already there} × scopes {Keep, Favorite, Rated, IDs, Collection}:
new `plan_export(IMPORTED, RAW_JPEG, SINGLE)` == old `plan_export(include_pairs=True)` (operations, names,
already_present candidates, missing). The equivalence claim covers `include_pairs = true` only. For
`include_pairs = false` a separate test documents the **difference** (old: pair → RAW only; new RAW_JPEG: RAW + JPEG)
and the one-time migration notice (§4); no test or text claims the old "off" preference is preserved. Keep / Reject: rejected and
undecided photos never appear for scope Keep; decisions of a pair's primary apply to the pair; copying never changes
decisions, subjects, view rotation or sources (byte-identical tables and files before/after).
6.2 **Formats** — 3 formats × imported fixtures: wanted files, `missing_format` issues, sizes; TIFF / PNG / HEIC:
copied under Imported + RAW_JPEG only, `missing_format` under RAW / JPEG and under every External combination, no
conversion (D10).
6.3 **External matching** — unit tests on synthetic folders (real JPEG / TIFF-based files with EXIF written by the
tests): same-format content match proven by full SHA-256; same size + same head/tail but a different middle byte →
`content_differs` (the quick filter alone would have passed it); duplicates identical by full SHA-256 → resolved,
duplicates equal only in head/tail → not duplicates; each file hashed once per dialog (`HashCache` counter); hash
cancel; cross-format within 2.0 s / at 2.01 s
(not matched); unknown time → ambiguous; two valid → ambiguous; camera mismatch; stem case and `DSC_0123 (1)`;
symlink / junction not followed; hidden folder skipped; the card is read-only during the whole export (directory and
file mtimes, sizes and a hash snapshot equal before/after; a read-only temp tree on Linux; on Windows CI the read-only
attribute); manual confirmation; scan cancel.
6.4 **Layout** — membership from auto/manual only; multi-subject → each folder; suggested-only and unknown →
"Chưa xác định"; merged subjects; duplicate names → `(#id)`; Windows-forbidden characters, reserved names, 60-char cut,
NFC; the fallback rule (`???`, `...`, spaces → `Chủ thể <id>`; `Mai/Lan?` → `Mai_Lan_`); merged subjects: an
occurrence still pointing to a dropped subject with `merged_into` resolves to the survivor, a chain of two merges
resolves to the last, a cycle or missing row → unresolved → `Chưa xác định` when nothing else; path > 259 → issue; DB
unchanged by planning and export.
6.5 **12 combinations** — parametrized end-to-end (plan + run + manifest) on one fixture with pairs, a JPEG-only photo,
two subjects, an unknown subject and an external folder; asserts operations, folders, issues, manifest rows.
6.6 **Copy safety** — verify-after-copy (full SHA-256) failure removes only our file; an already-present target
with the same size and head/tail but a different middle byte is not accepted: copied to ` (n)`, original untouched;
source revalidation: a source modified (content, size or mtime) or replaced between preview / confirmation and copy
→ `source_changed`, nothing (or only our removed file) written, for imported, content-matched, time-matched and
manually confirmed sources; a time-matched source replaced by a same-name file of another time → `source_changed`;
cancel mid-run (copied stay, manifest has `not_started`); card removed mid-run (fail-fast after 3); retry copies only
the missing; never overwrite (pre-created different file).
6.7 **Names** — one line per photo with pairs and multi-subject; with/without extension; scope ∩ Keep; same stem in two
folders; works with no destination / no external source; clipboard content.
6.8 **GUI** (offscreen + the real `windows` platform in CI): the three groups independent; preview counts; manual
confirm; buttons disabled while scanning; TINY / SHORT sizes; closing / switching folders during scan and during copy
(shutdown contract); bottom-bar size follows the format.
6.9 **Performance** — 10 000-photo session: imported planning on the GUI thread ≤ 100 ms for 1 000 photos (else it
moves to the plan thread, §5), external scan of a 5 000-file
tree, EXIF reads only for candidates; no Qt-thread block > 100 ms during scan / plan.
6.10 **Owner manual check** (Windows laptop, real card): checklist section 3 gets an "Xuất nâng cao" step.

## 7. Compatibility with Part 1 and Part 2

| Area | Effect |
|---|---|
| Default export | same files and names as today (6.1); the dialog's look changes (tabs, groups) |
| "Kèm file JPEG của cặp" box | replaced by ② Định dạng. Old `true` → RAW + JPEG, same files. Old `false` → RAW + JPEG, **different files** (a pair's JPEG is now copied too); one-time notice in the dialog; README / release notes say so |
| "Giữ cấu trúc thư mục con" box | removed (review Q1); it was off by default; users who used it now get one folder or subject folders; documented |
| Already-present detection | stricter: a target is skipped only after a full SHA-256 match at copy time (before: size + head/tail at plan time) |
| Bottom-bar size ("x GB") | follows ② Định dạng for the imported source, one folder (no subject duplication, no external lookup); tooltip says so. `stats.counts` takes the format instead of `include_pairs` |
| Client list export ("Xuất theo danh sách khách…") | unchanged entry; opens the dialog on scope "Danh sách khách" |
| ✓ "Xuất ảnh" step / `export_runs` | unchanged rule; files count includes subject duplicates |
| Close / switch while exporting | unchanged question; scan thread added to the same contract |
| Compare (Part 2) | untouched; Export is opened from the grid / bottom bar as today |
| Schema | unchanged (v7); confirmations kept in memory only |
| AI | no model runs during export; subject assignments only read |

## 8. Risks

| Risk | Level | Mitigation |
|---|---|---|
| Wrong external file copied (counter restart, second camera, renamed files) | high | 3.3 rules; ambiguous never automatic; preview + manifest list the match method |
| Slow scan of a large card / USB 2 reader | medium | background thread, progress, cancel; EXIF only for candidates |
| Subject folders duplicate many GB (group photos) | medium | totals count every operation; free-space check |
| Path too long on Windows | medium | explicit issue, never shortened silently |
| Users expect "Chưa xác định" photos to be assigned | low | preview hint + link to "Cần xem lại" |
| Dialog crowded on TINY | medium | tabs + scrolling; GUI tests at TINY / SHORT |
| Card ejected mid-copy | medium | fail-fast message; manifest; retry |
| Source changed or replaced after the preview | medium | revalidation before and during the copy (§3.6), `source_changed`, re-plan |
| Full hashing of large same-format sets takes time | medium | only candidates that pass the quick filter; one hash per file per dialog; plan thread with progress and cancel |

## 9. Reviewer answers (design checkpoint 1)

- **Q1** Remove "Giữ cấu trúc thư mục con" in the new UI; compatibility impact documented (§4, §7). → D11
- **Q2** Identical external duplicates are resolved automatically only after full-content (SHA-256) verification
  (§3.3 point 3). → D9
- **Q3** Standalone other rasters stay exported from the imported source under RAW_JPEG; other rasters are not matched
  externally in rev 2 (§3.2). → D10

## 10. Rev 1 → rev 2 delta

| Review item | Change | Sections |
|---|---|---|
| CR-P3-D01 content verification | quick fingerprint = filter only; byte identity = full SHA-256 for content matches, duplicates, already-present targets and copy verification; hashing only in worker threads, cancellable per 1 MiB chunk, cached once per file per dialog; `assets.sha256` reused when still valid | D9, §3.3.3, §3.6, §3.9, §5, §6.3, §6.6 |
| CR-P3-D02 other rasters | explicit list: Imported + RAW_JPEG keeps TIFF/PNG/HEIC; External matches RAW/JPEG only; JPEG-only excludes them; no conversion anywhere | D10, §3.2, §6.2 |
| CR-P3-D03 legacy migration | `include_pairs = false` → RAW + JPEG documented as a behaviour change with a one-time notice; equivalence tests only for `true` | D11, §4, §6.1, §7 |
| CR-P3-D04.1 folder fallback | one rule: no letter and no digit after sanitising → `Chủ thể <id>` | §3.4, plan Task 4 |
| CR-P3-D04.2 merged subjects | occurrences resolve through `merged_into` to the surviving subject (≤ 32 steps; cycle / missing → unresolved); `merge_subjects` normally leaves none | §3.4, §6.4, plan Task 4 |
| Additional safety case | source identity (size, mtime_ns, sha256 when known) recorded at plan / confirmation; revalidated before and during the copy; time matches re-read from the copied file; `source_changed` status | D12, §3.6, §3.7, §6.6, plan Task 7 |
| Q1–Q3 | answered | §9 |
