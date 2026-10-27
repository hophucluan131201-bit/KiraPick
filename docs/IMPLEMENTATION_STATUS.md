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
| M0 Feasibility + safety | **tested** | RAW feasibility; AI runtime (offline-only providers, telemetry off, GPU→CPU fallback); model manifest + licenses. **CUDA verified on the RTX 2080 Super Max-Q** (2026-10-27, see below). OSNet/DINOv2 not fetched yet |
| M1 Desktop MVP | **tested** | Ingest, storage, resumable import, PySide6 UI, keyboard culling, copy export, search, client lists, per-folder sessions. Used by the user on Windows with a real 439-NEF shoot (2026-10-27): import, culling, export, session restore confirmed working. No installer yet (M6) |
| M2 Identity | **implemented + tested (synthetic + 7 real photos)** | Detection, face embeddings, look-first grouping (face + outfit within 5 min), people panel, review queue, manual corrections that survive re-analysis. **Calibrated on one labelled shoot only** (precision 1.00 / recall 0.76, thin margin); no body re-ID model yet (OSNet/DINOv2 blocked from dev container) |
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

## Done — AI foundation (`app/ai/`, M0/M2 groundwork)

| Feature | Status | Evidence |
|---|---|---|
| Model registry: SHA-256 pinned manifest, missing/corrupt detection, never downloads at runtime | tested | `tests/unit/test_ai.py` |
| ONNX Runtime: explicit CUDA/CPU allow-list (Azure cloud EP never used), telemetry events disabled, `preload_dlls` for pip CUDA, device read back from the session | tested on CPU | GPU path untested until run on the laptop |
| Person detection YOLOX (M on GPU, S on CPU), face detection YuNet at 640+1600 px, SFace 128-d embeddings, face→person association | tested on real photos | portrait, group booth (DSC_0010), no-people (ISS) |

Observed on the owner's photos (dev container, CPU): occluded/tilted faces (hands over face,
DSC_0198) score 0.34–0.43 → not used for identity (threshold 0.75); background people are detected
(0.5–0.64) and must be separated from the main subject in M2. Face similarities between apparently
different cosplayers reached 0.49 (SFace's generic threshold is 0.363): identity thresholds must be
calibrated on labelled photos of this user, and uncertain pairs go to review.

### First GPU run on the owner's laptop (`scripts/ai_check.py`, 20 NEF from the Aki shoot, 2026-10-27)

ONNX Runtime 1.31.1 (onnxruntime-gpu, CUDA 13 / cuDNN 9 from pip), providers listed:
TensorRT, CUDA, CPU (TensorRT is not used). Person detector session ran on **CUDA**.

| Stage | Device | Median | p95 | Found |
|---|---|---|---|---|
| Person detection YOLOX-M | CUDA | 119 ms | 134 ms | 32 persons |
| Person detection YOLOX-S | CPU | 103 ms | 112 ms | 36 persons |
| Face detection YuNet (2 scales) | CPU/OpenCV | 108 ms | 151 ms | 22 faces |
| Face embedding SFace | CPU/OpenCV | 10 ms | 29 ms | |

GPU memory: +337 MiB. Timings include pre/post-processing; YOLOX-M on CUDA is slower than
expected for this GPU (to profile: FP16, IO binding, preprocessing share, power state). Estimated
~0.25 s/photo → ~2 min for 439 photos (estimate from these medians, not a measured full run).

## Done — M2 identity (`app/identity/`, `app/workers/analyze_job.py`, people UI)

| Feature | Status | Evidence |
|---|---|---|
| Schema v3: occurrences (normalised boxes, prominence, main/background), vectors, reviewed "different" pairs | tested | migration from v2 in place |
| Analysis job: prefetch decode, YOLOX + YuNet + SFace, outfit colour, avatar crops, resumable per photo, failures isolated, re-analysis keeps occurrence ids (box IoU) | tested | `tests/gui` real-photo flow, rerun = 0 work |
| Grouping v2 (look-first): link if face ≥ 0.65 (any time); or within ±5 min outfit ≥ 0.85 and faces (if both visible) ≥ 0.55; or within ±5 min face ≥ 0.58 and outfit ≥ 0.70. Groups merge only if mean face similarity ≥ 0.45 (no chaining); same-photo cannot-link; manual seeds attract first; user exclusions and "different" pairs respected; face-less members only *suggested* ("?"); a face-less-only group needs ≥ 2 photos; stable subject ids; background people never grouped. Review queue: same outfit within 5 min, or face ≥ 0.45 within 30 min, or face ≥ 0.60 any time (max 30) | tested | `tests/unit/test_identity_cluster.py` (synthetic), `scripts/calibration/evaluate_grouping.py` (real labels) |
| UI: "🧠 Nhận diện người" (auto after import, background, pause/resume), NGƯỜI list with face avatars, person filter, "Chưa xác định", "?" badge for suggested photos, rename (double-click), tick people + "🔗 Gộp người" toolbar button (or right-click) to merge, keeping the named person, mark different, grid menu: confirm / remove from person / assign to person, review dialog, inspector lists people in the photo | tested offscreen | `test_people_recognition_flow_on_real_photos` |

### Grouping calibration (owner's "Test" shoot, 2026-10-25)

Data: debug bundle of 109 NEF (Nikon Z 5), 341 occurrences, 159 usable faces. Ground truth: 37 looks
in `scripts/calibration/labels_test_20261025.py` (6 groups from the owner, the rest labelled
visually from thumbnails by costume continuity — may contain mistakes). Metric: pairwise, per photo
(its most prominent main person). Reproduce: `python scripts/calibration/evaluate_grouping.py snorlu_debug.zip`.

| Rules | Precision | Recall | Wrong merges |
|---|---|---|---|
| v1 face-only (best pair ≥ 0.55, average ≥ 0.45) | 0.56 | 0.76 | many different cosplayers in one person |
| v2 look-first (current) | **1.00** | **0.76** | none; 4 face-less photos suggested |

Measured distributions: same look face similarity median 0.68 (p10 0.40); different looks max 0.63
(p99 0.53); outfit same look median 0.92, different looks p99 0.86. **The margin is thin**: two
different cosplayers in similar pink, 2–5 min apart, reached face 0.54 / outfit 0.91 — that is why
outfit links need face ≥ 0.55. Remaining splits are mostly single photos (profile, back view, mask);
7 of them are in the top 12 of the review queue. Not yet known: behaviour on other shoots, lighting,
masks; face-less looks (e.g. full-helmet mecha) stay unidentified — needs a body re-ID model.

## Test run

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
231 passed in 54.99s
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
