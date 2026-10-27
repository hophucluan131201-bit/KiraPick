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
| M3 Quality | **implemented + tested (synthetic + 7 real NEF)** | Per-person technical score: eye/face/body sharpness on the full-resolution image, eDifFIQA face quality, face/person exposure, framing; N/A redistribution + confidence; warnings. **Not measured: eyes closed, aesthetics** (no suitable offline model yet). Rubric mappings are starting values, not calibrated on the owner's choices |
| M4 Best shot | **implemented + tested (synthetic)** | ⭐ Chọn ảnh: N per person or N in the current view, greedy MMR (λ 0.75) over score vs near-copy redundancy (layout similarity rescaled 0.85→0.97, same burst = copy), picks first then by score, optional Keep marks (never overrides user flags). No compare view yet; no burst table (bursts = same person ≤ 1.5 s apart) |
| M5 Local VLM | not started | |
| M6 Release | **implemented; Windows build not yet run** | CPU installer: PyInstaller onedir + Inno Setup per-user, verified models (YuNet, SFace, YOLOX-S, eDifFIQA; YOLOX-M GPU-only not shipped), `--self-test` with network blocked, portable zip, CI workflow. Verified here: Linux PyInstaller build launches and passes the self-test offline. **Not verified: the Windows build/installer itself** (no Windows machine in this environment); unsigned (SmartScreen warning); no GPU variant yet; no app license chosen yet |

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
| Grouping v2 (look-first): link if face ≥ 0.65 (photos > 5 min apart also need outfit ≥ 0.65, unless face ≥ 0.80); or within ±5 min outfit ≥ 0.80 and faces (if both visible) ≥ 0.55; or within ±5 min face ≥ 0.55 and outfit ≥ 0.78. Outfit = HSV histograms of 3 bands (hair, upper, lower body) of the central 60% of the person box at 400 px; older vectors are recomputed from cached thumbnails before regrouping (no models needed). Groups merge only if mean face similarity ≥ 0.45, or ≥ 0.60 when no photos of the two are within 5 min (no chaining); same-photo cannot-link; manual seeds attract first; user exclusions and "different" pairs respected; face-less members only *suggested* ("?"); a face-less-only group needs ≥ 2 photos; stable subject ids; background people never grouped. Review queue: same outfit within 5 min, or face ≥ 0.45 within 30 min, or face ≥ 0.60 any time (max 30) | tested | `tests/unit/test_identity_cluster.py` (synthetic), `scripts/calibration/evaluate_grouping.py` (real labels) |
| UI: "🧠 Nhận diện người" (started by the user, no longer automatic after import; background, pause/resume), NGƯỜI list with face avatars, person filter, "Chưa xác định", "?" badge for suggested photos, rename (double-click), tick people + "🔗 Gộp người" toolbar button (or right-click) to merge, keeping the named person, mark different, grid menu: confirm / remove from person / assign to person, review dialog, inspector lists people in the photo | tested offscreen | `test_people_recognition_flow_on_real_photos` |

## Done — M3 quality + M4 selection (`app/quality/`, `app/workers/quality_job.py`, `app/ai/face_quality.py`)

