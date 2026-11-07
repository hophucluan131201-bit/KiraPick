# Checklist test bản đầy đủ — bản cập nhật sau 3.0.0 / 3.0.0a (phần nền LIC-1 + Media Mốc 1)

**Trạng thái:** bản nháp để chủ dự án **chốt thời điểm build và tổ chức test**. Chưa có bản build nào cho checklist này.
Mọi mục dưới đây cần **bộ cài thật** hoặc **ảnh thật**, nên không làm được trong CI ("chờ bản build cuối").

**Không làm trước khi chủ dự án duyệt:** build, bộ cài, tag, phát hành, merge `main`, sửa mặc định, thay / gỡ asset.

Ghi kết quả từng dòng: **Đạt / Không đạt / Không làm được** + ảnh chụp màn hình hoặc file báo cáo. Không đoán.

**Thứ tự:** (1) CI build các gói ở mục 0 và kiểm kê (mục G); (2) **chủ dự án tự kiểm trước** trên máy mình: G5, A1, A2,
mở được hai chế độ; (3) chỉ khi đạt mới mời người quen test các mục còn lại.

---

## 0. Gói trong đợt test

**Phiên bản đang phát hành** (bản người dùng đang có, dùng làm mốc nâng cấp và so hiệu năng):

| Dòng | Bản phát hành | Tag | Ngày |
|---|---|---|---|
| DirectML (mặc định) | **KiraPick 3.0.0** | `v3.0.0` | 2026-11-05 |
| CUDA (NVIDIA) | **KiraPick 3.0.0a** | `v3.0.0a` | 2026-11-05 |
| OpenVINO | không có bản 3.x | — | — |

**Gói đề xuất cho đợt test** (chủ dự án chốt khi build; số phiên bản mới = VER-1, chờ chốt):

| Gói | Có trong đợt test? | Ghi chú |
|---|---|---|
| DirectML — bộ cài (`KiraPick-<ver>-BoCai.zip`: Setup.exe + .bin) | **Có** | Gói chính cho người quen |
| DirectML — portable (`KiraPick-<ver>-portable.zip`) | **Có** | Cho máy không muốn cài |
| CUDA — bộ cài (Setup.exe + các .bin) | **Có** | Máy chủ dự án (RTX 2080 Super Max-Q) và người có card NVIDIA. Không kèm cuDNN (LIC-7 b) |
| CUDA — portable | Không có | Quá 2 GB (giới hạn GitHub) |
| OpenVINO | **Không** trong đợt này | Chưa có bản 3.x làm mốc; build riêng nếu chủ dự án muốn |

Điền sau khi build (lấy từ `package-inventory.md` trong gói tải của CI, mục G):

| Gói | Phiên bản | Commit | Run | File | SHA-256 |
|---|---|---|---|---|---|
| DirectML bộ cài | | | | | |
| DirectML portable | | | | | |
| CUDA bộ cài | | | | | |

---

## A. Cài đặt (mỗi bản: DirectML, CUDA, OpenVINO)

| # | Ca | Ghi lại |
|---|---|---|
| A1 | **Cài mới** trên máy chưa từng có KiraPick | Cài xong mở được; màn chọn chế độ hiện |
| A2 | **Nâng cấp** gói DirectML đè lên **KiraPick 3.0.0** đã cài; gói CUDA đè lên **KiraPick 3.0.0a** đã cài (dữ liệu cũ còn). Máy có bản thử nội bộ 3.0.1b1.dev*: ghi lại, bản thử nằm riêng không bị đè | Phiên Chụp cá nhân cũ mở được (có bản sao `.v7.bak`); P/X, sao, tên người giữ nguyên; nhóm tự động cũ bị ẩn theo DATA-1. CI đã tự chạy ca này trên máy sạch (mục G3) |
| A3 | Dọn file cũ khi nâng cấp (CLEAN-1, 26 đường dẫn) | Thư mục cài không còn trọng số ArcFace / TOPIQ; `KiraPick.exe --self-test` đạt |
| A4 | **CLEAN-2 — quyết định còn mở cho ca nâng cấp CUDA** (10 DLL cuDNN do 3.0.0a cài) | Hiện bộ cài **giữ** các file này. Sau khi nâng cấp từ 3.0.0a: ghi danh sách `cudnn*64_9.dll` còn trong thư mục cài (CI ghi sẵn ở mục G3) và provider thật. Cài mới: không được có file cuDNN nào |
| A5 | `KiraPick.exe --self-test kq.json` | `ok: true`, `network_attempts: []`; báo cáo A chỉ có trọng số `verified`; mục `media` chỉ có YOLOX / YuNet; `media.personal_has_media_tables: false` |
| A6 | Gỡ cài đặt | Ảnh gốc không đổi; dữ liệu `%LOCALAPPDATA%\KiraPick` còn (như các bản trước) |
| A7 | Tắt mạng (rút cáp / tắt Wi-Fi) rồi dùng cả hai chế độ | Mọi chức năng chạy; chỉ "Cập nhật KiraPick" báo không có mạng |

