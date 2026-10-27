# Snorlu AI Culling

Offline, non-destructive photo culling for cosplay/street photographers (Windows desktop).
**Status: early development** — desktop culling app (import, grid, loupe with 100% zoom,
keyboard culling, copy export) works; offline AI groups photos by person and look
(calibrated on one labelled shoot), gives each person a technical score and picks N varied best
shots (first version: eyes-closed and aesthetics are not judged yet). See
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

## Dành cho người dùng (không cần biết lập trình)

1. Vào trang **[Releases](https://github.com/hophucluan131201-bit/snorlu-ai-culling/releases)** của dự án
   (cột bên phải trang GitHub → *Releases*).
2. Tải file **`Snorlu-AI-Culling-…-BoCai.zip`** trong phiên bản mới nhất.
3. Nhấp phải → *Extract All* → mở file **`HUONG_DAN_CAI_DAT.txt`** và làm theo (3 bước, không cần
   cài Git hay Python).

Dự án cá nhân, **phi thương mại**, chia sẻ miễn phí — xem [Giấy phép](#license--giấy-phép).

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
create). Every start is an empty session: click **📂 Nhập ảnh** and pick a shoot folder; photos are
only read. There are no projects to manage. Work is remembered per photo folder in hidden app data
(`%LOCALAPPDATA%\Snorlu\Snorlu AI Culling\sessions`): importing the same folder again brings back its
Keep/Reject/stars and client lists. A folder not opened for 30 days is forgotten automatically;
**↺ Làm lại** forgets the current folder immediately (asks first). Importing another folder switches
to that folder's session.

The toolbar switch **▦ Lưới ảnh | 🔍 Xem lớn** changes the view (the large view also has a
“◀ Về lưới ảnh (Esc)” button). A small cheat sheet of keys sits under the photos and follows the view;
hide/show it with **⌨ Phím tắt**, F1 lists everything.

| Key | Action |
|---|---|
| ← / → (↑ ↓ in grid) | previous / next photo |
| Space / Enter, Esc | loupe ↔ grid, back to grid |
| Z | true 100% zoom (full-resolution pixels) ↔ fit |
| + / − , mouse wheel | zoom closer (up to 800%, always on full-resolution pixels) / back |
| E | jump to the eyes of the main person (200% for small faces) to check focus; double-click = 100% there |
| K / X / U | keep / reject / clear flag (applies to all selected photos in the grid) |
| 1–5, 0 | star rating, clear rating |
| F | favorite |
| Ctrl+I / Ctrl+E | import folder / export |
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
CSV/JSON list into the `_snorlu_danh_sach` subfolder. Logs: `%LOCALAPPDATA%\Snorlu\Snorlu AI Culling\logs`.

**Step by step.** Nothing runs on its own; each button becomes available when the previous step is
done, so you can correct the result in between:
1. **📂 Nhập ảnh** — import only.
2. **🧠 Nhận diện người** — find and group people (GPU if available), then stop so you can fix groups.
3. **📊 Phân tích ảnh** — technical score of every person in every photo.
4. **⭐ Chọn ảnh** — pick N varied best shots; review with K/X; **⤴ Xuất ảnh**.

**People (🧠 Nhận diện người)** runs in the background. The **NGƯỜI** list shows each recognised person with a face thumbnail; click to
filter, double-click to name; tick the boxes of several people and press **🔗 Gộp người** in the
toolbar to merge them (or select several + right-click). Photos where the face is not
clearly visible are only *suggested* (a "?" badge) or listed under **Chưa xác định**. **Cần xem lại**
asks about pairs that look alike but are not certain. Right-click photos to confirm, remove from a
person, or assign to another person. All corrections survive re-analysis. Each correction is also kept as a learning example (numbers only: face/outfit similarity, time
gap, your answer) in `%LOCALAPPDATA%\Snorlu\Snorlu AI Culling\learning` — per Windows user, never
in the installer, so friends who install the app teach it their own way. Models: see
`docs/model-licenses.md`; fetch once with `python scripts/fetch_models.py`.

**Best shots (⭐ Chọn ảnh)**: 📊 Phân tích ảnh scores each person in each photo (sharpness at
the eyes measured on the full-resolution image, face quality, exposure, framing). The right panel
lists **Điểm mạnh** (strengths), **Điểm yếu** (weaknesses) and **Chưa đánh giá** (what could not be
judged, e.g. eyes closed and aesthetics — no model yet). ⭐ Chọn ảnh asks for N (per person, or in the current view) and picks the best
photos while skipping near-copies (same pose, same burst). Picked photos get an “AI” badge, go to
the top of the list (sorting box under the search field) and can be marked Keep automatically
(your own Keep/Reject is never changed). Review with K/X, then ⤴ Xuất ảnh → “Ảnh đã Giữ”.
Export **copies** only: the app never moves or deletes your originals.

## Check your own photo folder (read-only)

```powershell
.\.venv\Scripts\python -m app.ingest.cli "D:\Photos\Buoi chup" --verify --verify-untouched --json report.json
```

Reports, per file: camera, which preview is used, timings, orientation cross-check, and proves
with SHA-256 that no source file changed. Add `--full` to also time full-resolution loading.
Nothing is written next to your photos.

## Build the installer (Windows, for sharing)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Uses a separate `.venv-build` (Python 3.12, exact versions in `packaging/requirements-installer.txt`,
CPU ONNX Runtime — no CUDA, works on any PC), copies the SHA-256-verified models, builds the app with
PyInstaller (`packaging/snorlu.spec`), runs `Snorlu.exe --self-test` with the network blocked, then
writes `dist\installer\Snorlu-AI-Culling-<version>-portable.zip` and, if Inno Setup 6 is installed
(`winget install --id JRSoftware.InnoSetup -e`), `Snorlu-AI-Culling-Setup-<version>.exe` (per-user, no admin).
GitHub Actions can build the same on a clean Windows machine (`.github/workflows/build-windows.yml`,
run it from the Actions tab). Guide for testers: `packaging/notes/HUONG_DAN.txt`; notices:
`packaging/notes/LICENSES.txt`. The installer is not code-signed: Windows SmartScreen shows a warning.

## Tests

```powershell
.\.venv\Scripts\python -m pytest            # unit tests always; sample tests if test_photos/ exists
python scripts/raw_samples.py fetch         # DEV ONLY (network): download public RAW samples
```

`test_photos/` is git-ignored. Put private sample photos there; they are never committed.

## License / Giấy phép

Personal, **non-commercial** project. The Snorlu source code is licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE.md): free to use, copy, modify and share for any
noncommercial purpose; commercial use needs the author's permission. Bundled third-party software
and AI model weights keep their own licenses ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md),
[docs/model-licenses.md](docs/model-licenses.md)) — all of them allow this free, non-commercial
distribution; the non-commercial terms above apply to Snorlu's own code only.

Dự án cá nhân, phi thương mại: được dùng, sao chép, sửa, chia sẻ miễn phí; không bán lại hay dùng
thương mại khi chưa được tác giả đồng ý. Thư viện và mô hình AI đi kèm giữ giấy phép riêng của họ.