| Feature | Status | Evidence |
|---|---|---|
| Stage `quality` after detection, resumable per photo; full-resolution source recorded (`embedded_jpeg` on the owner's Z 5 NEFs = 6016×4016); measurements stored as JSON per occurrence (`measurements`), layout vector in `occurrence_vectors` | tested | GUI real-photo flow asserts full-res source and eye sharpness |
| Eye sharpness: YuNet re-run on the full-res face crop for landmarks, steepest-edge/contrast metric (≈1 = 1-px edge). Owner's NEFs: sharp eyes 0.48–0.81, defocused background face 0.08; synthetic blur monotone | tested | `tests/unit/test_quality.py` |
| Rubric `cosplay-tech-v1`: focus 35, face 25, exposure 20, framing 20; N/A re-weighted, confidence; low-key tolerated; warnings (lệch nét, mặt khó thấy, mặt cháy sáng, đầu chạm mép) | tested | unit tests |
| Selection: per person or in view, MMR diversity, saved run (`picks`, schema v4), “AI” badge, sort modes (time / score / AI picks first), inspector breakdown | tested offscreen | `test_ai_selection_puts_picks_first_marks_keep_and_explains` |
| Taste examples: each Keep/Reject on a scored photo → learning store v2 (`culling_feedback`: score parts, AI rank, decision) | tested | `tests/unit/test_learning.py` |

Workflow is step by step (owner's request 2026-10-27): import → 🧠 Nhận diện người (detect + group,
then stop for corrections) → 📊 Phân tích ảnh (quality only) → ⭐ Chọn ảnh; each button is enabled
only when the previous step has results and nothing is running (`_update_steps`). The inspector
explains a score as strengths / weaknesses / not judged, each item tied to a measurement.

Owner feedback 2026-10-27 (fixed): zoom beyond 100% (+/−, wheel up to 800%, double-click, **E** =
jump to the main person's eyes; any zoom loads full-resolution pixels first); the number box no
longer has an editable "N = " prefix; "every person N photos" used to be limited to the person shown
in the grid — it now always covers every person of the folder and switches the grid to all photos.

Owner report 2026-10-27: Ctrl/Shift+click did not select several photos — in the loupe's filmstrip
(single selection, keys applied only to the shown photo). Fixed: the filmstrip shares extended
selection with the grid and K/X/U/stars apply to every selected photo there too.

Owner feedback 2026-10-27 (UI): no obvious way back from the large view. Added a "▦ Lưới ảnh |
🔍 Xem lớn" switch in the toolbar (active one highlighted), a "◀ Về lưới ảnh (Esc)" button on the
large view, and a small cheat sheet of keys under the photos that follows the current view
(toggle "⌨ Phím tắt", remembered; F1 = full list).

Owner question 2026-10-27: why a 74-point photo was picked over 79/78-point ones (DSC_9929 vs
9939/9933). The raw HOG layout similarity rewarded a portrait→landscape crop and punished real pose
changes (measured on the full shoot: bursts ≤ 1.5 s median 0.98, different poses of one look 0.87).
Fixed: only near-copies are penalised (rescaled 0.85→0.97), quality weight 0.75; the right panel
says why each photo was picked or left out.

Export stays **copy only**: the owner asked for “copy or move”; moving would delete the source files,
which the product invariants forbid. Timing on the owner's 7 NEFs (CPU, dev container): detection +
quality 5.8 s for 7 photos (quality ≈ 0.1–0.3 s/photo + full-res JPEG decode 0.1–0.7 s).

### Learning from the user's corrections (step 1: recording)

Every people correction (merge, "different people", remove from person, assign/confirm) is
turned into examples: pairs of occurrences with face similarity, outfit similarity, time gap and
the user's answer. They are stored per Windows user in
`%LOCALAPPDATA%\Snorlu\Snorlu AI Culling\learning\learning.db` (`app/learning/`), survive the
30-day session purge, are never part of an installer (each friend starts from the defaults), and
contain no images, file names, paths, names or capture dates. Errors there never block a
correction. Tested: `tests/unit/test_learning.py`.
**Not yet:** using the examples (per-user threshold tuning with a safety check against past
answers), a "forget what was learnt" button, and taste learning from Keep/Reject/stars (needs M3
quality measurements first).

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

Owner's full shoot (439 NEF, 2026-10-27, screenshots): two pairs of *different* cosplayers hours
apart were merged (DSC_9664–9678 with DSC_9957–9964; DSC_9771–9788 with DSC_9954–9955) by single
face pairs ≥ 0.65. Fix: face links across more than 5 min need a compatible outfit, and far-apart
groups need mean face ≥ 0.60.

Full shoot debug bundle (2026-10-27): the owner found one more wrong merge, DSC_9754/9757 with
DSC_9763–9770 (two cosplayers in pink and white, 4 min apart, face 0.58, old outfit histogram
0.87). The old whole-box histogram was dominated by shared colours and background. The banded
central-strip descriptor separates looks better on the labelled pairs ≤ 5 min apart
(AUC 0.896 → 0.945; same look median 0.88, different looks p90 0.74). Labels for the whole shoot:
`scripts/calibration/labels_aki_20261025.py` (46 looks, 431 photos; owner's groups + visual).

| Full shoot, 431 labelled photos | Precision | Recall | Groups for 46 looks |
|---|---|---|---|
| before (whole-box histogram) | 0.996 | 0.830 | 67 |
| now (banded descriptor, retuned) | **1.000** | 0.817 | 73 |

The Test subset (old labels) measures 1.000 / 0.725 now. Remaining splits are mostly 1–3 photo
stragglers (profile, motion blur, hands over face) that the owner can merge with the tick boxes +
"🔗 Gộp người".

## Test run

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
253 passed in 55.34s
```

Windows (user's laptop, Python 3.12, via `scripts/setup_windows.ps1`, 2026-10-27):
`48 passed, 117 skipped in 3.15s` — all synthetic tests pass; the 117 skipped are RAW-sample tests
(no `test_photos/` on that machine) plus POSIX-only symlink/SIGKILL tests.

Synthetic-data tests always run; RAW sample tests skip when `test_photos/` is absent.
Sample corpus: 5 user NEF (Nikon Z 5, private), 5 rawpy public samples, 22 multi-vendor samples
from `drewnoakes/metadata-extractor-images` (no license stated → local testing only), 10
metadata-only ExifTool files. Manifest with SHA-256: `tests/fixtures/raw_samples.json`.

## Spec review items to resolve before the matching milestone

1. Pose/eye-state/limb-crop criteria need a keypoint + face-landmark model not in the registry (M3): MediaPipe Pose evaluated and rejected (see model-licenses.md); eye state still open.
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