## B. GPU / CUDA

| # | Ca | Ghi lại |
|---|---|---|
| B1 | Bản CUDA, máy **chưa cài cuDNN 9** | Chạy bằng CPU; thanh trạng thái nêu lý do; `--self-test` → `cuda.cudnn_dll: null`, `cuda.setup_error` có lý do |
| B2 | Bản CUDA, máy **đã cài cuDNN 9** (theo `docs\HUONG_DAN_CUDNN.txt`) | `cuda.cudnn_dll` = đường dẫn thật của `cudnn64_9.dll`; provider thật của từng mô hình trong báo cáo A (`CUDAExecutionProvider`) |
| B3 | Bản DirectML, card NVIDIA / AMD / Intel | Provider thật trong báo cáo A; nếu rơi về CPU thì có lý do |
| B4 | Thời gian phân tích Media 1.000 và 5.000 ảnh (GPU và CPU) | Số phút; cửa sổ không treo; ⏸ Tạm dừng / chạy tiếp được |
| B5 | Thời gian phân tích Chụp cá nhân trên cùng máy, cùng thư mục ảnh | So với **3.0.0** (DirectML) / **3.0.0a** (CUDA). Ghi từng bước: bản 3.0.x còn chạy ArcFace / TOPIQ (đã gỡ), nên tổng thời gian không so trực tiếp được |

## C. Windows / màn hình

| # | Ca | Ghi lại |
|---|---|---|
| C1 | 1080p ở 100 %, 125 %, 150 % | Màn chọn chế độ, cửa sổ Chụp cá nhân, cửa sổ Media: chữ không bị cắt, nút không chồng nhau |
| C2 | 4K ở 150 % / 200 % | Ảnh thu nhỏ nét; thẻ ảnh Media đọc được nhãn |
| C3 | Biểu tượng emoji trên nút (📂 🕒 🧠 🏷 ⤴) | Hiện đúng phông Segoe UI Emoji |
| C4 | Hai màn hình, kéo cửa sổ sang màn có DPI khác | Không vỡ bố cục |

## D. Hồi quy Chụp cá nhân

| # | Ca | Ghi lại |
|---|---|---|
| D1 | Bảng 11 bước của bản RC (`docs/owner-acceptance-rc.md`), **đối chiếu phạm vi hiện tại** (bảng dưới) | Từng bước Đạt / Không đạt |
| D2 | **Luồng gom thủ công: GRP-1** (`docs/owner-trial-grp1.md`) thay bước 3–4 của D1 | Số liệu `KiraPick.exe --grp1-counts` |
| D3 | Không có nhận mặt (SFace `pending`) | Gom người chỉ gán tay; thông báo đúng; không có điểm thẩm mỹ giả |

**D1 đối chiếu phạm vi hiện tại** (bảng RC viết cho 3.0.0b1a, khi còn ArcFace / TOPIQ):

| Bước RC | Còn dùng? | Làm thế nào ở bản này |
|---|---|---|
| 1 Nhập ảnh, cặp RAW+JPEG | Giữ | Tiêu đề ghi phiên bản mới |
| 2 Nhận diện chủ thể + Phân tích ảnh | **Đổi** | Chỉ dò người / mặt và đo kỹ thuật; ghi provider và thời gian. **Không** có điểm thẩm mỹ (TOPIQ, LAION đã gỡ / `pending`): không có số giả nào thay vào |
| 3 Xem cột Chủ thể (nhóm tự động) | **Thay bằng GRP-1** | Không có nhóm tự động (SFace `pending`, nhóm ArcFace cũ bị ẩn); gom tay theo D2 |
| 4 Gộp hai chủ thể + Ctrl+Z | **Thay bằng GRP-1** | Gộp / tách / hoàn tác trên nhóm gom tay (D2) |
| 5–9 Lọc P/X/sao, So sánh, Xuất (3 cách) | Giữ | Như bảng RC |
| 10 Đóng / mở lại | Giữ | Thêm: nhóm gom tay còn nguyên |
| 11 Dấu vân tay ảnh gốc | Giữ | Hai file CSV giống hệt |

