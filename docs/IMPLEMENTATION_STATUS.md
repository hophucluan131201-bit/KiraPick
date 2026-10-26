# Implementation status

Statuses: **not started** / **implemented** (code exists, not fully tested) / **tested** (automated
tests pass in the dev container) / **blocked**. "Tested" here never means "verified on the target
Windows laptop" unless stated.

Last update: 2026-10-26 — dev container: Linux x86-64, Python 3.13.17, no GPU, no display.

## Milestones

| Milestone | Status | Notes |
|---|---|---|
| M0 Feasibility + safety | **partially done** | RAW feasibility done (see below). GPU/CUDA probe, model manifest, license matrix: not started — need the Windows laptop for CUDA |
| M1 Desktop MVP | **partially done** | Ingest layer done. SQLite, PySide6 UI, export: not started |
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
| RAW+JPEG pairing by folder+stem, confirmed by capture time | tested | unit tests; not yet wired to a DB |
| Quick fingerprint (size + edge hashes) and full SHA-256 | tested | |
| `snorlu-raw-probe` CLI (read-only report, proves files untouched) | tested | integration test |
| Windows Unicode paths for RAW | implemented | file-object path for non-ASCII on Windows; **needs Windows test** |

Details and measurements: [`raw-support-matrix.md`](raw-support-matrix.md).

## Test run

```
$ .venv/bin/python -m pytest -q
148 passed in 51.47s
```

33 unit tests (synthetic data, always run) + 115 sample tests (skip when `test_photos/` is absent).
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

## Next

M1 continued: SQLite schema + migrations (with items 2–5 above), import job using `scan_folder` +
fingerprints + pairing, thumbnail cache, then the PySide6 shell.
