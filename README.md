# Snorlu AI Culling

Offline, non-destructive photo culling for cosplay/street photographers (Windows desktop).
**Status: early development** — only the RAW/JPEG ingest layer exists. See
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

Specification: [`docs/TECHNICAL_SPEC_v1.1.md`](docs/TECHNICAL_SPEC_v1.1.md).
RAW support evidence: [`docs/raw-support-matrix.md`](docs/raw-support-matrix.md).

## Setup (Windows, PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

(Linux/macOS: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.)
Versions verified so far are in `requirements.lock.txt` (recorded on Linux).

## Check your own photo folder (read-only)

```powershell
.\.venv\Scripts\python -m app.ingest.cli "D:\Photos\Buoi chup" --verify --verify-untouched --json report.json
```

Reports, per file: camera, which preview is used, timings, orientation cross-check, and proves
with SHA-256 that no source file changed. Add `--full` to also time full-resolution loading.
Nothing is written next to your photos.

## Tests

```powershell
.\.venv\Scripts\python -m pytest            # unit tests always; sample tests if test_photos/ exists
python scripts/raw_samples.py fetch         # DEV ONLY (network): download public RAW samples
```

`test_photos/` is git-ignored. Put private sample photos there; they are never committed.
