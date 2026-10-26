# Implementation status

Statuses: **not started** / **implemented** (code exists, not fully tested) / **tested** (automated
tests pass in the dev container) / **blocked**. "Tested" here never means "verified on the target
Windows laptop" unless stated.

Last update: 2026-10-27 — dev container: Linux x86-64, Python 3.13.17, no GPU, no display. First Windows field test received (see raw-support-matrix.md).

## Target machine (from `scripts/diagnose_hardware.py`, 2026-10-27)

Windows 11 (10.0.26300), Python 3.12.10, NVIDIA GeForce RTX 2080 Super with Max-Q Design,
8192 MiB total / 7987 MiB free at idle, driver 617.14, 42 °C idle. PyTorch and ONNX Runtime not
installed yet (installed in M0 GPU step; an ONNX `CUDAExecutionProvider` inference test is still
required — a listed provider does not prove inference works).

## Milestones

| Milestone | Status | Notes |
|---|---|---|
| M0 Feasibility + safety | **partially done** | RAW feasibility done (see below). GPU/CUDA probe, model manifest, license matrix: not started — need the Windows laptop for CUDA |
| M1 Desktop MVP | **implemented + tested offscreen** | Ingest, storage, resumable import, PySide6 UI, keyboard culling, copy export. **Not yet confirmed by the user on the real Windows display** |
| M2 Identity | not started | |
| M3 Quality | not started | |
| M4 Best shot | not started | |
| M5 Local VLM | not started | |
| M6 Release | not started | |

## Done in this session — RAW/JPEG ingest (`app/ingest/`)

| Feature | Status | Evidence |
|---|---|---|
| Format registry with verified/unverified levels | tested | `formats.py`, `test_scanner_fingerprint.py` |
| RAW embedded preview + orientation (LibRaw flip) | tested | 31 real files, orientation cross-checked against LibRaw demosaic |
| Demosaic fallback (half / full) when preview too small | tested | Sony ARW, Leica DNG, Fuji RAF, ORF, RW2 |
| Full-resolution loader for 100% zoom (records source) | tested | `load_full_resolution`, `is_full_resolution` |
| Metadata: ExifRead + own CR3 `CMT` reader + embedded-JPEG fallback; no GPS/serials | tested | `metadata.py`, unit + sample tests |
| Damaged/stripped/truncated file detection (typed errors) | tested | size + consistency guards; stale-buffer regression test |
| Raster JPEG/PNG/TIFF (EXIF orientation, 16-bit) | tested | unit tests (synthetic) |
| Recursive scan: no symlink/junction following, hidden/system dirs skipped, cancel | tested | Linux; junctions untested (Windows only) |
| RAW+JPEG pairing by folder+stem, confirmed by capture time | tested | unit tests; wired into the import job (below) |
| Quick fingerprint (size + edge hashes) and full SHA-256 | tested | |
| `snorlu-raw-probe` CLI (read-only report, proves files untouched) | tested | integration test |
| Windows Unicode paths for RAW | tested | **on the user's Windows laptop**: 439 NEF in a Vietnamese path with `&`, 0 errors, sources unchanged |

Details and measurements: [`raw-support-matrix.md`](raw-support-matrix.md).

## Done — storage + import (`app/storage/`, `app/workers/import_job.py`)

| Feature | Status | Evidence |
|---|---|---|
| One SQLite DB per project, WAL, FK on; atomic versioned migrations; newer schema refused untouched | tested | `test_storage.py` (incl. injected failing migration rolls back) |
| Spec-review fixes in schema: partial unique indexes for NULL subject/occurrence; `measurements` (raw, preset-independent) separate from scores; per-asset `stage_status`; sources + relative paths for relink | tested | `test_storage.py`, `test_import_job.py` |
| Keep/reject, 1–5 stars, favorite (upsert, validated) | tested | survive file missing → returned |
| Import: register (fingerprint, duplicates across folders, changed/missing/returned files) | tested | `test_import_job.py` |
| Import: thread-pool thumbnails (400 px, atomic write) + metadata, failures isolated, failed files retried once | tested | |
| Cancel → job `paused`; resume processes only remaining files | tested | |
| **Process killed (SIGKILL) mid-import → resume loses nothing, redoes nothing, no corrupt thumbnails** | tested | Linux only; Windows has no SIGKILL equivalent test yet |
| RAW+JPEG pairs confirmed by capture time; duplicates/undecodable files never paired by name alone | tested | a real bug found by this test was fixed |
| Project folder inside the photo folder is excluded from scans | tested | |

Real-data smoke run: 42 sample files imported in 0.6 s (33 ok, 9 damaged files reported with reasons), unchanged re-import 0.03 s (dev container, 3 workers).

