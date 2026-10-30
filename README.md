# KiraPick

**[🇻🇳 Tiếng Việt](#-tiếng-việt)** · **[🇬🇧 English](#-english)**

*(trước đây tên là / formerly "Snorlu AI Culling" — dữ liệu cũ được chuyển tự động / earlier data is moved automatically)*

---

## 🇻🇳 Tiếng Việt

KiraPick là ứng dụng Windows giúp **lọc ảnh cosplay và chân dung bằng AI, chạy hoàn toàn offline**:
gom ảnh theo từng người, chấm điểm kỹ thuật (nét ở mắt, mắt nhắm/mở, mặt, ánh sáng, bố cục) và tự chọn ra
những tấm đẹp, khác dáng nhau để bạn duyệt lại.

- **Không cần Internet** sau khi cài; không gửi ảnh hay dữ liệu đi đâu.
- **Không bao giờ sửa, xoá, đổi tên hay di chuyển ảnh gốc.** Xuất ảnh = sao chép.
- Đọc RAW (Nikon NEF ưu tiên, Canon CR2/CR3, Sony ARW, …) và JPEG.
- **Bản 2.0** (chính thức): gom ảnh theo chủ thể bằng khuôn mặt **ArcFace** (InsightFace, chỉ dùng phi thương
  mại / nghiên cứu) và dáng người **YoutuReID**, **tự học** từ các lần bạn gộp / tách chủ thể, phát hiện mắt
  nhắm / nhìn xuống, *gợi ý thẩm mỹ* bằng AI (TOPIQ, phi thương mại)
  (xem [Lưu ý miễn trừ](#lưu-ý-miễn-trừ-trách-nhiệm--disclaimer)).
- Giới hạn: điểm chủ yếu là điểm kỹ thuật, gợi ý thẩm mỹ chỉ chiếm phần nhỏ; ngưỡng gom mới được kiểm tra trên
  một buổi chụp; luôn xem lại kết quả AI trước khi giao ảnh. Chi tiết: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) (tiếng Anh).

### Cài đặt (không cần biết lập trình)

1. Vào trang **[Releases](https://github.com/hophucluan131201-bit/KiraPick/releases)**
   (cột bên phải trang GitHub → *Releases*).
2. Tải file **`KiraPick-…-BoCai.zip`** của phiên bản mới nhất.
3. Nhấp phải → *Extract All* (Giải nén) → mở **`HUONG_DAN_CAI_DAT.txt`** và làm theo.
   Không cần cài Git hay Python.
4. Nếu Windows báo *“Windows protected your PC”*: bấm **More info → Run anyway**
   (bộ cài chưa có chữ ký số trả phí, không phải virus).

Máy cần Windows 10/11 64-bit. Có card đồ hoạ (NVIDIA, AMD, Intel) thì AI chạy trên card qua
DirectML; không có thì chạy bằng CPU.

### Cách dùng: 4 bước, mỗi bước xong sẽ dừng chờ bạn

1. **📂 Nhập ảnh** — chọn thư mục ảnh của một buổi chụp.
2. **🧠 Nhận diện chủ thể** — AI gom ảnh theo từng người. Kiểm tra danh sách **CHỦ THỂ** bên trái:
   tick ô vuông của nhiều người rồi bấm **🔗 Gộp chủ thể** nếu một người bị tách thành nhiều nhóm;
   chuột phải vào ảnh để bỏ ảnh khỏi một chủ thể, gán cho chủ thể khác, hoặc **➕ Tạo chủ thể mới** nếu đó là
   người chưa có trong danh sách. Ô phía trên danh sách đổi cách xếp (theo số, thời gian chụp, nhiều ảnh nhất,
   tên); nhấp phải vào danh sách → **🔢 Đánh số lại** để có số 1, 2, 3… liền nhau.
3. **📊 Phân tích ảnh** — chấm điểm từng người trong từng ảnh. Mỗi ảnh có hai điểm: **K – Kỹ thuật**
   (nét, mắt, mặt, sáng, bố cục, thẩm mỹ TOPIQ + LAION) và **G – Hợp gu bạn** (app tự học từ các lần bạn
   Giữ/Loại/cho sao/❤; chỉ hiện khi đã học đủ ≥ 60 lựa chọn và đoán đúng rõ hơn đoán mò). Bảng bên phải có
   thanh điểm và lý do cho từng tiêu chí; lưới ảnh hiện “K 78 · G 85” và xếp được theo K, G hoặc K + G.
   🎓 **AI đã học → So sánh ảnh…**: chọn tấm thích hơn trong từng cặp ảnh giống nhau để app học gu nhanh hơn.
   ⚙ **Tuỳ chọn**: tỷ lệ K/G, **🔄 Cập nhật mô hình AI** (cần mạng, chỉ khi bạn bấm).
4. **⭐ Chọn ảnh** — nhập số ảnh muốn chọn cho mỗi người (xếp theo K + G). Ảnh AI chọn có nhãn **AI** và xếp lên đầu.
   Duyệt lại bằng **K** (giữ) / **X** (loại) / **U** (bỏ đánh dấu), rồi **⤴ Xuất ảnh → Ảnh đã Giữ**.

Nút **▦ Lưới ảnh | 🔍 Xem lớn** để đổi chế độ xem. Bảng phím tắt nhỏ luôn hiện dưới khu vực ảnh
(ẩn/hiện bằng **⌨ Phím tắt**, **F1** xem đầy đủ).

| Phím | Tác dụng |
|---|---|
| ← / → (↑ ↓ trong lưới) | ảnh trước / sau |
| Space / Enter, Esc | xem lớn ↔ lưới, về lưới (Esc cũng đóng bộ lọc / bảng chi tiết đang mở ra) |
| Z | 100% (điểm ảnh gốc) ↔ vừa khung |
| + / − , cuộn chuột | phóng to tới 800% / thu nhỏ (luôn trên ảnh gốc) |
| E | phóng tới mắt người chính để xem nét; nháy đúp = 100% tại chỗ đó |
| P (hoặc K) / X / U | Chọn / Loại / Bỏ chọn (áp dụng cho mọi ảnh đang đánh dấu) |
| Tab | hiện / ẩn bảng chi tiết (cửa sổ thấp: lưới ↔ chi tiết) |
| ô tick, Ctrl/Shift + click | đánh dấu nhiều ảnh |
| C, G / Esc | **So sánh** 2–4 ảnh đã đánh dấu cạnh nhau; về lưới |
| 1–5, 0 | chấm sao, xoá sao |
| F | yêu thích |
| Q / W / R | chấm nét: nét căng / hơi soft / lệch nét – rung (bấm lại để bỏ); app học độ nét riêng cho từng máy + ống kính |
| Ctrl+I / Ctrl+E | nhập thư mục / xuất ảnh |
| Ctrl+F | tìm tên file (nhiều số cách nhau bằng dấu cách: `9645 9650`) |
| Ctrl+L | danh sách khách chọn: dán tin nhắn của khách, vd `9645, 9657-9660, DSC_9665.jpg` |

Khi đang gõ trong ô tìm kiếm (hoặc ô tìm chủ thể), các phím chữ và số chỉ để gõ — không chấm ảnh.

**So sánh (C):** đánh dấu 2–4 ảnh rồi bấm C (hoặc ⧉ So sánh). Ảnh dưới con trỏ chuột là ảnh đang chọn (viền
xanh): P / X / U / 1–5 / F / Q / W / R chỉ tác động lên ảnh đó, không tự sang ảnh khác. Mỗi ảnh phóng to riêng.
I bật / tắt dòng điểm AI trên mọi ảnh (K · G, ⚠, điểm yếu chính; ảnh chưa phân tích ghi "chưa phân tích"); nút
"Xếp" chọn Tự động / Một hàng / Lưới 2×2 (được nhớ). Esc hoặc G về lưới, giữ nguyên ảnh đang xem, các dấu đánh dấu và vị
trí cuộn.

**Bố cục tự thích ứng với cửa sổ:** màn hình rộng có cột bộ lọc bên trái và bảng chi tiết bên phải.
Chia đôi màn hình theo chiều dọc: bộ lọc thu thành dải biểu tượng (bấm để mở ra), bảng chi tiết hiện bên phải
từ 900 px (hẹp hơn thì trượt ra khi bấm **Tab** / **▤ Chi tiết**). Chia đôi theo chiều ngang (cửa sổ thấp):
lưới chiếm hết chỗ kèm một dòng tóm tắt ảnh, **Tab** để xem chi tiết bên dưới một hàng ảnh. Kéo đổi cỡ cửa sổ
không làm mất ảnh đang xem, ảnh đang đánh dấu, bộ lọc hay vị trí cuộn. Trên màn hình 150 % / 200 % hoặc khi
kéo thanh cỡ ảnh lớn, app tự làm ảnh nhỏ nét hơn (đọc ảnh gốc, không sửa).

**Danh sách khách chọn (📋 Khách chọn):** dán tin nhắn khách gửi; app hiểu số, khoảng
(`9657-9660`, `9657 đến 9660`, `9645-50`) và tên file đầy đủ, báo trước những số không tìm thấy.

**Xuất ảnh** chỉ **sao chép** (Giữ, Yêu thích, ≥ N sao, ảnh đang chọn hoặc danh sách khách). Ba lựa
chọn độc lập: ① **Nguồn** — thư mục đã nhập, hoặc nguồn khác (thẻ nhớ, ổ cứng: KiraPick chỉ đọc, file
cùng định dạng phải giống hệt từng byte, khác định dạng thì khớp theo giờ chụp ≤ 2 giây và cùng máy;
trường hợp không chắc bạn tự chọn "Dùng file này"); ② **Định dạng** — RAW + JPEG, chỉ RAW, chỉ JPEG
(không chuyển đổi); ③ **Thư mục đích** — một thư mục, hoặc mỗi chủ thể một thư mục (ảnh chưa rõ
người vào "Chưa xác định"). Cặp RAW+JPEG luôn cùng tên; không bao giờ ghi đè (file trùng tên khác nội
dung → tên mới " (1)"); file đã có giống hệt được bỏ qua; nút Dừng dừng ngay cả giữa một file lớn (file
dở dang bị xoá). Danh sách đầy đủ mọi file và lý do bỏ qua (CSV/JSON) nằm trong thư mục con
`_kirapick_danh_sach`; "Thử lại các file chưa chép" chép phần còn thiếu. Tab **📋 Tên ảnh đã Chọn**
sao chép tên ảnh (mỗi ảnh một dòng, báo khi có ảnh khác nhau trùng tên) mà không cần thẻ hay thư mục
đích. Tuỳ chọn cũ "Giữ cấu trúc thư mục con" đã bỏ.

**Dữ liệu của ứng dụng** (không phải ảnh): `%LOCALAPPDATA%\KiraPick` — `sessions` (ghi nhớ từng
thư mục ảnh, tự quên sau 30 ngày không mở; **↺ Làm lại** để quên ngay), `learning` (bộ nhớ học:
chỉ là các con số từ những lần bạn sửa nhóm người và Giữ/Loại, riêng cho từng máy), `logs` (gửi
kèm khi báo lỗi).

### Dành cho người phát triển

```powershell
cd D:\Dev
git clone https://github.com/hophucluan131201-bit/KiraPick.git
cd KiraPick
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1   # tạo .venv, cài thư viện, chạy kiểm thử
.\KiraPick.cmd                                                          # mở ứng dụng
powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcut.ps1   # biểu tượng trên Desktop
```

- Kiểm thử: `.\.venv\Scripts\python -m pytest`
- Tải mô hình AI (một lần, cần Internet): `.\.venv\Scripts\python scripts\fetch_models.py`
- Bộ cài: GitHub Actions tự build khi commit trên `main` có chữ `[release]`; build tay:
  `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1`

---

## 🇬🇧 English

KiraPick is a Windows app that **culls cosplay and portrait photos with AI, fully offline**: it
groups photos by person, gives each person a technical score (sharpness at the eyes, eyes
open/closed, face, exposure, framing) and picks the best, varied shots for you to review.

- **No Internet needed** after installation; no photo or data ever leaves the computer.
- **Never edits, deletes, renames or moves original photos.** Export = copy.
- Reads RAW (Nikon NEF first, Canon CR2/CR3, Sony ARW, …) and JPEG.
- **Version 2.0** (stable): groups photos by subject with **ArcFace** faces (InsightFace, non-commercial
  research use only) and **YoutuReID** whole-body vectors, **learns** from your merge / split
  corrections, detects closed / downcast eyes and gives an AI *aesthetic hint* (TOPIQ, non-commercial)
  (see the [disclaimer](#lưu-ý-miễn-trừ-trách-nhiệm--disclaimer)).
- Limits: scores are mostly technical, the aesthetic hint weighs little; grouping thresholds were
  checked on one shoot so far; always review AI results before delivering photos. Details: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

### Install (no programming needed)

1. Open the **[Releases](https://github.com/hophucluan131201-bit/KiraPick/releases)** page
   (right-hand column of the GitHub page → *Releases*).
2. Download **`KiraPick-…-BoCai.zip`** of the latest version (*bộ cài* = installer).
3. Right-click → *Extract All* → open **`HUONG_DAN_CAI_DAT.txt`** (Vietnamese guide) and run
   `KiraPick-Setup-….exe`. No Git or Python needed; no administrator rights needed.
4. If Windows shows *“Windows protected your PC”*: click **More info → Run anyway**
   (the installer is not code-signed; it is not a virus).

Requires Windows 10/11 64-bit. With a graphics card (NVIDIA, AMD, Intel) the AI runs on it through
DirectML; otherwise on the CPU.

### Use: 4 steps, each one waits for you

1. **📂 Nhập ảnh** (Import) — pick the folder of one shoot.
2. **🧠 Nhận diện chủ thể** (Find people) — AI groups photos by person. Check the **CHỦ THỂ** (people)
   list: tick several people and press **🔗 Gộp chủ thể** (merge) if one person was split; right-click
   photos to remove them from a subject, assign them to another, or **➕ Tạo chủ thể mới** (new subject) for
   someone not in the list yet. The box above the list changes its order (number, capture time, most photos,
   name); right-click the list → **🔢 Đánh số lại** renumbers subjects 1, 2, 3… in shooting order.
3. **📊 Phân tích ảnh** (Analyse) — scores every person in every photo. Two scores: **K – technical**
   (focus, eyes, face, light, framing, TOPIQ + LAION aesthetics) and **G – fits your taste** (learnt from
   your keeps/rejects/stars/❤; shown only after ≥ 60 decisions and when it predicts clearly better than
   chance). The right panel has a bar and a reason per criterion; the grid shows “K 78 · G 85” and sorts by
   K, G or K + G. 🎓 → **So sánh ảnh…** asks which of two similar photos you prefer, to learn faster.
   ⚙ Options: the K/G ratio and **🔄 AI-model update** (needs the Internet, only when you click it).
4. **⭐ Chọn ảnh** (Pick) — enter how many photos per person (ranked by K + G). AI picks get an **AI** badge and go
   first. Review with **K** (keep) / **X** (reject) / **U** (clear), then **⤴ Xuất ảnh → Ảnh đã Giữ**
   (export kept photos).

The **▦ Lưới ảnh | 🔍 Xem lớn** switch changes between grid and large view. A small cheat sheet of
keys sits under the photos (toggle with **⌨ Phím tắt**, **F1** shows all).

| Key | Action |
|---|---|
| ← / → (↑ ↓ in grid) | previous / next photo |
| Space / Enter, Esc | large view ↔ grid, back to grid (Esc also closes an open filter drawer / detail sheet) |
| Z | true 100% (full-resolution pixels) ↔ fit |
| + / − , mouse wheel | zoom up to 800% / back (always full-resolution pixels) |
| E | jump to the main person's eyes to check focus; double-click = 100% there |
| P (or K) / X / U | Chọn (keep) / Loại (reject) / clear (applies to every marked photo) |
| Tab | show / hide the detail panel (low windows: grid ↔ details) |
| tick box, Ctrl/Shift + click | mark several photos |
| C, G / Esc | **Compare** 2–4 marked photos side by side; back to the grid |
| 1–5, 0 | star rating, clear rating |
| F | favourite |
| Ctrl+I / Ctrl+E | import folder / export |
| Ctrl+F | search file names (several numbers separated by spaces: `9645 9650`) |
| Ctrl+L | client pick list: paste the client's message, e.g. `9645, 9657-9660, DSC_9665.jpg` |

While typing in the search box (or the people filter), letter and number keys only type — they never mark photos.

**Compare (C):** mark 2–4 photos and press C (or ⧉ So sánh). The photo under the mouse pointer is the active one
(blue frame): P / X / U / 1–5 / F / Q / W / R act on it only, with no auto-advance. Each photo zooms on its own.
I shows / hides the AI line on every photo (K · G, ⚠, main weakness; "chưa phân tích" without analysis); the
"Xếp" button picks Auto / One row / 2×2 grid (remembered). Esc or G returns to the grid with the current photo, the
marking and the scroll position unchanged.

**The layout adapts to the window:** wide screens show the filters on the left and the detail panel on the right.
A side-by-side Snap half folds the filters into an icon rail (click to slide them in) and keeps the details on
the right from 900 px (narrower: they slide in with **Tab** / **▤ Chi tiết**). A top/bottom Snap half (low
window) gives the grid the whole width with a one-line summary; **Tab** shows the details under a single row of
photos. Resizing keeps the current photo, the marking, the filter and the scroll position. On 150 % / 200 %
screens or with large cards, sharper thumbnails are made automatically (the photo is only read).

**Client pick lists (📋 Khách chọn):** paste what the client sent; numbers, ranges
(`9657-9660`, `9657 đến 9660`, `9645-50`) and full file names are understood, and names that match
no photo are reported before anything is saved.

**Export** only **copies** (kept, favourites, ≥ N stars, the selection or a client list). Three
independent choices: ① **source** — the imported folders, or another folder (card, drive: read only;
same format must be byte-identical, other format matches by capture time ≤ 2 s and camera; unsure cases
are confirmed by you); ② **format** — RAW + JPEG, RAW only, JPEG only (no conversion); ③ **layout** —
one folder, or one folder per subject (unknown → "Chưa xác định"). A RAW+JPEG pair keeps one name; nothing
is overwritten; identical files already there are skipped; Dừng stops even inside a large file (the
partial file is removed). A full list of every file and every skip reason (CSV/JSON) goes into
`_kirapick_danh_sach`; "Thử lại các file chưa chép" copies what is missing. The **📋 Tên ảnh đã Chọn** tab
copies the kept photos' names (one line per photo, warns about different photos with the same name)
without a card or destination. The old "Giữ cấu trúc thư mục con" option was removed.

**App data** (not photos): `%LOCALAPPDATA%\KiraPick` — `sessions` (memory of each photo folder,
forgotten after 30 days unused; **↺ Làm lại** forgets it now), `learning` (numbers only, from your
people corrections and keep/reject choices, per computer), `logs` (attach when reporting a bug).

### For developers

```powershell
cd D:\Dev
git clone https://github.com/hophucluan131201-bit/KiraPick.git
cd KiraPick
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1   # .venv, dependencies, tests
.\KiraPick.cmd                                                          # run the app
powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcut.ps1   # desktop shortcut
```

- Requirements: Git and Python 3.11–3.14 (`winget install --id Git.Git -e`,
  `winget install --id Python.Python.3.12 -e`). Linux/macOS: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
- Tests: `.\.venv\Scripts\python -m pytest` (sample-photo tests run when `test_photos/` exists; it is git-ignored).
- AI models (once, needs Internet; the app itself never downloads): `.\.venv\Scripts\python scripts\fetch_models.py`.
  The installer build also stores the large models' weights as float16 (`scripts/shrink_models.py`, checked against the originals).
  Licenses: [`docs/model-licenses.md`](docs/model-licenses.md).
- Read-only check of a photo folder:
  `.\.venv\Scripts\python -m app.ingest.cli "D:\Photos\Shoot" --verify --verify-untouched --json report.json`
- Installer: GitHub Actions builds it on Windows for commits on `main` containing `[release]`
  (`.github/workflows/build-windows.yml`): PyInstaller (`packaging/kirapick.spec`) with ONNX Runtime
  DirectML, SHA-256-verified models, `KiraPick.exe --self-test` with the network blocked, Inno Setup
  per-user installer, portable zip. Local build: `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1`.
- Specification: [`docs/TECHNICAL_SPEC_v1.1.md`](docs/TECHNICAL_SPEC_v1.1.md) · RAW support:
  [`docs/raw-support-matrix.md`](docs/raw-support-matrix.md).

---

## License / Giấy phép

**Tiếng Việt.** Dự án cá nhân, **phi thương mại**, chia sẻ miễn phí. Mã nguồn KiraPick theo giấy phép
[PolyForm Noncommercial 1.0.0](LICENSE.md): được dùng, sao chép, sửa và chia sẻ cho mục đích phi
thương mại; không bán lại hay dùng thương mại khi chưa được tác giả đồng ý. Thư viện và mô hình AI đi
kèm giữ giấy phép riêng của họ ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md),
[docs/model-licenses.md](docs/model-licenses.md)); tất cả đều cho phép chia sẻ miễn phí như thế này.

**English.** Personal, **non-commercial** project, shared for free. The KiraPick source code is licensed
under the [PolyForm Noncommercial License 1.0.0](LICENSE.md): free to use, copy, modify and share for
any noncommercial purpose; commercial use needs the author's permission. Bundled third-party software
and AI model weights keep their own licenses ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md),
[docs/model-licenses.md](docs/model-licenses.md)); all of them allow this free, non-commercial
distribution.

## Lưu ý miễn trừ trách nhiệm / Disclaimer

**Tiếng Việt.**
- KiraPick là dự án cá nhân, **phi thương mại**, chia sẻ miễn phí cho bạn bè dùng thử. Không bán, không thu
  phí, không quảng cáo; không dùng cho mục đích thương mại dưới bất kỳ hình thức nào.
- KiraPick dùng một số mô hình AI **chỉ được phép dùng phi thương mại / nghiên cứu**:
  khuôn mặt **ArcFace** của InsightFace (“chỉ dành cho nghiên cứu phi thương mại”) và chấm thẩm mỹ
  **TOPIQ** (PolyForm Noncommercial). Mô hình dáng người **YoutuReID** có giấy phép Apache-2.0 nhưng được
  huấn luyện trên các bộ dữ liệu nghiên cứu (Market-1501, DukeMTMC-reID, MSMT17). Từ 2.2 có thêm
  **TOPIQ** chấm kỹ thuật và chấm khuôn mặt (PolyForm Noncommercial; dữ liệu nghiên cứu KonIQ-10k, CGFIQA-40k)
  và **CLIP ViT-L/14 của OpenAI** (mã nguồn MIT; tài liệu của OpenAI ghi mọi việc đưa vào sử dụng thực tế
  “nằm ngoài phạm vi” và không dùng để nhận dạng khuôn mặt) cùng bộ chấm thẩm mỹ **LAION** (Apache-2.0):
  KiraPick chỉ dùng CLIP để chấm thẩm mỹ và học gu của bạn, trên máy của bạn. Bản quyền các mô hình này
  thuộc tác giả của chúng; KiraPick chỉ dùng lại, không sở hữu.
- **Ai tải hoặc dùng các bản có những mô hình này phải tự tuân theo giấy phép của chúng** và không được dùng
  KiraPick (hay mô hình bên trong) để kiếm tiền, nhận diện người cho dịch vụ, giám sát hay theo dõi ai.
  Muốn dùng thương mại thì phải gỡ các mô hình này và xin phép tác giả của chúng.
- Nhận diện người chỉ để **gom ảnh của chính bạn chụp** theo từng người trên máy của bạn. App chạy offline:
  ảnh, vector khuôn mặt và dữ liệu học không rời khỏi máy. Ngoại lệ duy nhất là **Cập nhật mô hình AI** (chỉ khi
  bạn bấm, hoặc khi bạn bật tự kiểm tra): chỉ tải danh sách mô hình đã ký số và file mô hình từ GitHub của
  KiraPick, không gửi gì của bạn đi. Hãy tôn trọng quyền riêng tư của người được chụp.
- Kết quả AI (gom người, điểm, chọn ảnh) có thể sai; hãy luôn tự kiểm tra trước khi giao ảnh. Phần mềm được
  cung cấp “nguyên trạng” (as is), không có bảo đảm; tác giả không chịu trách nhiệm cho thiệt hại phát sinh.
- Nếu bạn là tác giả của một mô hình và không muốn nó được dùng ở đây, hãy mở *Issue* trên GitHub; mô hình sẽ
  được gỡ.

**English.**
- KiraPick is a personal, **non-commercial** project shared for free with friends for testing. It is not
  sold, has no fees or ads, and must not be used for any commercial purpose.
- KiraPick uses AI models whose weights are licensed for **non-commercial / research use only**: InsightFace
  **ArcFace** (“available for non-commercial research purposes only”) and **TOPIQ** aesthetics (PolyForm
  Noncommercial). The **YoutuReID** whole-body model is Apache-2.0 but was trained on research datasets
  (Market-1501, DukeMTMC-reID, MSMT17). Since 2.2: **TOPIQ** technical and face quality (PolyForm
  Noncommercial; research datasets KonIQ-10k, CGFIQA-40k) and **OpenAI CLIP ViT-L/14** (code MIT; OpenAI's
  model card calls any deployed use out of scope and excludes face recognition) with the **LAION** aesthetic
  predictor (Apache-2.0); KiraPick uses CLIP only for aesthetics and your personal taste, on your computer.
  These models belong to their authors; KiraPick only reuses them.
- **Anyone who downloads or runs a build containing these models must comply with their licenses** and must
  not use KiraPick (or the models inside it) to make money, to identify people as a service, or for
  surveillance or tracking. Commercial use requires removing these models and the authors' permission.
- Person recognition only **groups your own photos** by person on your own computer. The app runs offline:
  photos, face vectors and learning data never leave the machine. The only exception is the **AI-model
  update** (when you click it, or if you switch on the daily check): it downloads only KiraPick's signed
  model list and model files from GitHub and sends nothing of yours. Respect the privacy of the people you photograph.
- AI results (grouping, scores, picks) can be wrong; always check before delivering photos. The software is
  provided “as is”, without warranty of any kind; the authors are not liable for any damage.
- If you are the author of a model and do not want it used here, open a GitHub *Issue* and it will be removed.