## E. Media Mốc 1 — luồng chức năng (ảnh của chủ dự án)

| # | Ca | Ghi lại |
|---|---|---|
| E1 | Tạo sự kiện, 📂 nhập **hai thư mục của hai máy** | Hai nguồn máy; ảnh xếp theo giờ |
| E2 | 🕒 chỉnh giờ (nhập giây, và "Tính từ 2 ảnh đang chọn"); Ctrl+Z | Giờ đã chỉnh đúng; EXIF / ảnh gốc không đổi |
| E3 | 🧠 Phân tích sự kiện; ⏸ giữa chừng; chạy tiếp | Nhãn hiện dần; ảnh chưa xong có ⏳; nhãn AI có "(thử nghiệm)" |
| E4 | Lọc 3 nhóm (cỡ cảnh, nội dung, lỗi nét) + nguồn + khoảnh khắc + trạng thái + P/X | Kết quả lọc đúng |
| E5 | Phím P, X, **Backspace**, F, **Alt+0…5**, T/U/C, 1–5, Space, Ctrl+Z | Đúng như ghi chú dưới cửa sổ; **trong ô nhập chữ** (ô đổi tên…) các phím này chỉ gõ chữ |
| E6 | Tách tại đây → 🧠 Phân tích lại → Ctrl+Z (R1-UNDO-AI) | Thông báo "…cũng khôi phục cách chia khoảnh khắc trước đó…"; P/X và nhãn đã xác nhận không đổi |
| E7 | ⚠ lệch giờ: Chuyển / Giữ | Đúng như đặc tả MED-03 |
| E8 | ⤴ Xuất ảnh theo khoảnh khắc và theo cỡ cảnh | Xem trước trước khi chép; ảnh P chưa có khoảnh khắc vào "Chưa chia khoảnh khắc"; hai máy trùng tên file ra hai file; file có sẵn không bị đè; ảnh gốc không đổi |
| E9 | Cùng thư mục ảnh ở Chụp cá nhân và ở sự kiện, P/X khác nhau; đổi chế độ qua lại | Mỗi bên giữ P/X của mình |
| E10 | Xoá sự kiện | Chỉ mất dữ liệu KiraPick của sự kiện; ảnh gốc còn nguyên |

## F. Dán nhãn ảnh thật và chấm (spec §11)

**Trước khi bắt đầu (MED-SAMPLE):** với hai album VNNIC (19/6 chính, 18/6 bổ sung), kiểm và ghi lại: **số ảnh** truy cập
được, **độ phân giải**, **EXIF** (giờ chụp, hãng / dòng máy), **quyền sử dụng** (điều khoản trang, ai giữ bản quyền).
Chưa có quyền rõ ràng thì **không** dùng ảnh album; dùng ảnh gốc của chính chủ dự án. Ảnh không bao giờ vào repo / CI.