## Done — desktop UI + export (`app/ui/`, `app/export/`)

| Feature | Status | Evidence |
|---|---|---|
| Dark Vietnamese UI: folders/filters sidebar, thumbnail grid, inspector, status bar with counts | tested (offscreen) | `tests/gui/test_main_window.py`; screenshots reviewed with the user's NEFs |
| Import in a QThread with progress, pause/resume, auto-created project; UI event loop keeps running | tested | timer ticks during import |
| Async thumbnails (thread pool, LRU), RAW+JPEG pair shown once with "+JPG" badge | tested | |
| Loupe: 1600 px preview, **Z = true 100%** from `load_full_resolution`, stays at 100% when moving; filmstrip | tested | portrait EXIF-rotated case |
| Keys K/X/U/1–5/0/F/←/→/Space/Esc/Z; multi-select apply; optional auto-advance | tested | decisions survive restart |
| Filters: all / unflagged / keep / reject / favorite / ≥3★ / errors; per-folder | tested | |
| Broken files shown with reason, never crash the UI; unhandled errors -> dialog + log | tested / implemented | |
| Export: keep/favorite/≥N★/selection, preview table, free-space check, confirm, exclusive-create copies, pairs share stem, size verify, CSV (Excel-friendly UTF-8) + JSON | tested | `tests/integration/test_export.py` |
| Windows launcher `Snorlu.cmd`, optional desktop shortcut from setup script | implemented | not run on Windows yet |

| File-name search (sidebar, Ctrl+F, multi-token OR) | tested | typing digits never triggers rating shortcuts |
| Client pick lists: paste text + `DSC_####` pattern → parsed (numbers, ranges, shorthand `9645-50`, full names), unmatched/ambiguous report, saved as collection (schema v2), filter + export by list | tested | `tests/unit/test_client_list.py`, GUI test; requested by the user 2026-10-27 |
| Schema v2 migration (collections) upgrades existing v1 projects in place | tested | |
| **Session-per-folder** (user decision 2026-10-27): app always starts empty, no visible projects; hidden per-folder session in AppData restores work on re-import; 30-day purge removes only app-created session dirs; "↺ Làm lại" forgets a folder | tested | `tests/unit/test_sessions.py`, GUI tests. Replaces Documents\Snorlu Projects (old folder is not deleted automatically) |

Known gaps (M1 polish): no undo for decisions, no compare view (2–4 photos, planned with M4),
no thumbnail-size slider, no "clear cache" button, shortcuts not user-configurable yet.

## Test run

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
210 passed in 72.95s
```

Windows (user's laptop, Python 3.12, via `scripts/setup_windows.ps1`, 2026-10-27):
`48 passed, 117 skipped in 3.15s` — all synthetic tests pass; the 117 skipped are RAW-sample tests
(no `test_photos/` on that machine) plus POSIX-only symlink/SIGKILL tests.

Synthetic-data tests always run; RAW sample tests skip when `test_photos/` is absent.
Sample corpus: 5 user NEF (Nikon Z 5, private), 5 rawpy public samples, 22 multi-vendor samples
from `drewnoakes/metadata-extractor-images` (no license stated → local testing only), 10
metadata-only ExifTool files. Manifest with SHA-256: `tests/fixtures/raw_samples.json`.

## Spec review items to resolve before the matching milestone

1. Pose/eye-state/limb-crop criteria need a keypoint + face-landmark model not in the registry (M3).
2. Manual merge/split must survive re-detection: match new occurrences to old by bbox IoU, or store
   constraints at subject level (M2, schema).
3. Split `measurements` (preset-independent) from `scores` (preset-dependent) so reranking never
   recomputes (M1 schema).
4. Per-(asset, stage, version) job state for real pause/resume (M1 schema).
5. `decisions(asset_id, subject_id NULL)` unique constraint does not dedupe NULLs in SQLite.
6. Prefer ONNX Runtime at runtime; PyTorch only to export models (packaging size, CUDA pinning).
7. Naming nits: profile `rtx2080super_maxq_8gb` vs file `rtx2080_maxq_8gb.yaml`; spec §16.7 script
   name vs `scripts/diagnose_hardware.py`; `.gitignore` ignored `*.spec` (fixed).

Items 3, 4, 5 and 7 (`.gitignore`) are done in schema v1; 2 is designed for M2 (occurrence matching).

## Next

1. User runs the app on Windows (real display, HiDPI, real 439-photo folder) and reports issues.
2. M0 GPU step: install ONNX Runtime GPU, verify a real CUDA inference on the RTX 2080 Super Max-Q,
   model manifest + `docs/model-licenses.md`.
3. M2 identity: person/face detection, embeddings, subject groups with review queue.
