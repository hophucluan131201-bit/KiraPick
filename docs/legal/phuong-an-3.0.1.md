# Kế hoạch sửa phần nền trên `beta` và tiêu chí nghiệm thu (bản trình 4, 2026-11-06)

**Trạng thái:** kế hoạch, trình duyệt **LIC-1** (phạm vi sửa phần nền).
- **Chưa sửa mã ứng dụng, chưa build bộ cài, chưa đổi mặc định, chưa đụng tới release nào.**
- **Phát hành xét riêng.** Merge vào `main`, tạo tag, phát hành, thay hoặc gỡ asset đều cần chủ dự án duyệt riêng.
- Xác nhận của chủ dự án chỉ duyệt việc triển khai. **Quyền sử dụng** dựa trên điều khoản hoặc bên cấp quyền.

**Thay đổi so với bản trình 3:**
- Đối chiếu HEAD với mốc (mục 0).
- **Bảng phạm vi LIC-1** chia ba nhóm: có thể triển khai / chờ căn cứ / chờ quyết định sản phẩm, mỗi việc kèm ca nghiệm thu
  (mục 3).
- MED-CLIP ghi rõ thay đổi trạng thái CLIP (mục 4).
- BM-0 tách thành F-SF (kèm căn cứ chạy nội bộ) và Q-TECH (trình riêng theo đúng thành phần) (mục 7).
- **Tách nghiệm thu kỹ thuật khỏi quyết định phát hành.** Ghi chức năng thiếu khi không có gom nhóm tự động, ở từng chế độ
  (mục 5, 6).
- CI-1 thành mục sửa riêng (mục 8).

---

## 0. Mốc nền và đối chiếu HEAD

| Mục | Giá trị |
|---|---|
| Mốc kế hoạch | `38054b939b8c514e7bbcbed50f8f788263caf233` |
| HEAD `beta` lúc soạn bản này | `9f6082bd9f7d297841cf42dc9af358a49ce8689f` |
| Khác biệt `38054b9..9f6082b` | 2 commit, **chỉ** `docs/legal/phuong-an-3.0.1.md`. **Mã giống hệt mốc** |
| Thay đổi mã đã có so với `v3.0.0` (`e2fec9d`) | Màn chọn chế độ (`e05f464` … `ec744f0`); Media Mốc 0 (`703ad8d`); job CI `inspect-release` (`a36bba9` … `3956697`) |
| Luồng Chụp cá nhân | Giống 3.0.0: vẫn tự nạp ArcFace + YoutuReID, TOPIQ ×3, CLIP + LAION khi có file |
| Số phiên bản | **Chờ chốt** (VER-1) |

**Quy trình trước khi sửa:** khi bắt đầu, chạy lại `git diff --stat 38054b9 HEAD -- app configs packaging scripts`. Nếu có
thay đổi mã ngoài kế hoạch thì dừng lại và báo.

---

## 1. Căn cứ theo từng file (tóm tắt; chi tiết ở Phụ lục B)

| File | Dùng cho job có thu tiền | Phân phối |
|---|---|---|
| YOLOX-S, YOLOX-M, YuNet, eDifFIQA | đủ | đủ |
| MediaPipe mesh + blendshapes | đủ, **kèm điều kiện** chuyển đổi tái lập (S9) | như cột trước |
| LAION | đủ (riêng file), nhưng cần CLIP | đủ |
| **SFace**, **CLIP** + `clip_prompts`, **YoutuReID**, **AuraFace** | **chờ** | **chờ** |
| ArcFace, TOPIQ ×3 | không | không |
| DLL cuDNN 9 (gói CUDA) | — | **chờ** |
| Các thư viện khác | — | đủ, kèm nghĩa vụ thông báo |

---

## 2. Thành phần theo chế độ

| Thành phần | Chụp cá nhân | Media sự kiện |
|---|---|---|
| YOLOX-S / -M, YuNet | giữ | giữ (`pending` → `verified`) |
| eDifFIQA | giữ | không dùng |
| MediaPipe ×2 | giữ nếu S9 đạt, nếu không thì tắt | không dùng |
| SFace | **tắt** gom nhóm tự động | **tắt**: chỉ gom người thủ công |
| CLIP, `clip_prompts`, LAION | **tắt** | **tắt** (mục 4) |
| ArcFace, YoutuReID, TOPIQ ×3 | **gỡ** | không bao giờ |

---

## 3. Bảng phạm vi LIC-1

### 3.1 Có thể triển khai ngay khi LIC-1 được duyệt

Các việc này **không phụ thuộc** quyền của file nào còn "chờ". Với file "chờ", mặc định là **tắt**. Sau này có căn cứ thì chỉ
cần đổi trạng thái trong danh sách, không sửa lại mã.

