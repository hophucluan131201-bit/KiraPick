# Media sự kiện — Kế hoạch triển khai Mốc 1 (bản 2, 2026-11-07)

**Trạng thái:**
- Chủ dự án **duyệt M1-OK và MED-EXP** (2026-11-07).
- Review: làm theo **hai đợt**. **Đợt 1 (M1–M5) đã xong**, kết quả ở mục 6. **Đợt 2 (M6–M11)** bắt đầu sau vòng review đợt 1.
- Đặc tả đã lên **bản 6** (`docs/design/media-su-kien.md` mục 0).

**Căn cứ:**
- Đặc tả Media v5 (`docs/design/media-su-kien.md`, đã duyệt 2026-11-06).
- Phần nền LIC-1 đã làm trên `beta` (HEAD `ee33b9a`).
- Chủ dự án chọn (2026-11-07):
  - **đưa Media Mốc 1 vào bản cập nhật tiếp theo**;
  - duyệt LIST-1, PKG-1, CLEAN-1;
  - LIC-7 = (b).

**Không đổi:**
- Không build, không phát hành, không merge `main`. CI chỉ chạy kiểm tra; job build / đóng gói giữ `skipped`.
- Các ca cần bộ cài thật (cài mới, nâng cấp, GRP-1, đo trên GPU) để ở đợt test bản đầy đủ cuối cùng, ghi **"chờ bản
  build cuối"**.

---

## 0. Những chỗ đặc tả v5 phải chỉnh theo LIC-1

| Mục v5 | v5 viết | Thực tế sau LIC-1 | Ảnh hưởng tới Mốc 1 |
|---|---|---|---|
| §1 | Dữ liệu cá nhân schema v7 không đổi | Dữ liệu cá nhân nay là **v8** (ghi nguồn kết quả) | Media vẫn dùng **cơ sở dữ liệu riêng**; không đụng dữ liệu cá nhân |
| §12 | `configs/media-models.json`, trạng thái "đã duyệt có rủi ro" | Thay bằng `configs/model-policy.json` dùng chung, chỉ có verified / pending / never | Media nạp YOLOX-S/M và YuNet (verified, chế độ media); **không** nạp CLIP, SFace |
| §13 MOD-1 | CLIP được dùng trong Media | **MED-CLIP:** CLIP `pending` (chấp nhận rủi ro không phải căn cứ quyền) | Mốc 1 chạy **phương án dự phòng §12a**: không gợi ý nội dung bằng AI, khoảnh khắc chia theo khoảng nghỉ, gợi ý tên booth theo giờ |
| §7, §12 | SFace để gom người ở Mốc 2 | SFace `pending` | Mốc 1 không dùng. Mốc 2 gom người chỉ thủ công, trừ khi có căn cứ (R1) |
| §1 | 1209 test Linux | 1307 test Linux (gồm 23 test Media) | Hồi quy Chụp cá nhân phải giữ nguyên các test hiện có |

Các chỉnh sửa này sẽ ghi vào đặc tả thành **bản 6** (chỉ phần kỹ thuật, không đổi quyết định của chủ dự án).

---

## 1. Phạm vi Mốc 1 (theo §14 của v5)

| Có trong Mốc 1 | Không có (để sau) |
|---|---|
| Dữ liệu Media riêng (mỗi sự kiện một thư mục, một cơ sở dữ liệu) | Gom người, tên, vai trò (Mốc 2) |
| Nhập **nhiều thư mục / nhiều máy**, nguồn máy, gán nguồn tay | Gợi ý nội dung bằng AI (cần CLIP: R2) |
| **Chỉnh giờ** theo nguồn máy, hoàn tác | "Gợi ý lại từ ảnh đã xác nhận" cho nội dung (tắt, CT-F3) |
| **Khoảnh khắc**: AI chia theo khoảng nghỉ; 📌 sửa tay (Tách tại đây, gộp, chuyển, đổi tên); ⚠ lệch giờ (MED-03); hoàn tác | Chọn ảnh tự động (UX-2 = chưa) |
| **Cỡ cảnh** Toàn / Trung / Cận / Chưa xác định (YOLOX + YuNet), gán tay **T / U / C** | Tự xếp cỡ cảnh cho ảnh vật thể |
| **Cảnh báo nét** Out nét / Trật nét (đo trên ảnh gốc; LED / đèn bị loại; rung = Out nét) | Cảnh báo "Nhòe chuyển động" riêng |
| **Nội dung ảnh** gán tay, nhiều nhãn, phím **1–5**, gán cho nhiều ảnh / cả khoảnh khắc; **tên booth** tự đặt, gợi ý theo khoảnh khắc | |
| **5 trạng thái nhãn** (đang phân tích / chưa xác định / AI gợi ý / đã xác nhận / đã bỏ) | |
| Lưới, ảnh lớn, **P / X / sao / ❤**, lọc theo 3 nhóm (cỡ cảnh, nội dung, lỗi nét) + nguồn + khoảnh khắc + trạng thái, Ctrl+Z | |
| **Chế độ "Dán nhãn mẫu"** và **lệnh chấm offline** (chỉ số liệu) | |
| `--self-test` có bước Media, báo cáo A | |

