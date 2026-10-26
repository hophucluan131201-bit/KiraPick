# Snorlu AI Culling

Offline, non-destructive photo culling for cosplay/street photographers (Windows desktop).
**Status: early development** — desktop culling app (import, grid, loupe with 100% zoom,
keyboard culling, copy export) works; AI subject grouping and scoring are not built yet. See
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

Specification: [`docs/TECHNICAL_SPEC_v1.1.md`](docs/TECHNICAL_SPEC_v1.1.md).
RAW support evidence: [`docs/raw-support-matrix.md`](docs/raw-support-matrix.md).

## Setup (Windows, PowerShell)

Requirements: Git and Python 3.11–3.14 (`winget install --id Git.Git -e`,
`winget install --id Python.Python.3.12 -e`). Use a normal (non-Administrator) PowerShell and a
work folder such as `D:\Dev` — not `C:\Windows\System32`.

```powershell
cd D:\Dev
git clone https://github.com/hophucluan131201-bit/snorlu-ai-culling.git
cd snorlu-ai-culling
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

The script picks a suitable Python, creates `.venv` inside the project, installs dependencies and
runs the tests. It changes nothing system-wide.
(Linux/macOS: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.)
Versions verified so far are in `requirements.lock.txt` (recorded on Linux).

## Run the app

Double-click **`Snorlu.cmd`** in the project folder (or the desktop shortcut the setup script can
create). Then click **📂 Nhập thư mục ảnh** and pick a shoot folder. A project (database + thumbnail
cache) is created under `Documents\Snorlu Projects\<folder name>`; photos are only read.

| Key | Action |
|---|---|
| ← / → (↑ ↓ in grid) | previous / next photo |
| Space / Enter, Esc | loupe ↔ grid, back to grid |
| Z | true 100% zoom (full-resolution pixels) ↔ fit |
| K / X / U | keep / reject / clear flag (applies to all selected photos in the grid) |
| 1–5, 0 | star rating, clear rating |
| F | favorite |
| Ctrl+I / Ctrl+E / Ctrl+O | import folder / export / open project |
| Ctrl+F | search file names (several numbers separated by spaces: `9645 9650`) |
| Ctrl+L | client pick list: paste the client's message, e.g. `9645, 9657-9660, DSC_9665.jpg` |

**Client pick lists** (📋 Khách chọn): paste what the client sent and the file-name pattern
(`DSC_####`, detected automatically). Numbers, ranges (`9657-9660`, `9657 đến 9660`, `9645-50`) and
full names are understood. The preview lists names that match no photo and names found in several
folders before anything is saved. The list appears under **Lọc → Danh sách khách** and in the export
dialog; it does not change your own Keep/Reject flags unless you tick that option.

Export copies the chosen photos (Kept, Favorites, ≥ N stars, or the selection), RAW+JPEG pairs
together, never overwrites (a different file with the same name gets " (1)"), skips photos already
exported there (identical bytes), refuses the shoot folder itself as destination, and writes a
CSV/JSON list into the `_snorlu_danh_sach` subfolder. Logs: `%LOCALAPPDATA%\Snorlu\AI Culling\logs`.

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