| # | Ca | Ghi lại |
|---|---|---|
| F1 | 🏷 Dán nhãn mẫu ~100–150 ảnh: cỡ cảnh, nội dung, Nét / Out nét / Trật nét, B (bắt đầu khoảnh khắc), 0 (chưa đánh giá) | Số ảnh đã dán |
| F2 | `KiraPick.exe --media-score "<sự kiện>" --out kq.json` | Gửi `kq.json` (chỉ có số) |
| F3 | **Tách tập chỉnh ngưỡng khỏi tập chấm:** lệnh tự chia theo khoảnh khắc (~40 % / ~60 %). Chỉ đọc tỉ lệ ở tập chấm; ngưỡng đề xuất lấy từ tập chỉnh ngưỡng và **không** tự áp dụng | `samples.tuning_set_photos`, `samples.scoring_set_photos` |
| F4 | Nhóm dưới 15 mẫu | Ghi "chưa đủ mẫu", không kết luận |
| F5 | **Ghi riêng các ca khó** (đánh dấu trong ghi chú, chấm riêng bằng tay nếu ít): | |
| F5a | — ảnh có **màn LED / màn chiếu** phía sau (bão hoà và chưa bão hoà, FC-02b / FC-06) | Số ảnh; AI báo gì |
| F5b | — ảnh **ISO cao, nhiễu** (FC-05 và mặt mờ có nhiễu) | Số ảnh; AI báo gì |
| F5c | — **chủ thể có chi tiết chủ yếu theo một hướng** (áo sọc, rèm, vách kẻ ngang / dọc): giới hạn đã biết, có thể bị báo Out nét nhầm | Số ảnh; AI báo gì |
| F5d | — áo trắng sáng còn chi tiết (FC-07) | Số ảnh; AI báo gì |
| F6 | Ngưỡng nét hiện tại (0,25 / 0,40 / ×1,8) **giữ nguyên** trong đợt thử | Chỉ đổi sau khi có số ở tập chỉnh ngưỡng |

## G. Kiểm trên chính bộ cài gửi người test (căn cứ phân phối)

Làm trên **đúng các file** sẽ gửi đi (mục 0), không trên bản build khác. CI tự làm G1–G3 trong lần build; chủ dự án làm
G5 trên máy mình.

| # | Bước | Ghi lại |
|---|---|---|
| G1 | **Kiểm kê từng gói** (CI, `scripts/package_inventory.py`): phiên bản, commit, run, kích thước và SHA-256 từng file | `package-inventory.md` trong gói tải của CI; chép vào bảng mục 0 |
| G2 | **Kiểm gói P1–P4** trên thư mục chương trình của chính gói đó: trọng số = đúng danh sách `verified` có SHA-256 ghim; không ArcFace / TOPIQ / CLIP / LAION / YoutuReID / SFace; không FFmpeg, TensorRT, cuDNN; đủ văn bản giấy phép trong `docs\licenses\`; CUDA có `docs\HUONG_DAN_CUDNN.txt` | `package-inventory.md`: "đạt" |
| G3 | **Cài thử trên máy CI sạch:** cài mới bản thử (thư mục riêng) và nâng cấp đè 3.0.0 / 3.0.0a; kiểm P1–P4 trên thư mục **đã cài**; self-test của bản đã cài | `installed-inventory.md`, `upgraded-inventory.md`; dòng "CLEAN-2" liệt kê DLL cuDNN còn lại sau nâng cấp CUDA |
| G4 | Đối chiếu tài liệu: `configs/model-policy.json`, `docs/model-licenses.md`, `docs/legal/danh-sach-file-ban-tiep-theo.md`, `THIRD_PARTY_NOTICES.md` | Không có thành phần nào trong gói mà tài liệu không nêu |
| G5 | **Chủ dự án, trước khi mời người test:** tải gói, kiểm SHA-256 bằng PowerShell (lệnh dưới) khớp mục 0; cài mới trên một máy / tài khoản Windows chưa có KiraPick; nâng cấp trên máy đang có 3.0.0 hoặc 3.0.0a; mở được **cả hai chế độ** (Chụp cá nhân, Media) | Đạt cả bốn thì mới mời người quen |

```powershell
Get-FileHash "D:\Tai\KiraPick-<ver>-BoCai.zip" -Algorithm SHA256
```

## H. Còn chờ quyết định riêng

- **CLEAN-2** (ca nâng cấp CUDA từ 3.0.0a): giữ hay xoá 10 DLL cuDNN do 3.0.0a đã cài. Hiện giữ.
- **MED-SAMPLE**: chờ xác minh số ảnh, độ phân giải, EXIF, quyền sử dụng của hai album; chưa đủ điều kiện thì dùng ảnh
  gốc của chủ dự án.
- **DOC-1**: bản nháp ở `docs/legal/doc-1-ban-nhap.md` (điều khoản dùng thử, phạm vi dùng cho job có thu tiền: trình
  riêng). Ghi chú phát hành hoàn thiện sau khi có kết quả test. `LICENSE.md` chưa sửa.
- Mời người test, merge `main`, tag, phát hành công khai: quyết định riêng của chủ dự án.
- Thời điểm build, danh sách người test: chủ dự án quyết định.
