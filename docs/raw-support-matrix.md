# RAW support matrix (evidence)

Decoder: **rawpy 0.27.1 / LibRaw 0.22.1**, Pillow 13.0.0, ExifRead 3.5.1, Python 3.13.
Measured **2026-10-26 on the Linux dev container** (4 vCPU Xeon 2.1 GHz). These are *not*
measurements on the target Windows laptop (i7-10750H); re-run `snorlu-raw-probe` there.

"Verified" = a real, full camera file passed all of: embedded-preview decode, metadata
(make/model/capture time), orientation cross-check against LibRaw's own demosaic,
full-resolution load, and unchanged SHA-256 afterwards (`tests/integration/test_raw_samples.py`).

| Ext | Vendor | Real samples verified | Embedded preview | Full-res (100% zoom) source | Notes |
|---|---|---|---|---|---|
| **NEF** | Nikon | **Z 5 ×5 (user's own)**, D810, D5100, D4, D3S | full size (Z 5: 6016×4016) | embedded JPEG (camera-rendered) | Portrait frames: flip=5, preview stored landscape → rotated by us |
| CR2 | Canon | 5D Mark II, 70D, 40D sRAW | full size (40D: 1936) | embedded JPEG | Rebel XTi sample has corrupt sensor data → preview shown, full-res refused |
| CR3 | Canon | EOS R3, R8 ×4 (incl. C-RAW) | 6000×4000 | embedded JPEG | ExifRead can't parse CR3 → own `CMT1/CMT2` box reader |
| ARW | Sony | A7 IV, A7 III, A5000, NEX-7, NEX-5N, A500 | **1616×1080** (A7 IV: full) | **demosaic** (0.6–1.8 s here) | Small preview: fine for grid/analysis, not for focus checks |
| RAF | Fujifilm | X-E1 | 1920×1280 | demosaic (3.0 s here, X-Trans) | EXIF only via embedded JPEG; lowest preview↔demosaic similarity (0.22) |
| ORF | Olympus / OM System | OM-1, E-M10 | 3200×2400 | demosaic | OM-1 sample has unset clock (`0000:00:00`) → capture time reported missing |
| RW2 | Panasonic | DMC-GF7 | 1920×1440 | demosaic | |
| PEF | Pentax | K-1 Mark II | full size | embedded JPEG | |
| DNG | Leica (and others) | Leica T | **720×480** | demosaic | Grid uses tiny preview; analysis forces half-size demosaic |
| SRW | Samsung | NX1 | full size | embedded JPEG | |
| RWL | Leica | D-LUX (Typ 109) | 1920×1280 | demosaic | |
| NRW, CRW, SR2, SRF, 3FR, FFF, IIQ, KDC, DCR, MEF, MOS, MRW, ERF, X3F, RAW, GPR | various | **not verified** | – | – | Passed to LibRaw; shown as *unverified* in UI. Only metadata-stripped samples were available |

Grid thumbnail (320 px incl. metadata): median 30 ms, max 103 ms over 31 files on the dev container.
Analysis preview (1600 px): 50–335 ms. Full NEF demosaic (24 MP Z 5): ~2.2 s; half-size ~0.4 s.

## Failure handling (verified)

| Situation | Behaviour |
|---|---|
| Garbage bytes / not a RAW | `UnsupportedFormatError` ("damaged file or unsupported camera") |
| File cut to ≤ 0.2 % | `UnsupportedFormatError` (header gone) |
| Sensor data stripped / file far too small | `NoPreviewError` / `CorruptImageError` "sensor data missing (file too small)" |
| NEF cut anywhere 30–99 % (e.g. interrupted card copy) | grid preview shown; full-res → `CorruptImageError(LibRawIOError)` |
| Corrupt sensor data (LibRaw data error) | preview shown; full-res → `CorruptImageError(LibRawDataError)` |
| Empty file | `CorruptImageError` |

Two guards exist because LibRaw does **not** always fail on missing sensor data:

1. **Size guard** (deterministic): file bytes ÷ sensor pixels must be ≥ 0.05. Measured: real files
   0.47 (Canon C-RAW) … 2.7 B/px; stripped files ≤ 0.006 B/px.
2. **Consistency guard** (heuristic): a demosaiced image must resemble its own embedded preview
   (edge similarity ≥ 0.10; real files measured ≥ 0.22, unrelated images ≈ 0).

Found during this work: a stripped DNG decoded *successfully* when it followed real files in the
same process — LibRaw left a stale/uninitialised buffer. Regression test:
`test_stripped_file_rejected_even_after_decoding_real_files`.

## Known limits / to verify on Windows

- **Unicode paths on Windows**: LibRaw takes a narrow `char*` path; for non-ASCII paths we pass a
  file object (reads the whole file into RAM). Tested with Vietnamese paths on Linux only.
- Embedded JPEG colour: assumed sRGB. Nikon reports no `ColorSpace` tag in the samples; a camera set
  to AdobeRGB would render slightly desaturated until ICC handling lands (M1 follow-up).
- Full-res via embedded JPEG includes in-camera sharpening; focus scoring (M3) must record
  `source` and compare like with like.
- LibRaw prints diagnostics such as "Unexpected end of file" to stderr (includes the path); the
  packaged GUI has no console, but logs must not capture stderr verbatim.

Reproduce: `python scripts/raw_samples.py fetch` then `python -m pytest -m samples` or
`python -m app.ingest.cli test_photos --full --verify --verify-untouched`.