**Câu hỏi phạm vi (MED-EXP):** v5 để **xuất ảnh** ở Mốc 3. Nếu bản cập nhật tới chỉ có Mốc 1, người thử lọc được
nhưng **không xuất được** ảnh sự kiện. Đề xuất: đưa vào Mốc 1 một bản **xuất cơ bản**, dùng lại bộ xuất sao chép của Chụp
cá nhân (an toàn, không đè file). Ảnh P được chia thư mục theo khoảnh khắc, hoặc theo cỡ cảnh. Chờ chủ dự án.

---

## 2. Thiết kế

### 2.1 Dữ liệu

- **Nơi lưu:** `%LOCALAPPDATA%\KiraPick\media\<mã sự kiện>\`, gồm `event.db`, ảnh thu nhỏ, file ghi việc xuất.
- **Cấu trúc `event.db`:**
  - Dùng lại các bảng ảnh của phiên cá nhân (`assets`, `previews`, `decisions`, `occurrences`, `measurements`,
    `analysis_runs`…). Như vậy dùng lại được phần nhập ảnh, ảnh thu nhỏ, đánh dấu P/X, xuất, và ghi nguồn kết quả.
  - Thêm một chuỗi migration riêng **chỉ áp cho cơ sở dữ liệu Media** (`app/media/schema.py`), ghi phiên bản trong một
    bảng riêng. Cơ sở dữ liệu cá nhân không bao giờ nhận các bảng này.

| Bảng Media | Nội dung |
|---|---|
| `media_event` | tên sự kiện, ngày tạo |
| `camera_sources` | nguồn máy: thư mục con + hãng / dòng máy (không serial, UX-3), tên hiển thị |
| `asset_source` | ảnh → nguồn (tự động / gán tay) |
| `clock_offsets` | độ lệch giây theo nguồn; **lịch sử** từng lần chỉnh (để hoàn tác) |
| `moments` | khoảnh khắc: tên, `pinned` (📌), nguồn tạo (AI / tay) |
| `moment_assets` | danh sách ảnh của khoảnh khắc 📌 (giữ nguyên qua phân tích lại / chỉnh giờ) |
| `drift_warnings` | ⚠ lệch giờ: ảnh, khoảnh khắc gợi ý, lần chỉnh giờ tạo ra nó |
| `labels` | ảnh × nhóm (`shot`, `content`, `focus`) × giá trị, **trạng thái** (5 trạng thái), độ tự tin, `run_id` |
| `booth_names` | tên booth / nhà tài trợ tự đặt; gán ảnh |
| `sample_labels` | nhãn mẫu do người dán (chế độ Dán nhãn mẫu), **tách khỏi `labels`**, để chấm không bị lẫn |
| `media_journal` | nhật ký hoàn tác cho thao tác Media (chỉnh giờ, sửa khoảnh khắc, nhãn) |

**Quy tắc:**
- Không thao tác tự động nào ghi đè nhãn "Đã xác nhận" hoặc "Đã bỏ".
- Mọi thứ gắn theo **mã ảnh**.
- Giờ đã chỉnh luôn tính từ `capture_time` gốc cộng độ lệch; không sửa EXIF.

### 2.2 Phân tích sự kiện (một nút, UX-1)

- Chạy trong tiến trình con như Chụp cá nhân; tạm dừng / chạy tiếp; kết quả hiện dần; ảnh chưa xong có ⏳.
- **Mô hình:** chỉ qua `MediaRegistry`, gồm YOLOX-S (YOLOX-M khi GPU nhanh hơn) và YuNet. Mỗi lượt có `run_id` và danh
  sách mô hình thật đã mở.
- **Thứ tự:** (1) cỡ cảnh + cảnh báo nét theo từng ảnh; (2) khoảnh khắc khi đủ ảnh. Không có bước gom người ở Mốc 1.
- **Cỡ cảnh (§5):**
  - chọn chủ thể chính theo khung lớn nhất, sau khi loại người bị cắt quá nửa, người quay lưng, đầu khán giả ở tiền cảnh;
  - **có mặt:** theo tỉ lệ chiều cao mặt / chiều cao ảnh (Cận > 12 %, Trung 4–12 %, Toàn < 4 %);
  - **không mặt:** khung người < 25 % → Toàn, còn lại → Chưa xác định;
  - không người → Chưa xác định.
  - Ngưỡng ghi trong cấu hình, chỉnh trên tập chỉnh ngưỡng.
- **Cảnh báo nét (§6):**
  - đo trên ảnh gốc (dùng lại `app/quality/measure.py`), có tính ISO;
  - **Out nét:** vùng chủ thể mờ (không chủ thể thì xét cả ảnh); rung máy / nhòe chuyển động cũng là Out nét (UX-4);
  - **Trật nét:** chủ thể mờ + vùng gần chủ thể nét + vùng đó **không** phải màn LED / đèn. LED / đèn nhận ra theo độ
    sáng gần bão hoà và vùng phát sáng lớn; chỉ dùng để **loại** khỏi phép so;
  - chỉ là cảnh báo, không tự đánh X.
- **Khoảnh khắc (§8):**
  - AI chia theo **khoảng nghỉ** của giờ đã chỉnh, vì không có CLIP: dự phòng MT-F1. Ngưỡng khoảng nghỉ chỉnh trên ảnh mẫu;
  - khoảnh khắc 📌 giữ nguyên danh sách ảnh; AI chỉ chia lại ảnh ngoài 📌;
  - quy tắc ⚠ lệch giờ đúng như v5 (τ = 30 s, khoảng đối chiếu không gồm ảnh của nguồn vừa chỉnh);
  - "Không rõ giờ" cho ảnh thiếu giờ;
  - báo "đủ cỡ cảnh" theo khoảnh khắc trên ảnh đã P.

### 2.3 Giao diện Media

- **Cửa sổ Media riêng** thay cho trang chờ hiện nay, mở từ màn chọn chế độ, giữ "⇄ Đổi chế độ".
- **Dùng lại** thành phần đã có: lưới ảnh, ảnh lớn, so sánh, phím P/X/sao/❤, Ctrl+Z.
- **Mới:**
  - danh sách sự kiện (tạo / mở / xoá sự kiện; xoá thì xoá dữ liệu Media của sự kiện đó, **không** đụng ảnh);
  - **📂 Nhập ảnh** (nhiều thư mục);
  - **🕒 Máy ảnh & giờ** (hiện khi có từ 2 nguồn);
  - **🧠 Phân tích sự kiện**;
  - thanh lọc 3 nhóm (cỡ cảnh, nội dung, lỗi nét) + nguồn + khoảnh khắc + trạng thái;
  - dải khoảnh khắc (📌, ⚠, Tách tại đây, gộp, đổi tên);
  - phím **T / U / C** (cỡ cảnh), **1–5** (nội dung);
  - chế độ **Dán nhãn mẫu**.
- **Mã Media không import** luồng phân tích của Chụp cá nhân (test quét mã đã có, mở rộng cho thư mục mới).

### 2.4 Dán nhãn mẫu và chấm

- **Chế độ Dán nhãn mẫu:** người dán gắn cỡ cảnh, nội dung (nhiều nhãn), Nét / Out nét / Trật nét, ranh giới khoảnh
  khắc, "Chưa đánh giá"; lưu vào `sample_labels`.
- **Lệnh chấm offline:** `KiraPick.exe --media-score "<sự kiện>" [--out kq.json]`.
  - Chia tập chỉnh ngưỡng (≈ 40 %) / tập chấm (≈ 60 %) **theo khoảnh khắc**.
  - Báo theo §11: tỉ lệ kèm số mẫu; nhóm dưới 15 mẫu ghi "chưa đủ mẫu".
  - Mốc 1 chấm: cỡ cảnh, Out nét, Trật nét, khoảnh khắc (đúng / thừa / thiếu theo khoảng nghỉ).
  - Nội dung: "không áp dụng" (không có AI nội dung).
  - Đầu ra chỉ có số, không tên file.

---

## 3. Thứ tự commit và ca kiểm thử

Mỗi commit kèm test. CI Linux + Windows ở chế độ kiểm tra (`lic1-checks` / `perf` với `editions` rỗng).

| Commit | Nội dung | Ca kiểm thử |
|---|---|---|
| **M1** | Lưu trữ sự kiện: thư mục, `event.db`, migration Media riêng, tạo / mở / xoá sự kiện | Cơ sở dữ liệu cá nhân không có bảng Media; xoá sự kiện chỉ xoá dữ liệu Media, ảnh gốc không đổi (SHA-256) |
| **M2** | Nhập nhiều thư mục, nguồn máy tự động (thư mục con + hãng / dòng), gán tay, ghép RAW+JPEG | CAM-01, CAM-02, CAM-03, CAM-05 |
| **M3** | Chỉnh giờ (chọn hai ảnh cùng lúc / nhập giây), lịch sử, hoàn tác | CAM-04; giờ đã chỉnh = gốc + lệch; EXIF không đổi |
| **M4** | Khoảnh khắc: chia theo khoảng nghỉ, 📌, quy tắc ⚠, hoàn tác (logic thuần, không giao diện) | **MED-03 S0–S4, 03b, 03c, 03d** bằng ảnh tổng hợp; MT-F1; phân tích lại giữ 📌 |
| **M5** | Trạng thái nhãn + nhãn tay (cỡ cảnh, nội dung nhiều nhãn, tên booth), gợi ý tên booth theo khoảnh khắc | Không ghi đè "Đã xác nhận" / "Đã bỏ"; CT-F1, CT-F2, BT-F1 |
| **M6** | Phân tích sự kiện: cỡ cảnh (YOLOX + YuNet qua `MediaRegistry`), ghi nguồn | SZ-01a…05 bằng ảnh tổng hợp có khung người / mặt dựng sẵn (logic); bản ảnh thật = [Ảnh mẫu]; báo cáo A chỉ có YOLOX / YuNet |
| **M7** | Cảnh báo nét: Out nét / Trật nét, loại LED / đèn, rung = Out nét | FC-01…07 bằng ảnh tổng hợp (mờ Gauss, nhòe chuyển động, vùng LED sáng, **FC-06 màn LED sắc nét chưa bão hoà**, **FC-07 trang phục trắng sáng còn chi tiết**). Báo **riêng**: kết quả quy tắc trên ảnh tổng hợp (CI) và phần cần kiểm trên ảnh thật |
| **M8** | Cửa sổ Media: danh sách sự kiện, lưới, lọc **3 nhóm Mốc 1** (cỡ cảnh, nội dung, lỗi nét) + nguồn + khoảnh khắc + trạng thái, P/X / sao / ❤, phím T / U / C / 1–5, dải khoảnh khắc, 🕒, 🧠; nhãn AI kèm "(thử nghiệm)" | GUI offscreen: nhập → phân tích → lọc → sửa → hoàn tác; đổi chế độ giữ dữ liệu cả hai bên |
| **M9** | Dán nhãn mẫu + `--media-score` | Chấm trên bộ nhãn tổng hợp cho số đúng; chia tập theo khoảnh khắc; dưới 15 mẫu → "chưa đủ mẫu"; đầu ra không có tên file |
| **M10** | `--self-test` bước Media; mở rộng test chặn mạng, đổi chế độ, quét mã import | Báo cáo A Media trên ảnh tổng hợp; chặn mạng (socket + tường lửa trên CI Windows) |
| **M11** (MED-EXP **đã duyệt**) | Xuất ảnh P theo khoảnh khắc / cỡ cảnh, dùng bộ xuất sao chép hiện có | Không đè file; ảnh gốc không đổi (SHA-256); ảnh ⏳ vẫn xuất được theo P/X; **ảnh đã P nhưng chưa có khoảnh khắc** (chưa phân tích) xuất vào thư mục "Chưa chia khoảnh khắc"; **hai máy có file trùng tên** ra hai file khác tên, không đè nhau |

**Hồi quy:**
- Sau mỗi commit: bộ test Chụp cá nhân giữ nguyên (1284 Linux).
- Cuối Mốc 1: chạy job Windows `perf` (kiểm tra, không build).

---

## 4. Kiểm chứng: làm được trong CI và cần ảnh thật

| Loại | Làm ở Mốc 1 | Ghi chú |
|---|---|---|
| Logic (MED-03, MT-F1, CT-F*, BT-F1, CAM-*, trạng thái nhãn) | **CI**, ảnh tổng hợp | Đủ để nghiệm thu kỹ thuật |
| Cỡ cảnh, nét trên ảnh tổng hợp | **CI** | Chỉ kiểm quy tắc, không kiểm độ chính xác thật |
| Ngưỡng và tỉ lệ đạt (§11) | **Cần 100–150 ảnh sự kiện thật có nhãn** | Chủ dự án dán nhãn bằng chế độ Dán nhãn mẫu trên bản build cuối. Trước đó nhãn AI hiện "(thử nghiệm)" |
| MED-02, SZ / FC trên ảnh thật | [Ảnh mẫu] | Cùng đợt trên |
| Thời gian 1.000 / 5.000 ảnh, GPU | **Chờ bản build cuối** | Máy chủ dự án |
| Bản CUDA cài mới và nâng cấp từ 3.0.0a | **Chờ bản build cuối** | Ghi: provider thực tế của từng mô hình (báo cáo A), **đường dẫn `cudnn64_9.dll` được nạp** (`--self-test` → `cuda.cudnn_dll`), lý do chạy CPU nếu có (`cuda.setup_error`, thanh trạng thái). Hai ca: máy chưa cài cuDNN (phải chạy CPU, ghi lý do) và máy đã cài cuDNN 9. Nâng cấp từ 3.0.0a: theo CLEAN-2 (chờ chủ dự án) |

### 4a. Ảnh mẫu (MED-SAMPLE)

- **Nguồn:**
  - **Chính:** album **VNNIC Internet Conference 2026**, ngày 19/6.
  - **Bổ sung:** album **tổng kết IPv6, trao bằng khen**, ngày 18/6.
  - **Đường dẫn album: chờ chủ dự án gửi.** Hai album là album công khai trên mạng.
- **Trước khi lập tập mẫu**, kiểm và ghi lại:
  - số ảnh truy cập được;
  - độ phân giải;
  - EXIF giờ chụp: có / không, và có giữ hãng / dòng máy không.
- **Dùng ảnh album để thử:**
  - cỡ cảnh;
  - nhãn nội dung;
  - luồng lọc – chọn – xuất.
- **Lỗi nét và chỉnh giờ nhiều máy:** ưu tiên **ảnh gốc** có metadata đầy đủ (ảnh album thường bị nén lại, cắt EXIF, giảm
  độ phân giải). Nếu album thiếu EXIF / độ phân giải thì ghi rõ "không dùng được cho lỗi nét / chỉnh giờ", và đề nghị
  chủ dự án cung cấp ảnh gốc của cùng sự kiện, chạy trên máy chủ dự án.
- **Báo cáo đủ mẫu:** ghi nhóm nhãn nào đủ ≥ 15 mẫu (cỡ cảnh từng giá trị, từng nhãn nội dung, Out nét, Trật nét),
  nhóm nào cần bổ sung.
- **Nguồn từng ảnh:** ghi **URL nguồn** cho từng ảnh trong danh sách mẫu (file danh sách chỉ có URL, mã ảnh, nhãn).
- **Quyền sử dụng:**
  - Kiểm điều khoản của nơi đăng album và quyền của ảnh **trước khi** đưa bất kỳ ảnh nào vào repo, CI hoặc gói test
    chia sẻ.
  - Mặc định ảnh **không vào repo, không vào CI**. Chủ dự án dán nhãn trên máy mình bằng bản build cuối; repo chỉ giữ
    danh sách URL và nhãn (không có ảnh), nếu điều khoản cho phép.
- **Trên `beta`:** tiếp tục kiểm bằng mã nguồn và ảnh tổng hợp trong CI.

---

## 5. Quyết định cần chủ dự án

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| **M1-OK** | Duyệt kế hoạch Mốc 1 (mục 1–3) | **Đã duyệt** 2026-11-07 |
| **MED-EXP** | Đưa xuất ảnh cơ bản vào Mốc 1 | **Đã duyệt** 2026-11-07 (M11) |
| **MED-SAMPLE** | Hai album VNNIC (19/6, chính; 18/6, bổ sung), mục 4a | **Đã chọn**; chờ đường dẫn album |
| **CLEAN-2** | Giữ hay xoá 10 DLL cuDNN do bản 3.0.0a đã cài khi nâng cấp | **Chờ chủ dự án** (hiện giữ) |
| Đặc tả v6 | Ghi các chỉnh sửa kỹ thuật ở mục 0 vào đặc tả | **Đã làm** |
| **Đợt 2** | Bắt đầu M6–M11 sau vòng review đợt 1 | Chờ review |
| **R1-UNDO-AI** | Hoàn tác một thao tác khoảnh khắc làm trước lần "Phân tích lại" thì trả cả bảng khoảnh khắc về ảnh chụp trước thao tác đó, nên phần AI chia lại cũng bị trả về (khoảnh khắc 📌 và P/X không bị ảnh hưởng). Giữ cách này, hay chỉ trả các khoảnh khắc 📌 liên quan? | Đề xuất: **giữ**, vì đơn giản và dễ đoán; chạy "Phân tích lại" sẽ chia lại phần AI. Chờ review |

---

## 6. Kết quả đợt 1 (M1–M5)

| Commit | Nội dung | Ca kiểm thử | Kết quả |
|---|---|---|---|
| `d0f73f7` M1 | Kho dữ liệu riêng cho từng sự kiện | **Cùng thư mục ảnh mở ở hai chế độ, P/X khác nhau → tách riêng**; phiên cá nhân không có bảng Media; nhập / mở / xoá không đổi ảnh gốc (SHA-256); mã sự kiện lạ, thư mục không phải sự kiện bị từ chối | Đạt |
| `4fcb613` M2 | Nhiều thư mục, nguồn máy, gán tay | CAM-01, CAM-02 (gán tay giữ qua nhập lại), CAM-03 (trùng tên ở hai thư mục, ảnh gốc không đổi), CAM-05, đổi tên / gộp nguồn | Đạt |
| `1f2daff` M3 | Chỉnh giờ theo nguồn, hoàn tác | Lệch từ cặp ảnh + hoàn tác (ảnh, EXIF, `capture_time`, P/X không đổi); hai lần chỉnh hoàn tác từng bước; ảnh không có giờ; lịch sử giữ 50 bước, còn sau khi mở lại | Đạt |
| `f26d0c2` M4 | Khoảnh khắc, 📌, ⚠ lệch giờ | **MED-03 S0–S4** đúng bảng đặc tả; 03b (vùng chồng), 03c (không có khoảng đối chiếu), 03d (A-6 không bị kéo theo); Giữ + hoàn tác; MT-F1; **khoảnh khắc 📌 giữ nguyên qua phân tích lại**; gộp / chuyển / đổi tên hoàn tác được | Đạt |
| `e52a67b` M5 | Trạng thái nhãn, nhãn tay, tên booth | **AI không ghi đè nhãn đã xác nhận / đã bỏ**; CT-F1 / F2 / F3; BT-F1; **CAM-04** (chỉnh giờ giữ P/X, sao, nhãn, booth, khoảnh khắc 📌); "đủ cỡ cảnh" theo khoảnh khắc | Đạt |

**Tổng:** 1307 test Linux đạt (23 test Media mới). CI Windows ở chế độ kiểm tra: run `lic1-checks` và `perf` (kết quả ở
gói review). Job build / đóng gói: `skipped`.