| # | Việc | Chế độ | Ca nghiệm thu |
|---|---|---|---|
| **S1** | **Lớp chặn dùng chung.**<br>• Một danh sách cho phép theo SHA-256 (`configs/model-policy.json`), thay `media-models.json`.<br>• Trạng thái mỗi file: `verified` / `pending` / `never`. Chỉ `verified` được mở.<br>• Mọi chỗ mở mô hình đi qua một cửa kiểm. `MediaRegistry` đang có dùng lại cửa này | cả hai | U1, U2, U3 |
| **S2** | **Gỡ đường nạp** ArcFace + YoutuReID (`embed_job.py:53`), TOPIQ ×3 (`quality_job.py:195`, `load_extras`); CLIP / LAION / `clip_prompts` đi qua S1 (gồm `main_window.py:1052`). Các file này được ghi là `never` / `pending` trong danh sách | Cá nhân | U1, U4 |
| **S3** | **Tách "dò" khỏi "nhận mặt"**:<br>• phân tích chạy được chỉ với YOLOX + YuNet (+ eDifFIQA, MediaPipe);<br>• khi không có mô hình nhận mặt: không gom nhóm tự động, giao diện ghi "Gom người tự động chưa có trong bản này";<br>• gom thủ công vẫn dùng được: "Đây là người khác" (`actions.create_subject`) và đưa ảnh vào một người (`assign_photos_to_subject`), dựa trên khung người đã dò | Cá nhân | U9 |
| **S4** | **Dự phòng:** GPU → CPU, YOLOX-M → S, thiếu file, `--self-test`. Mọi nhánh đi qua S1 | cả hai | U1 (mọi đường) |
| **S5** | **Cache cũ:**<br>• không đọc vector `face_arc`, `body`, `clip`;<br>• không đọc điểm `aesthetic_mos`, `tech_iqa`, `face_iqa`;<br>• `session_profile` (`cluster.py:153`) không chọn hồ sơ ArcFace;<br>• `learning.db` không đọc / ghi các cột đó.<br>**Không xoá** dữ liệu | Cá nhân | U4, U5 |
| **S6** | **Bảo toàn chỉnh sửa của người dùng:**<br>• P/X, sao, ❤, lịch sử xuất;<br>• nhóm có gán tay (`occurrences.assignment = 'manual'`), tên đã khoá (`subjects.user_locked`), cặp "khác nhau" (`subject_pairs`).<br>Mở / phân tích lại bằng bản mới không thay đổi các dòng này. Nhóm **tự động** cũ: mặc định **giữ nguyên trong DB**, cách hiển thị theo DATA-1 | Cá nhân | U4, U8, P8 |
| **S7** | **Báo cáo A** cho cả hai chế độ: mỗi file đã mở (id, SHA-256, provider) và mỗi file **bị bỏ qua** kèm lý do. Ghi ở `--self-test` và trong log phân tích | cả hai | P5, P6, P7 |
| **S8** | **Kiểm kê bộ cài:**<br>• script build chỉ tải file `verified`;<br>• `kirapick.spec` bỏ FFmpeg, TensorRT provider, DLL NVIDIA trùng;<br>• `[InstallDelete]` file mô hình không còn trong danh sách;<br>• `inspect-release` chạy trên artifact build, lỗi nếu lệch danh sách / còn DLL bị bỏ / thiếu toàn văn | mọi gói | P1–P4, P8 |
| **S9** | **Chuyển đổi MediaPipe tái lập:** chạy lại `scripts/convert_mediapipe.py` từ `.task` `64184e22…c9ff`, so SHA-256 với file trong repo. Không trùng thì MediaPipe chuyển `pending` | Cá nhân | U10 |
| **S10** | **Giấy tờ:** `docs\licenses\` có đủ toàn văn và thông báo theo Phụ lục B.3; viết lại `THIRD_PARTY_NOTICES`, `model-licenses.md` | mọi gói | P4 |
| **S11** | **Chạy khi mạng bị chặn:** chặn socket trong tiến trình (Linux + Windows), và chặn bằng tường lửa hệ điều hành trên CI Windows | cả hai | U7 |
| **S12** | Đổi chế độ Cá nhân ↔ Media nhiều lần trong một lần chạy: không mở file ngoài danh sách | cả hai | U6 |

### 3.2 Chờ căn cứ (mã của S1 đã sẵn; chỉ đổi trạng thái khi có căn cứ)

| # | Thành phần | Thiếu gì | Chức năng bị tắt tới khi có | Ca nghiệm thu khi được bật |
|---|---|---|---|---|
| R1 | **SFace** (hoặc mô hình nhận mặt thay thế: AuraFace, dlib) | Xác nhận của tác giả (SFace) / nguồn gốc `glintr100` (AuraFace) / kiểm file (dlib) — LIC-3 | Gom nhóm tự động ở cả hai chế độ; học nhận diện trong `learning.db` | U1 với file mới; F-* đạt; P1 |
| R2 | **CLIP** + `clip_prompts` (+ LAION đi kèm) | Xác nhận của OpenAI (model card: triển khai "ngoài phạm vi") | Cá nhân: điểm thẩm mỹ CLIP, "Hợp gu". Media: nhãn nội dung, tách khoảnh khắc theo cảnh, gợi ý booth, ảnh gần trùng | U1; Q-CL đạt |
| R3 | **cuDNN 9** | Văn bản NVIDIA cho phép phân phối các DLL bản 9 | Gói CUDA (LIC-7) | P1–P4 cho gói CUDA |
| R4 | **YoutuReID** | Công bố của Tencent | Gom người quay lưng / che mặt | — (không đề xuất) |
| R5 | **MediaPipe** (chỉ khi S9 không đạt) | File chuyển đổi tái lập được | Kiểm mắt nhắm / mở | U10 |

### 3.3 Chờ quyết định sản phẩm

| # | Câu hỏi | Ảnh hưởng tới mã | Đề xuất |
|---|---|---|---|
| D1 **DATA-1** | Nhóm **tự động** cũ (gom bằng ArcFace, `assignment != 'manual'`, chưa khoá tên) trong phiên 3.0.0: ẩn hay hiện? | S6: chỉ khác phần hiển thị; dữ liệu giữ nguyên | Ẩn nhóm tự động; hiện nhóm có gán tay / tên khoá |
| D2 **GRP-1** | Chấp nhận bản **chỉ gom thủ công** (mục 6)? | Không đổi S1–S12; đổi chữ trên giao diện | Trình chủ dự án |
| D3 **CFG-1** | Gói nào: có AI (DirectML, portable, CUDA theo LIC-7), có cần gói tối thiểu không AI? | S8 | Trình cùng quyết định phát hành |
| D4 **VER-1** | Số phiên bản | build | Chờ chốt |
| D5 **MED-CLIP** | Xác nhận đổi trạng thái CLIP (mục 4) | S1, S2 | Đồng ý |

---

## 4. MED-CLIP: thay đổi trạng thái CLIP

| | Trước (đang trên `beta`) | Sau |
|---|---|---|
| `configs/media-models.json` → `model-policy.json`, `clip_l14_image`, `clip_prompts` | `approved_with_risk`: Media **được nạp** | **`pending`**: không nạp ở cả hai chế độ |
| Chụp cá nhân | nạp CLIP + LAION khi có file | không nạp |
| Cấu hình dùng cho **job có thu tiền** | — | Đây là cấu hình duy nhất được đóng gói. CLIP **không có trong danh sách cho phép** và **không có trong bộ cài** |
| Quyết định MOD-1 (2026-11-06, chủ dự án chấp nhận rủi ro CLIP cho Media) | căn cứ cho `approved_with_risk` | Giữ làm **hồ sơ** về ý kiến của chủ dự án. **Không** dùng làm căn cứ quyền. Mở lại khi có R2 |
| Dự phòng Media (đặc tả v5) | — | nhãn nội dung thủ công; tách khoảnh khắc theo khoảng thời gian; không gợi ý booth; không tìm ảnh gần trùng bằng CLIP |
| Ca nghiệm thu | — | U1 (CLIP có trong thư mục nhưng không mở), P1 (CLIP không có trong bộ cài), P7 (Media báo cáo A không có CLIP) |

---

## 5. Nghiệm thu kỹ thuật

Đạt / không đạt theo các ca dưới đây. **Không** kèm quyết định phát hành (mục 6).

**Ai chạy:**
- **CI:** Windows Server 2022, không GPU. Ảnh tổng hợp / ảnh mẫu công khai, **không** dùng ảnh của chủ dự án.
- **Chủ dự án:** máy của chủ dự án. Kết quả ghi riêng; chưa chạy thì ghi "chưa chạy".

### 5.1 Test tự động (Linux + Windows CI)

| # | Ca | Việc |
|---|---|---|
| U1 | Bọc mọi hàm mở mô hình (`InferenceSession`, `cv2.dnn.readNet*`, `FaceRecognizerSF.create`, `FaceDetectorYN.create`). Thư mục `models\` có **đủ 15 file của 3.0.0**. Chỉ file `verified` được mở, ở mọi đường:<br>• chạy thường;<br>• GPU → CPU;<br>• YOLOX-M → S;<br>• thiếu từng file;<br>• `--self-test`;<br>• mở phiên cũ, phân tích lại, tính lại điểm;<br>• Media Mốc 0 | S1, S2, S4 |
| U2 | `w600k_r50.onnx` đổi tên thành tên file được phép → bị từ chối (sai SHA-256), báo "chưa có" | S1 |
| U3 | `KIRAPICK_MODELS_DIR` trỏ sang thư mục có file lạ → bị chặn | S1 |
| U4 | Phiên kiểu 3.0.0 (schema v7) có `face_arc` / `body` / `clip`, điểm TOPIQ, P/X, sao, ❤, nhóm tự động, nhóm gán tay, tên khoá, cặp "khác nhau", lịch sử xuất. Mở và phân tích lại:<br>• không đọc vector và điểm cũ;<br>• mọi dòng của người dùng **giống từng byte** trước và sau;<br>• dòng tự động cũ **còn trong DB**;<br>• hiển thị theo DATA-1 | S2, S5, S6 |
| U5 | `learning.db` cũ có cột `face_arc` / `body`: không đọc / ghi, không xoá | S5 |
| U6 | Đổi chế độ nhiều lần: không mở file ngoài danh sách | S12 |
| U7 | Phân tích khi mạng bị chặn (socket + tường lửa trên CI Windows) | S11 |
| U8 | SHA-256 ảnh gốc trước và sau mọi ca bằng nhau | S6 |
| U9 | Không có mô hình nhận mặt:<br>• phân tích vẫn ra khung người / mặt, điểm kỹ thuật, mắt;<br>• "Đây là người khác" và đưa ảnh vào người hoạt động;<br>• gom tự động không chạy và giao diện nói rõ | S3 |
| U10 | Chuyển đổi MediaPipe tái lập, SHA-256 trùng | S9 |

### 5.2 Kiểm bộ cài thực tế

| # | Kiểm | DirectML | CUDA | portable | Ai | Đạt khi |
|---|---|---|---|---|---|---|
| P1 | File mô hình | ✔ | ✔ | ✔ | CI | Đúng danh sách `verified` (tên + SHA-256) |
| P2 | Không file trọng số nào khác | ✔ | ✔ | ✔ | CI | Không `.onnx` / `.pth` / `.pt` / `.npz` / `.task` ngoài P1 |
| P3 | DLL | ✔ | ✔ | ✔ | CI | Không FFmpeg; CUDA: không TensorRT, không bản trùng, cuDNN theo LIC-7 |
| P4 | Giấy tờ | ✔ | ✔ | ✔ | CI | Đủ S10 theo gói |
| P5 | `--self-test`, hai chế độ | ✔ CPU | ✔ CPU | ✔ CPU | CI | Báo cáo A chỉ có file `verified` |
| P6 | Phân tích thư mục mẫu, Chụp cá nhân | ✔ CPU | ✔ CPU | ✔ CPU | CI | Log chỉ có file `verified`; U9 trên bộ cài thật |
| P7 | Mở Media | ✔ | ✔ | ✔ | CI | Báo cáo A Media không có file nào ngoài `verified` (Mốc 0: không file nào) |
| P8 | Nâng cấp từ v3.0.0 / v3.0.0a thật, có phiên, `learning.db` và 15 file cũ | ✔ | ✔ | giải nén đè | CI | File bị loại không còn; chép lại → "bỏ qua"; U4–U5 trên bộ cài thật; ảnh gốc không đổi |
| P9 | P6, P7 trên GPU thật | ✔ DirectML | ✔ CUDA | ✔ | **Chủ dự án** | Provider đúng; chỉ file `verified`; thời gian mỗi ảnh |
| P10 | Nâng cấp trên phiên ảnh thật | ✔ | ✔ | — | **Chủ dự án** | P/X, nhóm chỉnh tay, ảnh gốc giữ nguyên |
| P11 | Tắt mạng | ✔ | ✔ | ✔ | CI (U7) + chủ dự án (rút mạng) | Như P6 |
| P12 | Trình cập nhật | ✔ | ✔ | — | CI (danh sách release giả) | 3.0.0 → bản mới; tag beta không bị mời |

**Kết quả nộp:**
- Báo cáo CI gồm U1–U10, P1–P8, P11 (phần CI), P12. Kèm danh sách file từng gói, báo cáo A, log nạp mô hình.
- Ca của chủ dự án ghi riêng.

---

## 6. Quyết định phát hành (tách khỏi nghiệm thu kỹ thuật)

Bản đạt mục 5 **chưa** có nghĩa là được phát hành. Chủ dự án quyết các điểm sau, sau khi xem kết quả mục 5:

### 6.1 Chức năng thiếu khi chưa có gom nhóm tự động (GRP-1)

| Chế độ | Có | **Thiếu** so với 3.0.0 | Cách người dùng làm thay |
|---|---|---|---|
| **Chụp cá nhân** | Dò người, dò mặt; chấm kỹ thuật (nét ở mắt, sáng, bố cục, chất lượng mặt); mắt nhắm / mở (nếu S9 đạt); chọn ảnh theo điểm kỹ thuật; P/X, xuất | • **Gom ảnh theo người / bộ trang phục tự động** (3.0.0: ArcFace + dáng người).<br>• **Gợi ý gộp nhóm**, hàng "cần xem lại".<br>• **Học nhận diện** theo người dùng.<br>• **Chọn N ảnh đẹp nhất cho từng người**: chỉ còn chọn theo ảnh.<br>• **Điểm thẩm mỹ** (TOPIQ, CLIP) và "Hợp gu" | Chọn ảnh rồi "Đây là người khác" hoặc đưa vào một người có sẵn; lọc theo người sau khi đã gom tay |
| **Media sự kiện** | Màn hình Media (Mốc 0). Mốc 1 (cỡ cảnh, dò người / mặt) chưa làm | • **Gom người tự động** (Mốc 2: đặc tả dự phòng là "chỉ gom thủ công").<br>• **Nhãn nội dung, gợi ý booth, tách khoảnh khắc theo cảnh** bằng CLIP | Nhãn và người gán thủ công; khoảnh khắc tách theo khoảng thời gian |

**Câu hỏi cho chủ dự án:**
- Có chấp nhận phát hành bản chỉ gom thủ công không?
- Hay giữ bản này ở dạng build thử nội bộ, chờ R1?

### 6.2 Các quyết định phát hành khác

| Mã | Câu hỏi |
|---|---|
| VER-1 | Số phiên bản |
| CFG-1 | Gói phát hành (có AI / tối thiểu) |
| LIC-7 | Gói CUDA khi cuDNN 9 chưa rõ: (a) chưa đăng; (b) không kèm cuDNN; (c) chờ NVIDIA |
| REL | Lệnh phát hành, merge `main`, tag |
| Asset cũ | Hồ sơ riêng, mục 9 |

---

## 7. BM-0: F-SF và Q-TECH

### 7.1 F-SF (gom nhóm bằng SFace, đo nội bộ)

| Mục | Nội dung |
|---|---|
| Mục đích | Biết SFace (hoặc mô hình thay thế sau này) gom tốt tới đâu, để quyết định có đáng xin xác nhận (LIC-3) không. **Không** dẫn tới việc đưa SFace vào bộ cài |
| Thành phần | YOLOX-S / -M (đủ), YuNet (đủ), **SFace (chờ)**, màu trang phục (mã của app) |
| **Căn cứ chạy nội bộ** | • Chỉ chạy trên máy chủ dự án, không phân phối file, không đưa kết quả cho khách, không dùng cho job.<br>• Căn cứ duy nhất cho SFace là câu Apache-2.0 của **bên phân phối lại** (opencv_zoo, thư mục SFace). Repo của tác giả không có giấy phép.<br>• Như vậy căn cứ **chưa đầy đủ** ngay cả với việc đo nội bộ. Chủ dự án quyết chạy với căn cứ này, hoặc chờ trả lời LIC-3 |
| Dữ liệu | D1: 431 ảnh có nhãn của một buổi chụp của chủ dự án. Ảnh không rời máy |
| Chờ | Quyết định BM-0a |

### 7.2 Q-TECH (chấm kỹ thuật, trình riêng)

| Mục | Nội dung |
|---|---|
| Mục đích | So thứ hạng theo điểm kỹ thuật (không có TOPIQ, CLIP) với lịch sử P/X của chủ dự án |
| Nạp mô hình | **Không**: chỉ đọc số đo đã lưu |
| Thành phần (nguồn của số đo đã lưu) | • Nét ở mắt, sáng, bố cục: mã của app, dùng vị trí mặt / mắt từ **YuNet** (đủ) và khung người từ **YOLOX** (đủ).<br>• Chất lượng mặt: **eDifFIQA** (đủ).<br>• Mắt nhắm / mở: **MediaPipe** (đủ, kèm S9) |
| Không đọc | `aesthetic_mos`, `tech_iqa`, `face_iqa` (TOPIQ); vector `clip`; điểm "Hợp gu" |
| **Không dựa vào nhóm người cũ** | Nhóm người trong phiên cũ do ArcFace gom. Q-TECH so **theo ảnh và theo loạt chụp liên tiếp (theo thời gian)**, không theo nhóm người |
| Kiểm tra nguồn số đo | DB của phiên **không** ghi mã băm file mô hình. Bảng `measurements` chỉ có `extractor` + `extractor_version`; bảng `model_registry` có trong schema nhưng app không ghi. Bằng chứng thay thế [Bộ cài], trên mọi bản từ v0.2.0b1 tới v3.0.0a:<br>• YuNet, YOLOX-S, eDifFIQA: **cùng một** SHA-256 ở mọi bản;<br>• YOLOX-M: bản cũ là file gốc `21ff6cfd…b3f`, bản mới là float16 `be329495…6aaf` của chính file đó;<br>• MediaPipe: có từ v0.2.0b4, cùng SHA-256 ở mọi bản.<br> Q-TECH chỉ dùng số đo có `extractor` thuộc các bộ đo đó |
| Biến thể | Q-TECH-noMP: bỏ giá trị mắt (dùng nếu S9 không đạt) |
| Chỉ số | Tỉ lệ ảnh đầu loạt trùng **P**; tương quan thứ hạng; ca sai đáng chú ý |
| Chờ | Quyết định BM-0b |

---

## 8. CI-1 (mục sửa riêng)

| Mục | Nội dung |
|---|---|
| Vấn đề | Run 42245312724: ô `editions` để trống khi kiểm release → job `plan` hiểu là `directml,cuda,openvino` → 3 job build chạy, đã huỷ, không có artifact build, không có release |
| Sửa | Trong job `plan`: khi `inspect_release` có giá trị, coi `editions` trống là `none`. Khi cả hai cùng có giá trị thì báo lỗi rõ ràng, không build |
| Nghiệm thu | Chạy `workflow_dispatch` với `inspect_release=["v0.2.0b1"]` và `editions` **trống**:<br>• cả 3 job `build (…)` có `conclusion = skipped`;<br>• có job `inspect-release (v0.2.0b1)`;<br>• run không có artifact nào ngoài `inventory-*`.<br>Bằng chứng: kết quả `gh run view --json jobs` dán vào báo cáo |
| Phụ thuộc | Không phụ thuộc LIC-1; làm được ngay khi duyệt |

---

## 9. Hồ sơ riêng: asset đã phát hành (chủ dự án quyết riêng)

Không thay đổi so với bản trình 3:
- 19 release đều đã kiểm.
- 15 tag / 43 asset chứa ArcFace / YoutuReID / TOPIQ / CLIP; 4 tag / 12 asset chỉ có SFace.
- Hai mốc D (dừng cung cấp) và U (mở đường cập nhật).

Danh sách đầy đủ ở Phụ lục A. Chưa thao tác gì.

| Mốc | Việc | Phụ thuộc |
|---|---|---|
| D | Xoá asset bị ảnh hưởng; giữ trang release, tag, ghi chú | Không phụ thuộc bản mới |
| U | Đăng bản mới | Nghiệm thu mục 5 + quyết định mục 6 + lệnh phát hành |

| Thứ tự | Trong khoảng giữa |
|---|---|
| D trước, U sau | Không có bộ cài để tải; trình cập nhật báo "không có bản mới"; máy đã cài vẫn chạy và vẫn còn file cũ |
| U trước, D ngay sau | Bộ cài cũ vẫn tải được tới khi bản mới xong |

Mình không có quyền sửa release (GitHub trả 403).

---

## 10. Quyết định cần duyệt ở lượt này

| Mã | Nội dung | Đề xuất |
|---|---|---|
| **LIC-1** | Duyệt **S1–S12** (mục 3.1) | Đồng ý |
| **CI-1** | Sửa job `plan` (mục 8) | Đồng ý |
| **MED-CLIP** | CLIP → `pending` ở cả hai chế độ (mục 4) | Đồng ý |
| **DATA-1** | Hiển thị nhóm tự động cũ | Ẩn; giữ nhóm gán tay / tên khoá |
| **BM-0a** | Chạy F-SF nội bộ với căn cứ chưa đầy đủ (mục 7.1), hay chờ LIC-3 | Chủ dự án quyết |
| **BM-0b** | Chạy Q-TECH và Q-TECH-noMP (mục 7.2) | Đồng ý |
| **LIC-3** | Hỏi xác nhận: tác giả SFace, fal, Tencent, OpenAI, NVIDIA | Đồng ý, song song |
| GRP-1, VER-1, CFG-1, LIC-7, REL, asset | **Quyết định phát hành**: xét sau nghiệm thu (mục 6, 9) | — |

---

## Phụ lục A. Asset theo tag

| Tag | Asset | Byte | SHA-256 | Run xác minh | Bộ cài lẻ = bộ cài trong `BoCai.zip` |
|---|---|---|---|---|---|
| v0.2.0b1 | `Snorlu-AI-Culling-0.2.0b1-BoCai.zip` | 151 113 911 | `eb6b87202632bdee77e02fb0df73b59146069581e74fb81fd8ada269c97e1981` | 42208112442 | — |
| v0.2.0b1 | `Snorlu-AI-Culling-0.2.0b1-portable.zip` | 188 451 654 | `d370841c39ad1677fe67261df240b1434de0a048a1e0f84e0576ef3aec05e9cc` | 42208112442 | — |
| v0.2.0b1 | `Snorlu-AI-Culling-Setup-0.2.0b1.exe` | 151 583 045 | `be148bcc76e165ebe9688d7eb9ba656c6f79141d307850ddf0f6ba6a98197db6` | 42208112442, 42245312724 | **trùng** |
| v0.2.0b2 | `KiraPick-0.2.0b2-BoCai.zip` | 151 138 706 | `e8565643ade44b111d02795735987b37fdfc87981b094beb2a0bd178cdf16626` | 42208112442 | — |
| v0.2.0b2 | `KiraPick-0.2.0b2-portable.zip` | 188 458 070 | `862ac1f58dbd7d2ed44a71ef62d8e81fe95290796eca111493434330e9ca58cc` | 42208112442 | — |
| v0.2.0b2 | `KiraPick-Setup-0.2.0b2.exe` | 151 607 578 | `3a972050d110d951e137dd118d558ea1d3673935049789fccd6be07cd568c7f1` | 42208112442, 42245312724 | **trùng** |
| v0.2.0b3 | `KiraPick-0.2.0b3-BoCai.zip` | 253 725 148 | `ce46082ad473df79c4e24cf1e05e6b827f614171dce7f47ade4f21bb7a75fc24` | 42208112442 | — |
| v0.2.0b3 | `KiraPick-0.2.0b3-portable.zip` | 292 921 518 | `f8e494232c1a6aba5fedb3f0fbc2a181c271e562112128ff9cb53ce4dbdd3871` | 42208112442 | — |
| v0.2.0b3 | `KiraPick-Setup-0.2.0b3.exe` | 254 170 219 | `c14ff98df32de3b410154cb80adad5055c39fe71f166181840f64e346974192e` | 42208112442, 42245312724 | **trùng** |
| v0.2.0b4 | `KiraPick-0.2.0b4-BoCai.zip` | 256 917 951 | `40f9a50c3c79c03f285ef94ce2f9778c38c3c7137c62ed2fd74bc8987b843ce9` | 42208112442 | — |
| v0.2.0b4 | `KiraPick-0.2.0b4-portable.zip` | 296 920 497 | `5bb75f9d52ea7029ab4dabaab380cb6c73b98e77399c74c153e0e3b885eaa4fe` | 42208112442 | — |
| v0.2.0b4 | `KiraPick-Setup-0.2.0b4.exe` | 257 361 437 | `3cfef21a5c5a2d11aa45c2e176a5bb4eed6e2c2f6f2f6377b7f53c37155dcbbd` | 42208112442, 42245312724 | **trùng** |
| v0.3.0b1 | `KiraPick-0.3.0b1-BoCai.zip` | 511 518 238 | `cf9c4484f5d603c051beeb71cec21c709fc03cbbaed30b8a44f8591b5233f23f` | 42208112442 | — |
| v0.3.0b1 | `KiraPick-0.3.0b1-portable.zip` | 553 532 733 | `191856dda8d3e4e80fa67f9a6713510d1d6e9fce3c75948370ccb096fe1cbea7` | 42208112442 | — |
| v0.3.0b1 | `KiraPick-Setup-0.3.0b1.exe` | 511 884 325 | `e28fd7a9bcad5b8310125142d48c36e995ef0a89d4c141008039df53382236e9` | 42208112442, 42245312724 | **trùng** |
| v0.3.0b2 | `KiraPick-0.3.0b2-BoCai.zip` | 769 883 196 | `7f5c89e107b8310b71e8830385a0b936a41d998e223388b2558ce0975824ce0b` | 42208112442 | — |
| v0.3.0b2 | `KiraPick-0.3.0b2-portable.zip` | 813 335 962 | `3d616a0ee276d9698caec6aab7dfbd394813d2219bd80e580c61f923f26beb3c` | 42208112442 | — |
| v0.3.0b2 | `KiraPick-Setup-0.3.0b2.exe` | 770 170 259 | `08fa3bc765ceb0d6dea07a6b43c74f6822f09a5a3ecdd7deaa988b069b42b04c` | 42208112442, 42245711312 | **trùng** |
| v0.3.0b3 | `KiraPick-0.3.0b3-BoCai.zip` | 769 983 865 | `148fc22327f39b1998533724724ebc387b88bf1e31823607ed7ede3dfab7b1c6` | 42208112442 | — |
| v0.3.0b3 | `KiraPick-0.3.0b3-portable.zip` | 813 338 172 | `a0d7b5faec677ec5215dfe569c5870e639312e7ed4f33296b7ded15c7c1ba1d7` | 42208112442 | — |
| v0.3.0b3 | `KiraPick-Setup-0.3.0b3.exe` | 770 270 624 | `4d68086b9ec80a692566d911263bbcdb7d81b8f896aa93fee695c243108d7f10` | 42208112442, 42245312724 | **trùng** |
| v0.3.0b4 | `KiraPick-0.3.0b4-BoCai.zip` | 769 737 030 | `17e4b5e5b80d73d4390399488d69adcecfc9c0117158efe8915d19c7dfb8d95e` | 42208112442 | — |
| v0.3.0b4 | `KiraPick-0.3.0b4-portable.zip` | 813 338 573 | `a5721099f687e65605db46799ef401b3706ca28ca88457e3cdfecf9fcef1485e` | 42208112442 | — |
| v0.3.0b4 | `KiraPick-Setup-0.3.0b4.exe` | 770 024 870 | `4f59141530561751b4df65008958eadc06c49b557697f5931de3d6860fb8d7bb` | 42208112442, 42245711312 | **trùng** |
| v2.0.0 | `KiraPick-2.0.0-BoCai.zip` | 769 970 494 | `3b87b79346062c4b89879700217ca12951065280ec300c30a0ca968893c38cec` | 42208112442 | — |
| v2.0.0 | `KiraPick-2.0.0-portable.zip` | 813 336 900 | `bce623170b80b3f3ced7da0f3b41abbda7104ef280a91f8c29544ac7398db66a` | 42208112442 | — |
| v2.0.0 | `KiraPick-Setup-2.0.0.exe` | 770 257 617 | `8ec8779f485a10281935b97aa7b9e14194a96cccf3dde87d1326de762ff776b8` | 42208112442, 42245312724 | **trùng** |
| v2.0.1 | `KiraPick-2.0.1-BoCai.zip` | 433 172 035 | `eba69fe445104eb845d021d3ba619d8458a547c8e9b85f9c2a19a767e9ab4bcb` | 42208112442 | — |
| v2.0.1 | `KiraPick-2.0.1-portable.zip` | 477 363 705 | `e985a68bdc23a2052ab7dfbe568e42be99ebc0939d7e6b12c3ef2592b0149b07` | 42208112442 | — |
| v2.0.1 | `KiraPick-Setup-2.0.1.exe` | 433 562 100 | `10a218080512fdbaa212191e90bfc6fd2626829cf510dcb0fb18075ccafceadd` | 42208112442, 42245312724 | **trùng** |
| v2.0.2 | `KiraPick-2.0.2-BoCai.zip` | 433 190 055 | `87cc32d1dd65e734e613ed916f43350633678225708e6294ac17dd6124197fbb` | 42208112442 | — |
| v2.0.2 | `KiraPick-2.0.2-portable.zip` | 477 364 616 | `462acd1fb0ac409f047094a135dcbe453792bedf32b51f657e2a0d082e981125` | 42208112442 | — |
| v2.0.2 | `KiraPick-Setup-2.0.2.exe` | 433 579 259 | `2803a39e178f362e3522280bfcd7340e3d7176d3eafda7c21874c34f7c77c146` | 42208112442, 42245312724 | **trùng** |
| v2.0.3 | `KiraPick-2.0.3-BoCai.zip` | 433 171 065 | `1ad8188ff458c16aad0089fa5f3ce03e03d6a10be4dce94e915e24ddfc65e7d3` | 42208112442 | — |
| v2.0.3 | `KiraPick-2.0.3-portable.zip` | 477 363 258 | `aa82b9e7d1805b82ebc3cdad909be3c1495753af8eb0ecea46a710227018fc9e` | 42208112442 | — |
| v2.0.3 | `KiraPick-Setup-2.0.3.exe` | 433 561 153 | `650e0e8449e5528831cc2cf84d05703333cb826fc2b98c645f93f2c735d80a57` | 42208112442, 42245312724 | **trùng** |
| v2.0.4 | `KiraPick-2.0.4-BoCai.zip` | 433 181 858 | `cdb0f4169377de3cb064b71015d8700207fca82a49aea7f521df0b3665a88c8f` | 42208112442 | — |
| v2.0.4 | `KiraPick-2.0.4-portable.zip` | 477 369 509 | `d2ece5c95bfdea444dff07024bc4c9db85021ccd69de1f96c73c90c74d25914c` | 42208112442 | — |
| v2.0.4 | `KiraPick-Setup-2.0.4.exe` | 433 571 984 | `9e24d441fe9000c20034b8ab4ddbdec8d5ab6cfe40a42b92de35e44bacff8bf6` | 42208112442, 42245312724 | **trùng** |
| v2.0.5 | `KiraPick-2.0.5-BoCai.zip` | 433 181 206 | `2028640688b7b62a698948a27795b15948eb357a1d8b7f4ee18228f1b075b577` | 42208112442 | — |
| v2.0.5 | `KiraPick-2.0.5-portable.zip` | 477 372 813 | `a25004659371e4f4067dc0e4b6bacc0155d68fb2067e684478a5e4fd1b410de9` | 42208112442 | — |
| v2.0.5 | `KiraPick-Setup-2.0.5.exe` | 433 571 497 | `f965fe7ed78c416d3a4939d0c477c487591d8c5a4a7afae52ef98b0172f02c9f` | 42208112442, 42245312724 | **trùng** |
| v2.0.6 | `KiraPick-2.0.6-BoCai.zip` | 433 189 517 | `4a916134c39ba2029ba4febe5dc5df1345c3dc302e75412115cc744b8eeed763` | 42208112442 | — |
| v2.0.6 | `KiraPick-2.0.6-portable.zip` | 477 378 490 | `9d183c91ebe3f896b5747e60ac18038ddb55dc4f65d149f01815c0ea91d3b18e` | 42208112442 | — |
| v2.0.6 | `KiraPick-Setup-2.0.6.exe` | 433 579 458 | `00afb3444f54a8b28bfb7c62a9668b8c081858d0133828d3d7771f5d93f49e45` | 42208112442, 42245312724 | **trùng** |
| v2.2.0a | `HUONG_DAN_CAI_DAT.txt` | 5 302 | `a4578a224913e8a180cd9c8f37fbc67d359116aeaa87270fb5a9ae9fa32df105` | 42208112442 | — |
| v2.2.0a | `KiraPick-Setup-2.2.0a-1.bin` | 1 797 875 712 | `ace7fa83258eeea23f91321d1f7c780dccb9f763d14420bd92dec8802022d383` | 42208112442 | — |
| v2.2.0a | `KiraPick-Setup-2.2.0a-2.bin` | 1 306 652 017 | `8f932231bad7e84f4d0c3470eeb6779bd15e88044307c8fa0da782e1ad578a9a` | 42208112442 | — |
| v2.2.0a | `KiraPick-Setup-2.2.0a.exe` | 2 124 090 | `b60a89a4eb5cd4a16dc032ad2446d0d0e5d5bbf20e348ada6d0c598c08d093ee` | 42208112442 | — |
| v2.2.1 | `KiraPick-2.2.1-BoCai.zip` | 1 148 044 235 | `6f464e943ff7b0abb34132a83b5d26cc3d1ee430c3cafbc059b04ce09f72311f` | 42208112442 | — |
| v2.2.1 | `KiraPick-2.2.1-portable.zip` | 1 209 369 564 | `0c3a3ecc73968002342aef35a1feda4df9c28571a60dcf4a1b52b153331b41e5` | 42208112442 | — |
| v3.0.0 | `KiraPick-3.0.0-BoCai.zip` | 1 145 855 229 | `9c1e8678ed1eaffdfba4ca56e25e9b5ceda9e1a0880001c8e58d3a3dc0d2e92a` | 42199575662, 42208112442 | — |
| v3.0.0 | `KiraPick-3.0.0-portable.zip` | 1 206 122 458 | `ba5833c396e198c28d1158d1de1aa97a6ea57e987802b1ac601acfd8c48c5d79` | 42199575662, 42208112442 | — |
| v3.0.0a | `HUONG_DAN_CAI_DAT.txt` | 6 291 | `298697d84b5b4ee0f84c68a79c3cd2756ae753edf8affd29b5924a7075a82bc9` | 42199575662 | — |
| v3.0.0a | `KiraPick-Setup-3.0.0a-1.bin` | 1 797 876 736 | `4542bea179df002798474b58401234d7bc7a938c604e1003d28a2eaffb4e45c6` | 42199575662 | — |
| v3.0.0a | `KiraPick-Setup-3.0.0a-2.bin` | 1 314 386 504 | `cdc39fee7aa0241ae93a7a4692003f471cb2de69e40fcbd9fb3a1b7d20b4249f` | 42199575662 | — |
| v3.0.0a | `KiraPick-Setup-3.0.0a.exe` | 2 123 057 | `59dd2734984f7d748502d6e332e7203b2954d11466f782617fbefa854d6c94c9` | 42199575662 | — |
| v3.0.0a | `owner_backup.ps1` | 6 265 | `67dc1097627ff515d0c03f2a957e851ecd388157eb8b34754057e21afd854f51` | 42199575662 | — |

**Trọng số trong gói, theo tag** [Bộ cài]: (chỉ nêu file không có trong cấu hình A)

| Tag | File trong gói nhưng không có trong cấu hình A |
|---|---|
| v0.2.0b1 | SFace |
| v0.2.0b2 | SFace |
| v0.2.0b3 | SFace |
| v0.2.0b4 | SFace |
| v0.3.0b1 | SFace, TOPIQ-IAA |
| v0.3.0b2 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v0.3.0b3 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v0.3.0b4 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.0 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.1 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.2 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.3 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.4 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.5 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.0.6 | ArcFace, SFace, TOPIQ-IAA, YoutuReID |
| v2.2.0a | ArcFace, CLIP, CLIP prompts, LAION, SFace, TOPIQ-IAA, TOPIQ-KonIQ, TOPIQ-face, YoutuReID |
| v2.2.1 | ArcFace, CLIP, CLIP prompts, LAION, SFace, TOPIQ-IAA, TOPIQ-KonIQ, TOPIQ-face, YoutuReID |
| v3.0.0 | ArcFace, CLIP, CLIP prompts, LAION, SFace, TOPIQ-IAA, TOPIQ-KonIQ, TOPIQ-face, YoutuReID |
| v3.0.0a | ArcFace, CLIP, CLIP prompts, LAION, SFace, TOPIQ-IAA, TOPIQ-KonIQ, TOPIQ-face, YoutuReID |

---

## Phụ lục B. Bằng chứng theo từng file (từ bản trình 2)

### B.1 Cách xét

Mỗi file được xét **hai câu hỏi tách riêng**:

1. **Phạm vi giấy phép của trọng số.** **Chủ sở hữu** (tác giả hoặc tổ chức làm ra mô hình) có công bố giấy phép cho mô
   hình đó, hoặc cho nơi chính họ đăng file đó không? File app dùng có đúng là file đó không (cùng SHA-256, hoặc chuyển đổi
   từ đúng file đó)?
   - **Đủ căn cứ** khi chủ sở hữu có công bố, và không có điều khoản nào của chủ sở hữu mâu thuẫn.
   - **Chờ xác minh** khi chỉ có **bên phân phối lại** công bố giấy phép (chủ sở hữu im lặng), hoặc có điều khoản mâu
     thuẫn.
2. **Thông tin dữ liệu huấn luyện.** Ghi riêng, là **thông tin còn thiếu**. Không trộn vào câu hỏi 1.

**Quy tắc đưa vào:** file chưa đủ căn cứ cho một mục đích thì **không** được đưa vào cấu hình hoặc gói phục vụ mục đích đó.
Mục đích ở đây là dùng cho job có thu tiền, hoặc phân phối.

### B.2 Trọng số mô hình

| File (SHA-256 file cài trong 3.0.0) | Chủ sở hữu, nguồn | Phạm vi giấy phép trọng số [Nguồn] | Dùng cho job có thu tiền | Phân phối | Nghĩa vụ đi kèm | Thông tin còn thiếu (giấy phép) | Thông tin dữ liệu huấn luyện (còn thiếu) | **Quyết định** |
|---|---|---|---|---|---|---|---|---|
| `yolox_s.onnx` `c5c2d13e…8063` | Megvii; release `0.1.1rc0` của repo YOLOX | Repo của Megvii, nơi Megvii tự đăng file, có LICENSE Apache-2.0. Ngoài ra opencv_zoo có file **giống từng byte** (`object_detection_yolox_2022nov.onnx`, LFS oid `c5c2d13e…8063`), README thư mục ghi "All files in this directory are licensed under Apache 2.0" | **Đủ** | **Đủ** | Toàn văn Apache-2.0, thông báo Megvii | Release không ghi riêng giấy phép cho file trọng số | COCO 2017: ảnh theo giấy phép Flickr từng ảnh. **Chưa xác minh** | **Giữ** |
| `yolox_m.onnx` `be329495…6aaf` (float16 của `21ff6cfd…b3f`) | Megvii; release `0.1.1rc0` | Như YOLOX-S nhưng **chỉ có** LICENSE repo của Megvii; không có bản nào kèm câu giấy phép cho file | **Đủ** (cùng căn cứ với S) | **Đủ** | Như trên + **ghi rõ đã đổi sang float16** | Như S | COCO 2017 | **Giữ** |
| `face_detection_yunet_2023mar.onnx` `8f2383e4…52fa4` | Shiqi Yu | opencv_zoo: LICENSE MIT ghi "Copyright (c) 2020 Shiqi Yu", README "All files in this directory are licensed under MIT". Repo gốc `ShiqiYu/libfacedetection.train` (chứa các file `yunet_*.onnx`) có LICENSE BSD-3 cùng chủ sở hữu. Mã băm LFS trùng file app dùng | **Đủ** | **Đủ** | Thông báo MIT (và BSD-3 của repo gốc) | Repo gốc hiện có LICENSE BSD-3, opencv_zoo ghi MIT. Cả hai cho phép; kèm cả hai thông báo | WIDER FACE. **Chưa xác minh** | **Giữ** |
| `face_recognition_sface_2021dec.onnx` `f55a362e…45c5` (float16 của `0ba9fbfa…79`) | Yaoyao Zhong (tác giả SFace) | opencv_zoo ghi Apache-2.0 cho "all files", nhưng thư mục được **nhân viên OpenCV** thêm (commit 2021-10-15, "Add SFace for face recognition (#3)"); file ONNX do người khác chuyển đổi. **Repo gốc `zhongyy/SFace` không có file giấy phép**. Không thấy công bố của tác giả | **Chờ xác minh** | **Chờ xác minh** | (nếu được xác nhận) Apache-2.0, ghi float16 | Xác nhận của tác giả hoặc BUPT về giấy phép trọng số | Không công bố | **Chờ xác minh**, chưa đưa vào |
| `ediffiqa_tiny_jun2024.onnx` `9426c899…fc6a` | Žiga Babnik (`LSIbabnikz`) | **Chính tác giả** thêm thư mục vào opencv_zoo (commit 2024-08-22, #263) với LICENSE CC BY 4.0. Repo gốc của tác giả có LICENSE MIT. Mã băm LFS trùng | **Đủ** | **Đủ** | Ghi công CC BY 4.0: tác giả, tên tác phẩm, đường dẫn giấy phép, "không chỉnh sửa" | — | Backbone MobileFaceNet huấn luyện sẵn. **Chưa xác minh** | **Giữ** |
| `mediapipe_face_landmarks_v2.onnx` `a044fec2…f56` | Google | Model card PDF "Face Mesh V2" của Google ghi "LICENSED UNDER Apache License, Version 2.0". File gốc `face_landmarker.task` tải từ địa chỉ chính thức của Google (`storage.googleapis.com/mediapipe-models/…/float16/1/`), SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` | **Đủ** | **Đủ** | Toàn văn Apache-2.0; **ghi rõ đã chuyển `.task` sang ONNX** | File `.task` không kèm giấy phép; model card không ghi mã băm. **Chưa chạy lại chuyển đổi** để chứng minh file ONNX trong repo sinh ra từ đúng file `.task` trên | Model card: ảnh thu thập có đồng ý, dữ liệu tổng hợp. Chi tiết không công bố | **Giữ**, kèm điều kiện: chạy lại chuyển đổi và khớp mã băm trước khi đóng gói |
| `mediapipe_face_blendshapes_v2.onnx` `ce56bc10…d77` | Google | Model card "Blendshape V2": Apache-2.0. Cùng file `.task` | **Đủ** | **Đủ** | Như trên | Như trên | Model card: mẫu thu trong phòng thí nghiệm, dữ liệu tổng hợp | **Giữ**, cùng điều kiện |
| `laion_aesthetic.onnx` `5a5e0481…4f53` | Christoph Schuhmann (LAION) | File gốc `sac+logos+ava1-l14-linearMSE.pth` nằm **trong repo của chủ sở hữu**, LICENSE Apache-2.0; SHA-256 `21dd590f…f1e0` trùng | Đủ (riêng file này) | Đủ | Apache-2.0, ghi đã chuyển ONNX | — | AVA và các bộ khác. Chưa xác minh | **Không đưa vào**: chỉ chạy được trên vector CLIP, mà CLIP chưa đủ căn cứ |
| `clip_l14_image.onnx` `223bd172…587c` + `clip_prompts_v1.npz` | OpenAI | Repo `openai/CLIP`: MIT. **Model card của chủ sở hữu** nói mọi trường hợp triển khai là "ngoài phạm vi" → mâu thuẫn với dùng cho dịch vụ | **Chờ xác minh** | **Chờ xác minh** | MIT | Xác nhận của OpenAI | Không công bố | **Chờ xác minh**, chưa đưa vào |
| `w600k_r50.onnx` (ArcFace) | InsightFace | Chủ sở hữu ghi "non-commercial research purposes only" | **Không** | **Không** | — | — | WebFace600K | **Loại** |
| `person_reid_youtu_2021nov.onnx` (YoutuReID) | Tencent Youtu Lab | opencv_zoo ghi Apache-2.0 (nhân viên OpenCV thêm, 2021-11-18, #24). Nguồn được dẫn `ReID-Team/ReID_extra_testdata` **không có giấy phép** | **Chờ xác minh** | **Chờ xác minh** | — | Công bố của Tencent | Bộ dữ liệu nghiên cứu, có DukeMTMC (đã bị rút) | **Loại** khỏi 3.0.1 |
| `topiq_iaa_res50.onnx`, `topiq_nr_koniq_res50.onnx`, `topiq_nr_face_res50.onnx` | Chaofeng Chen (pyiqa) | PolyForm Noncommercial | **Không** | **Không** | — | — | AVA, KonIQ… | **Loại** |

**Ứng viên thay nhận mặt (chưa có trong bộ cài nào):**

| File | Phạm vi giấy phép [Nguồn] | Quyết định |
|---|---|---|
| AuraFace `glintr100.onnx` (`a7933ea5…5c60`, 260 694 151 byte, ResNet-100) | Model card của fal ghi Apache-2.0 và "trained on commercially and publicly available data". Nhưng repo cũng phát hành dưới Apache-2.0 **bốn file giống từng byte** với gói `antelopev2` phi thương mại của InsightFace: `scrfd_10g_bnkps`, `2d106det`, `1k3d68`, `genderage` (đã so SHA-256). Giấy phép chung của repo vì vậy **không theo đúng nguồn gốc từng file**. Riêng `glintr100.onnx` khác bản của InsightFace (`4ab1d643…4cdf`). Chưa rõ nó huấn luyện từ đầu hay tinh chỉnh từ trọng số InsightFace | **Chờ xác minh** (hỏi fal về nguồn gốc). Lưu ý: ResNet-100 260 MB **chậm hơn** ArcFace R50 |
| dlib `dlib_face_recognition_resnet_model_v1` | Tác giả công bố CC0 (bản kiểm trước). Chưa tải, chưa kiểm file; cần thêm thư viện dlib | **Chưa kiểm** |

### B.3 Thư viện chạy kèm, theo gói

| Thành phần | Gói | Căn cứ phân phối [Nguồn] | Nghĩa vụ | Quyết định |
|---|---|---|---|---|
| ONNX Runtime 1.24.4 | cả ba | MIT | LICENSE + `ThirdPartyNotices.txt` của ORT | Giữ |
| `DirectML.dll` 1.15.4 | DirectML, portable | Điều khoản DirectML của Microsoft (trong gói NuGet `Microsoft.AI.DirectML` 1.15.4, cùng kích thước 18 527 776 byte với file đã cài): cho phép "copy and distribute … in applications … you develop", chỉ cho Windows / Xbox | Kèm điều khoản; không dịch ngược | Giữ. **Thông tin còn thiếu:** điều khoản nói phần mềm "có thể thu thập thông tin … gửi Microsoft". Chưa đo lưu lượng mạng của DirectML; app vẫn chạy khi tắt mạng |
| `onnxruntime_providers_cuda.dll` | CUDA | MIT | như ORT | Giữ |
| `cudart64_12`, `cublas64_12`, `cublasLt64_12`, `cufft64_11`, `cufftw64_11`, `curand64_10`, `nvrtc64_120_0` (+ `.alt`), `nvrtc-builtins64_129` | CUDA | EULA CUDA (file `License.txt` trong gói NVIDIA 12.9), Attachment A liệt kê `cudart.dll`, `cufft.dll`, `cufftw.dll`, `cublas.dll`, `cublasLt.dll`, `curand.dll`, `nvrtc.dll`, `nvrtc-builtins.dll`. Điều kiện: app có chức năng đáng kể ngoài SDK; chỉ app được truy cập các file đó | Theo EULA | **Giữ** |
| `cudnn*64_9.dll` (10 file) | CUDA | SLA cuDNN trong gói `nvidia-cudnn-cu12` 9.28 chỉ liệt kê `cudnn64_7.dll` là phần được phân phối. **Không nêu** các DLL cuDNN 9 | — | **Chờ xác minh**. Xem LIC-7: bỏ khỏi gói và yêu cầu người dùng tự cài cuDNN, hoặc chờ NVIDIA làm rõ |
| Bản sao DLL NVIDIA trong `_internal\nvidia\…\bin\` | CUDA | như trên | — | **Bỏ bản trùng** |
| `onnxruntime_providers_tensorrt.dll` | CUDA | MIT, nhưng app không dùng TensorRT | — | **Bỏ** |
| `opencv_videoio_ffmpeg4140_64.dll` (FFmpeg) | cả ba | LGPL-2.1: phải kèm toàn văn và chỉ nguồn; 3.0.0 **không ghi** | — | **Bỏ**. App không dùng `cv2.VideoCapture` [Mã] |
| OpenCV 4.14 | cả ba | Apache-2.0 | Toàn văn + thông báo thư viện con | Giữ |
| Qt 6 / PySide6 6.12 | cả ba | LGPL-3.0 | Toàn văn LGPL-3.0 **và** GPL-3.0; chỉ nguồn; DLL thay được | Giữ, bổ sung toàn văn |
| rawpy / LibRaw | cả ba | LGPL-2.1 hoặc CDDL-1.0 | Toàn văn | Giữ, bổ sung toàn văn |
| Python, NumPy, Pillow và các gói khác | cả ba | PSF, BSD, HPND… | Sinh bảng tự động lúc build | Giữ |
