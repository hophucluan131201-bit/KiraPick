# Checklist test bản đầy đủ — bản cập nhật sau 3.0.1 (phần nền LIC-1 + Media Mốc 1)

**Trạng thái:** bản nháp để chủ dự án **chốt thời điểm build và tổ chức test**. Chưa có bản build nào cho checklist này.
Mọi mục dưới đây cần **bộ cài thật** hoặc **ảnh thật**, nên không làm được trong CI ("chờ bản build cuối").

**Không làm trước khi chủ dự án duyệt:** build, bộ cài, tag, phát hành, merge `main`, sửa mặc định, thay / gỡ asset.

Ghi kết quả từng dòng: **Đạt / Không đạt / Không làm được** + ảnh chụp màn hình hoặc file báo cáo. Không đoán.

---

## A. Cài đặt (mỗi bản: DirectML, CUDA, OpenVINO)

| # | Ca | Ghi lại |
|---|---|---|
| A1 | **Cài mới** trên máy chưa từng có KiraPick | Cài xong mở được; màn chọn chế độ hiện |
| A2 | **Nâng cấp** từ 3.0.0a / 3.0.1 (dữ liệu cũ còn) | Phiên Chụp cá nhân cũ mở được; P/X, sao, tên người giữ nguyên; nhóm tự động cũ bị ẩn theo DATA-1 |
| A3 | Dọn file cũ khi nâng cấp (CLEAN-1, 26 đường dẫn) | Thư mục cài không còn trọng số ArcFace / TOPIQ; `KiraPick.exe --self-test` đạt |
| A4 | **CLEAN-2** (10 DLL cuDNN do 3.0.0a cài) | **Chờ quyết định riêng của chủ dự án.** Hiện giữ; chỉ ghi lại các file còn trong thư mục cài |
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
| B5 | Thời gian phân tích Chụp cá nhân trên cùng máy | So với bản 3.0.1 |

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
| D1 | Bảng 11 bước của bản RC (`docs/owner-acceptance-rc.md`) | Từng bước Đạt / Không đạt |
| D2 | GRP-1 (`docs/owner-trial-grp1.md`) | Số liệu `KiraPick.exe --grp1-counts` |
| D3 | Không có nhận mặt (SFace `pending`) | Gom người chỉ gán tay; thông báo đúng; không có điểm thẩm mỹ giả |

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

## G. Căn cứ phân phối (đối chiếu trước khi phát hành)

| # | Mục | Tài liệu |
|---|---|---|
| G1 | Trọng số trong bộ cài = đúng danh sách `verified`, SHA-256 ghim | `scripts/check_package.py` (báo cáo B); `docs/legal/danh-sach-file-ban-tiep-theo.md` |
| G2 | Giấy phép kèm theo trong `{app}\docs\licenses\` | `scripts/collect_licenses.py`; `THIRD_PARTY_NOTICES.md` |
| G3 | Bản CUDA không kèm cuDNN; có `docs\HUONG_DAN_CUDNN.txt` | LIC-7 (b) |
| G4 | CLIP, SFace, LAION, YoutuReID `pending`; ArcFace, TOPIQ `never` | `configs/model-policy.json`; `docs/model-licenses.md` |

## H. Còn chờ quyết định riêng

- **CLEAN-2**: giữ hay xoá 10 DLL cuDNN do 3.0.0a đã cài.
- Ghi chú phát hành, `LICENSE.md` (DOC-1): chưa sửa.
- Thời điểm build, danh sách người test: chủ dự án quyết định.
