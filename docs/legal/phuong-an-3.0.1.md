# Phương án 3.0.1 và tiêu chí nghiệm thu (bản trình, 2026-11-06)

**Trạng thái:** chỉ là phương án. **Chưa sửa mã, chưa build, chưa đổi mặc định, chưa đụng tới release nào trên GitHub.**

- Mọi thao tác dưới đây đều cần chủ dự án duyệt riêng: sửa mặc định, thay hoặc gỡ asset, merge vào `main`, tạo tag, phát
  hành.
- Xác nhận của chủ dự án chỉ duyệt **việc triển khai trong dự án**. **Quyền sử dụng** phải dựa trên điều khoản hoặc bên cấp
  quyền.

**Nguồn bằng chứng** (cùng ký hiệu với `docs/legal/kiem-ke-quyen-su-dung.md`):

| Ký hiệu | Nghĩa |
|---|---|
| **[Bộ cài]** | Kiểm trực tiếp asset đã phát hành. CI job `inspect-release`: run **42199575662** (v3.0.0, v3.0.0a) và run **42208112442** (18 release từ v0.2.0b1 tới v3.0.0, gồm cả `portable.zip`). Cài silent trên máy CI dùng xong là bỏ, **không chạy app** |
| **[Mã]** | Đọc mã trên `beta` (HEAD `532e388`) |
| **[Điều khoản]** | Giấy phép / model card gốc |

---

## 1. Bảng thành phần

### 1.1 Ba mức căn cứ (dùng chung cho mọi tài liệu và cho `configs/media-models.json`)

| Mức | Nghĩa | Thành phần |
|---|---|---|
| **A. Có căn cứ** | Bên có quyền công bố giấy phép cho chính file đó, và giấy phép cho phép dùng thương mại và phân phối | eDifFIQA; ONNX Runtime; OpenCV; Qt / PySide6; LibRaw; DirectML; Python |
| **B. Căn cứ chưa đầy đủ** | Có giấy phép mở công bố, nhưng **chưa xác minh** được: giấy phép đó có phủ file trọng số không, hoặc điều khoản của dữ liệu huấn luyện | YOLOX-S / -M, YuNet, SFace, MediaPipe mesh / blendshapes, đầu LAION |
| **C. Không có căn cứ / chưa xác minh** | Giấy phép cấm thương mại, không có giấy phép, hoặc model card nói "ngoài phạm vi" | ArcFace, YoutuReID, TOPIQ ×3, CLIP (+ `clip_prompts`) |

**Gỡ mâu thuẫn trạng thái YOLOX:**
- Bản kiểm kê v2 ghi "có theo LICENSE repo" cho job có thu tiền. `media-models.json` lại ghi `pending`.
- **Thống nhất: YOLOX thuộc mức B.**
  - LICENSE Apache-2.0 nằm ở **repo mã**.
  - File `yolox_s.onnx` / `yolox_m.onnx` được đăng ở mục release của **cùng repo**, nhưng không có câu nào nói rõ trọng
    số theo giấy phép nào.
  - Dữ liệu huấn luyện là COCO: ảnh của COCO theo giấy phép Flickr của từng ảnh.
- Mục 5 của bản kiểm kê sẽ được sửa theo mức này khi làm (một dòng).
- `media-models.json` giữ `pending` **cho tới khi chủ dự án chốt MOD-3** (mục 6). Chốt "giữ" thì đổi thành
  `approved_with_risk`, kèm ghi rõ: đây là **chấp nhận rủi ro**, **không phải** căn cứ quyền.

### 1.2 Trọng số: giữ hay loại trong 3.0.1

SHA-256 là của **file đã cài trong 3.0.0** [Bộ cài], kèm file gốc nếu app đã đổi sang float16.

| Thành phần | File | Nguồn và phiên bản | SHA-256 (đã cài / gốc) | Căn cứ dùng cho job có thu tiền | Căn cứ phân phối | Đề xuất 3.0.1 |
|---|---|---|---|---|---|---|
| Dò người YOLOX-S | `yolox_s.onnx` | Megvii-BaseDetection/YOLOX, release `0.1.1rc0` | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` (đúng file gốc) | **B**: Apache-2.0 của repo | B | **Giữ nếu MOD-3 = giữ** |
| Dò người YOLOX-M | `yolox_m.onnx` | như trên | `be329495ec618a375a6b9bf04c155aea364863e4ef15e02561c9b062a8096aaf` / gốc `21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f` (app đổi sang float16) | B | B | Giữ nếu MOD-3 |
| Dò mặt YuNet | `face_detection_yunet_2023mar.onnx` | opencv_zoo commit `48b10fa5` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` (đúng file gốc) | **B**: MIT; dữ liệu WIDER FACE chưa xác minh | B (MIT) | Giữ nếu MOD-3 |
| Nhận mặt SFace | `face_recognition_sface_2021dec.onnx` | opencv_zoo `48b10fa5` | `f55a362e04742de60c22a70389d8495f1e5c695f59c8b086549482e999ad45c5` / gốc `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` (float16) | **B**: Apache-2.0; dữ liệu không công bố | B | Giữ nếu MOD-3 |
| Chất lượng mặt eDifFIQA | `ediffiqa_tiny_jun2024.onnx` | opencv_zoo `48b10fa5` | `9426c899cc0f01665240cb7d9e7f98e18e24e456c178326c771a43da289bfc6a` (đúng file gốc) | **A**: CC BY 4.0 | A, kèm ghi công | **Giữ** |
| Mắt: MediaPipe mesh | `mediapipe_face_landmarks_v2.onnx` | Google MediaPipe Face Landmarker v2 (`.task`), app chuyển sang ONNX, lưu trong repo | `a044fec26cd90125566eb8703258dd7a211cca60423801462663af8f13636f56` | **B**: model card Apache-2.0; file `.task` không kèm giấy phép | B | Giữ nếu MOD-3 |
| Mắt: MediaPipe blendshapes | `mediapipe_face_blendshapes_v2.onnx` | như trên | `ce56bc10f1b0306701b8bdb5cd05661a37a380f62638db7102bb61d6bc0d1a77` | B | B | Giữ nếu MOD-3 |
| Đầu thẩm mỹ LAION | `laion_aesthetic.onnx` | `sac+logos+ava1-l14-linearMSE.pth` (`21dd590f…f1e0`), app chuyển sang ONNX | `5a5e04813c758e18cad2d45c919096e5e552a422620022e48353598722614f53` | B; **chỉ chạy được khi có CLIP** | B | **Đi cùng quyết định CLIP** (LIC-6) |
| CLIP ViT-L/14 | `clip_l14_image.onnx` | OpenAI `ViT-L-14.pt` (`b8cca3fd…3836`) → ONNX float16 | `223bd17288a5d33f105209f45973e1f2455d14e97a8cf7bcdb2f453ee24e587c` | **C**: model card nói triển khai "ngoài phạm vi". Việc chủ dự án chấp nhận rủi ro **không phải** căn cứ | C | **Đề xuất loại** (LIC-6) |
| Câu mẫu CLIP | `clip_prompts_v1.npz` | tính lúc build từ CLIP | `cbe112ddff60fb3e5e9bf17c3422d6da9e9bc29fe16e9def785859f23607bd6d` | C (dẫn xuất từ CLIP) | C | Theo CLIP |
| **ArcFace** | `w600k_r50.onnx` | InsightFace `buffalo_l` v0.7 | `761eefe5…f5c3` / gốc `4c06341c…9e43` | **C**: "non-commercial research purposes only" | C | **Loại** |
| **YoutuReID** | `person_reid_youtu_2021nov.onnx` | opencv_zoo `48b10fa5` | `16d61f9b…c55` / gốc `05796833…580d` | **C**: chưa xác minh (văn bản Apache không ghi chủ thể quyền; repo gốc không có giấy phép; dữ liệu nghiên cứu, có DukeMTMC đã bị rút) | C | **Loại** |
| **TOPIQ IAA** | `topiq_iaa_res50.onnx` | pyiqa `cfanet_iaa_ava_res50-3cd62bb3.pth` → ONNX float16 | `3b7ebfd8…b3e4` | **C**: PolyForm Noncommercial | C | **Loại** |
| **TOPIQ NR KonIQ** | `topiq_nr_koniq_res50.onnx` | pyiqa → ONNX float16 | `240a4068…148f` | C | C | **Loại** |
| **TOPIQ NR face** | `topiq_nr_face_res50.onnx` | pyiqa → ONNX float16 | `4394bd18…40f1` | C | C | **Loại** |

### 1.3 Thư viện chạy kèm (runtime)

| Thành phần | Có trong 3.0.0 | Căn cứ | Đề xuất 3.0.1 |
|---|---|---|---|
| ONNX Runtime 1.24.4 | có | A, MIT | Giữ |
| ORT DirectML + `DirectML.dll` (bản DirectML) | có | A, điều khoản tái phân phối của Microsoft | Giữ |
| ORT CUDA provider + DLL NVIDIA (bản CUDA) | có | **cần đọc lại EULA** CUDA 12 / cuDNN 9 (danh sách file được tái phân phối) | Giữ sau khi đọc EULA (LIC-3); **bỏ bản sao trùng** ở `_internal\nvidia\…\bin\` nếu app vẫn chạy |
| **`onnxruntime_providers_tensorrt.dll`** (bản CUDA) | có | MIT, nhưng app không dùng TensorRT | **Bỏ** khi đóng gói |
| OpenCV 4.14 | có | A, Apache-2.0 | Giữ |
| **`opencv_videoio_ffmpeg4140_64.dll` (FFmpeg)** | có, **không ghi trong NOTICES** | LGPL-2.1, phải kèm toàn văn và chỉ nguồn | **Bỏ** khi đóng gói. [Mã] app không gọi `cv2.VideoCapture`. Cách làm: thêm tên DLL vào bộ lọc `_UNUSED` trong `packaging/kirapick.spec`. Test: `--self-test` vẫn chạy OpenCV DNN và đọc ảnh |
| Qt 6 / PySide6 6.12 | có | A, LGPL-3.0 | Giữ, **bổ sung toàn văn** LGPL-3.0 + GPL-3.0 |
| rawpy / LibRaw | có | A, LGPL-2.1 hoặc CDDL-1.0 | Giữ, bổ sung toàn văn |
| Python + các gói Python khác | có | giấy phép từng gói | Giữ; sinh bảng giấy phép tự động lúc build |

### 1.4 Nghĩa vụ thông báo của từng thành phần được giữ

3.0.0 **thiếu toàn văn** của mọi giấy phép bắt buộc [Bộ cài]. 3.0.1 sẽ kèm thư mục `{app}\docs\licenses\` với các file
dưới đây. `THIRD_PARTY_NOTICES.md` có một dòng cho từng thành phần, trỏ tới đúng file.

| Thành phần | Nghĩa vụ |
|---|---|
| YOLOX-S / -M | Toàn văn Apache-2.0; giữ thông báo bản quyền Megvii; **ghi rõ YOLOX-M đã đổi sang float16**; kèm file NOTICE nếu repo có (kiểm lúc làm) |
| YuNet | Thông báo bản quyền và đoạn cho phép của MIT |
| SFace | Toàn văn Apache-2.0; **ghi rõ đã đổi sang float16** |
| eDifFIQA | Ghi công: tác giả, tên tác phẩm, đường dẫn CC BY 4.0, "không chỉnh sửa" (đã có ghi công; thêm đường dẫn giấy phép) |
| MediaPipe ×2 | Toàn văn Apache-2.0; **ghi rõ đã chuyển từ `.task` sang ONNX** |
| LAION, CLIP (nếu giữ) | Apache-2.0 (LAION) và thông báo MIT (CLIP); ghi rõ đã chuyển sang ONNX / float16 |
| ONNX Runtime | Thông báo MIT + `ThirdPartyNotices.txt` của ORT |
| DirectML | Điều khoản giấy phép DirectML của Microsoft |
| DLL NVIDIA (bản CUDA) | Thông báo theo EULA (đọc lại khi làm) |
| OpenCV | Toàn văn Apache-2.0 + thông báo các thư viện con của OpenCV |
| Qt / PySide6 | Toàn văn **LGPL-3.0 và GPL-3.0**; chỉ nơi lấy mã nguồn; DLL Qt nằm rời nên người dùng thay được (bản đóng gói thư mục đã đáp ứng) |
| LibRaw (rawpy) | Toàn văn LGPL-2.1 (hoặc CDDL-1.0) |
| FFmpeg | **Không còn nghĩa vụ** nếu bỏ DLL. Nếu giữ: toàn văn LGPL-2.1 và chỉ nguồn của đúng bản build |
| Python, NumPy, Pillow… | PSF và các giấy phép BSD / HPND…: sinh tự động lúc build |
| Mô hình bị loại | Xoá khỏi NOTICES và `model-licenses.md` trong bộ cài, chỉ giữ trong tài liệu lịch sử của repo |

---

## 2. Chặn cho cả hai chế độ

**Nguyên tắc:**
- **Một danh sách cho phép duy nhất**, theo **SHA-256** chứ không theo tên file. Mở rộng `configs/media-models.json`
  thành `configs/model-policy.json` dùng chung cho Chụp cá nhân và Media.
  - Đổi tên file ArcFace thành tên của SFace vẫn bị chặn.
  - Đặt file vào thư mục khác qua `KIRAPICK_MODELS_DIR` vẫn bị chặn.
- **Không xoá dữ liệu cũ:** chỉ không đọc.

### 2.1 Các điểm chặn

| Đường | 3.0.0 [Mã] | 3.0.1 |
|---|---|---|
| Chạy thường, Chụp cá nhân | `embed_job.py:53` tự nạp ArcFace + YoutuReID khi có file; `quality_job.py:195` / `load_extras` nạp TOPIQ | Mọi chỗ mở mô hình đi qua `ModelRegistry.require(id)`: chỉ mở file có id **và** SHA-256 trong danh sách. Gặp file khác thì ghi log "bỏ qua, không được phép", không mở |
| Chạy thường, Media | `MediaRegistry` đã chặn (Mốc 0) | Dùng chung danh sách mới |
| Dự phòng | GPU → CPU; YOLOX-M → S; thiếu file → SFace + màu trang phục | Như cũ, nhưng **mỗi nhánh** đều đi qua `require`. Có test riêng cho từng nhánh |
| `--self-test` | Nạp **mọi** mô hình có mặt | Chỉ nạp mô hình được phép. Báo cáo A ghi id, file, SHA-256, provider của từng file đã mở, và danh sách file **bị bỏ qua** |
| Chỗ đọc `clip_prompts` | `main_window.py:1052` đọc thẳng | Đi qua `require` |
| Cache phiên: vector | `cluster.py:153` `session_profile` chọn cách gom ArcFace nếu phiên có vector `face_arc` | Luôn trả hồ sơ SFace + màu. Không đọc `face_arc`, `body` (và `clip` nếu loại CLIP). **Không cần tính lại**: 3.0.0 vốn luôn lưu vector SFace |
| Cache phiên: điểm | `score.py:91-98` đọc `aesthetic_mos`, `tech_iqa`, `face_iqa` | Chỉ đọc số đo có `model_id` + phiên bản nằm trong danh sách. Số TOPIQ cũ coi như "chưa đánh giá", phần trọng số của nó chia lại (cơ chế N/A sẵn có) |
| `learning.db` | `identity_feedback` lưu giá trị `face_arc` / `body`; gu học từ CLIP | Chỉ đọc và ghi đặc trưng SFace + màu. Bỏ qua cột `face_arc`, `body`, `clip`; **không xoá cột** |
| File cũ khi nâng cấp | Bộ cài không xoá file nào trong `{app}\models` | Thêm `[InstallDelete]` cho 5 file bị loại (và CLIP / LAION / prompts nếu LIC-6 = loại) cùng file `.sha256` đi kèm. Đây là file của app, **không phải** ảnh hay dữ liệu người dùng. Mã vẫn chặn kể cả khi file còn sót |

### 2.2 Test tự động (Linux + Windows CI)

1. **Bọc mọi hàm mở mô hình:** `onnxruntime.InferenceSession`, `cv2.dnn.readNet*`, `FaceRecognizerSF.create`,
   `FaceDetectorYN.create`. Thư mục `models\` chứa **đủ 15 file của 3.0.0**. Khẳng định chỉ file được phép bị mở:
   - đường chạy thường;
   - GPU → CPU;
   - YOLOX-M → S;
   - thiếu từng file;
   - `--self-test`;
   - mở phiên cũ, gom lại, tính lại điểm;
   - Media Mốc 0.
2. **Đổi tên / đổi thư mục:** đặt `w600k_r50.onnx` dưới tên `face_recognition_sface_2021dec.onnx` → bị từ chối vì sai
   SHA-256, app báo SFace "không dùng được" thay vì chạy ArcFace.
3. **Phiên cũ:** dựng một phiên đúng kiểu 3.0.0 (schema v7) có vector `face_arc` / `body` / `clip`, điểm TOPIQ, P/X, sao,
   ❤, nhóm đã gộp / tách / "khác nhau" / đặt tên tay, lịch sử xuất.
4. **Không có mạng:** smoke test hiện có vẫn chạy.

### 2.3 Checklist nghiệm thu: cài mới và nâng cấp

**Cài mới** (máy sạch: CI Windows, sau đó máy chủ dự án):

| # | Kiểm | Đạt khi |
|---|---|---|
| N1 | File trong `{app}\models` | Đúng **danh sách cho phép** (tên + SHA-256), không thừa không thiếu |
| N2 | Không có file trọng số nào khác trong toàn bộ thư mục cài | Không có `.onnx` / `.pth` / `.pt` / `.npz` / `.task` ngoài N1 |
| N3 | DLL | Không có `opencv_videoio_ffmpeg*.dll`; bản CUDA không có `onnxruntime_providers_tensorrt.dll` |
| N4 | `KiraPick.exe --self-test` | Đạt. Báo cáo A chỉ có file trong danh sách |
| N5 | Phân tích một thư mục ảnh mẫu | Log nạp mô hình chỉ có file được phép; có nhóm người, chấm điểm kỹ thuật, chọn ảnh |
| N6 | Tắt mạng | App chạy đủ như N5 |
| N7 | Giấy tờ | `{app}\docs\licenses\` có đủ các file ở mục 1.4 |

**Nâng cấp từ 3.0.0** (cài v3.0.0 thật, tạo dữ liệu, rồi cài 3.0.1 đè lên; làm cho cả DirectML và CUDA):

| # | Kiểm | Đạt khi |
|---|---|---|
| U1 | File cũ | 5 file bị loại (và CLIP / LAION nếu LIC-6 = loại) **không còn** trong `{app}\models` |
| U2 | File cũ đặt lại bằng tay | Copy lại `w600k_r50.onnx` và `topiq_*.onnx` vào `{app}\models` → app **không nạp** (log ghi "bỏ qua") |
| U3 | Phiên đã phân tích bằng 3.0.0 | Mở được. P/X, sao, ❤ **giữ nguyên** (so từng dòng DB trước và sau) |
| U4 | Nhóm chỉnh tay | Gộp, tách, "khác nhau", tên nhóm **giữ nguyên** |
| U5 | Vector, điểm cũ | Gom lại dùng SFace + màu; điểm TOPIQ hiện "chưa đánh giá"; dòng cũ **vẫn còn** trong DB (không xoá) |
| U6 | `learning.db` | Mở được; không đọc `face_arc` / `body` / `clip`; dữ liệu cũ còn nguyên |
| U7 | Ảnh gốc | SHA-256 mọi ảnh gốc và file RAW giống trước khi nâng cấp |
| U8 | Cài lại 3.0.0 lên trên (quay về) | Dữ liệu phiên vẫn mở được (kiểm tính tương thích, không phải khuyến nghị dùng) |
| U9 | Bản cập nhật trong app | 3.0.0 được mời lên 3.0.1; 3.0.0a lên 3.0.1a; bản beta (`3.0.1b…`) **không** được mời |

---

## 3. Bản đã phát hành và đường tải cũ

### 3.1 Asset bị ảnh hưởng [Bộ cài, run 42208112442 và 42199575662]

Mọi asset đều khớp digest của GitHub. `portable.zip` chứa **đúng cùng các file mô hình** với bản cài của cùng release.

| Release | Asset | ArcFace | YoutuReID | TOPIQ | CLIP / LAION |
|---|---|---|---|---|---|
| v0.2.0b1 | `Snorlu-AI-Culling-0.2.0b1-BoCai.zip`, `-portable.zip`, `Setup-0.2.0b1.exe` | không | không | không | không |
| v0.2.0b2–b4 | `KiraPick-0.2.0bN-BoCai.zip`, `-portable.zip`, `Setup-0.2.0bN.exe` | không | không | không | không |
| **v0.3.0b1** | `KiraPick-0.3.0b1-BoCai.zip`, `-portable.zip`, `Setup-0.3.0b1.exe` | không | không | **IAA** | không |
| **v0.3.0b2–b4** | 3 asset mỗi bản | **có** (fp32) | **có** (fp32) | IAA | không |
| **v2.0.0** | `KiraPick-2.0.0-BoCai.zip`, `-portable.zip`, `Setup-2.0.0.exe` | có (fp32) | có (fp32) | IAA | không |
| **v2.0.1–v2.0.6** | 3 asset mỗi bản | có (fp16) | có (fp16) | IAA fp16 | không |
| **v2.2.0a** (CUDA, đang là pre-release) | `KiraPick-Setup-2.2.0a.exe`, `-1.bin`, `-2.bin`, `HUONG_DAN_CAI_DAT.txt` | có | có | **×3** | có |
| **v2.2.1** | `KiraPick-2.2.1-BoCai.zip`, `-portable.zip` | có | có | ×3 | có |
| **v3.0.0** (Latest) | `KiraPick-3.0.0-BoCai.zip`, `-portable.zip` | có | có | ×3 | có |
| **v3.0.0a** | `KiraPick-Setup-3.0.0a.exe`, `-1.bin`, `-2.bin`, `owner_backup.ps1`, `HUONG_DAN_CAI_DAT.txt` | có | có | ×3 | có |

**Tổng kết:**
- **15 release** chứa ít nhất một trọng số mức C: v0.3.0b1 tới v3.0.0a.
- **4 release** v0.2.0b1–b4 không có, nhưng vẫn **thiếu toàn văn giấy phép** và có DLL FFmpeg không ghi thông báo.
- Asset cần xử lý: mọi file `BoCai.zip`, `portable.zip`, `Setup*.exe` / `.bin` của 15 release.
- `HUONG_DAN_CAI_DAT.txt` và `owner_backup.ps1` không chứa trọng số.
- Repo git **không** chứa các trọng số này: chúng được tải lúc build. Chỉ có hai file MediaPipe nằm trong repo.

### 3.2 Đường cập nhật [Mã: `app/updates/app_update.py`]

- App đọc 30 release mới nhất. Mỗi bản chỉ nhận đúng loại tag của nó:
  - DirectML: `3.0.0`, bỏ pre-release;
  - CUDA: `3.0.0a`;
  - OpenVINO: `x.y.zb`.
- App bỏ release nháp, và bỏ release **không còn file cài** (không có `-BoCai.zip` hoặc `.exe` / `.bin`).
- **Hệ quả:**
  - Khi có v3.0.1 / v3.0.1a, mọi máy 3.0.0 / 3.0.0a và 2.2.x tự được mời lên 3.0.1. Tag beta `3.0.1b…` không khớp mẫu
    nên **không** bị mời.
  - Nếu **gỡ asset 3.0.0 trước khi có 3.0.1**, máy 2.2.x sẽ không được mời gì. Không hỏng, nhưng mất đường lên bản sạch.
    Vì vậy phải **đăng 3.0.1 trước, gỡ sau**.
  - Bản trước 2.2 không có trình cập nhật trong app; người dùng chỉ biết qua trang release.
  - Bản `portable.zip` không tự cập nhật; người dùng phải tải và giải nén lại.
- Bản đã tải về hoặc đã cài trên máy người khác **không thu hồi được**. Gỡ asset chỉ dừng phân phối tiếp. Bộ cài 3.0.1 xoá
  các file đó khi người dùng nâng cấp (mục 2.1).

### 3.3 Trình tự đề xuất (mỗi bước chờ chủ dự án duyệt)

Mình **không có quyền** sửa release trong phiên này (GitHub trả 403). Các bước 5 và 7 do chủ dự án tự bấm, hoặc cấp quyền
riêng.

| Bước | Việc | Ai | Điều kiện |
|---|---|---|---|
| 0 | Chủ dự án chọn LIC-4 (giữ / thay / thêm chế độ / xin phép) và MOD-3, LIC-6 | Chủ dự án | — |
| 1 | Làm mã chặn + đóng gói theo mục 1–2 trên `beta` | Mình | Bước 0 |
| 2 | Build thử nội bộ `3.0.1b1.devN` (không đăng release) | Mình (CI) | Test xanh |
| 3 | CI nghiệm thu N1–N7, U1–U9 trên Windows | Mình (CI) | Bước 2 |
| 4 | Chủ dự án tự cài thử, kiểm phiên cũ của mình | Chủ dự án | Bước 3 đạt |
| 5 | **Lệnh phát hành riêng:** tag + đăng v3.0.1 (Latest) và v3.0.1a, kèm giấy tờ đầy đủ | Chủ dự án duyệt | Bước 4 |
| 6 | Kiểm máy 3.0.0 / 3.0.0a được mời lên 3.0.1 (U9 với release thật) | Mình | Bước 5 |
| 7 | **Gỡ asset** của 15 release ở mục 3.1. Thêm một dòng vào ghi chú mỗi release: "Đã gỡ bộ cài vì chứa mô hình chỉ cho phép phi thương mại. Dùng 3.0.1 trở lên." Giữ tag và ghi chú để còn lịch sử | Chủ dự án | Bước 6 |
| 8 | Báo người thử beta riêng (nếu có) cập nhật lên 3.0.1 | Chủ dự án | Bước 5 |

**So sánh cách gỡ ở bước 7:**

| Cách | Hệ quả |
|---|---|
| **Xoá asset, giữ release và tag** (đề xuất) | Link tải cũ trả 404; lịch sử phiên bản còn đọc được; trình cập nhật bỏ qua release đó |
| Chuyển release về nháp | Ẩn cả trang release; tag vẫn còn trong git |
| Xoá release | Mất ghi chú; tag vẫn còn nếu không xoá riêng |

v0.2.0b1–b4: không bắt buộc gỡ vì không chứa trọng số mức C. Có thể gỡ cùng lúc cho gọn, vì vẫn thiếu toàn văn giấy phép.

---

## 4. Tiêu chí nghiệm thu bản 3.0.1

| # | Tiêu chí | Cách kiểm | Đạt khi |
|---|---|---|---|
| K1 | **Danh sách file bộ cài** so với danh sách cho phép | `inspect-release` (mở rộng) chạy trên artifact build, **trước** khi đăng: bộ cài DirectML, CUDA và `portable.zip` | N1–N3 đạt cho cả 3 gói; CI lỗi nếu lệch |
| K2 | **Log nạp mô hình trên Windows** | CI Windows chạy `--self-test` và một lần phân tích ảnh mẫu (ảnh tổng hợp / ảnh mẫu công khai, **không** dùng ảnh của chủ dự án), cả cài mới lẫn nâng cấp | Log chỉ có id + SHA-256 trong danh sách; có dòng "bỏ qua" cho file bị loại đặt lại bằng tay (U2) |
| K3 | **Giấy tờ giấy phép** | Kiểm cụm chữ đặc trưng của từng văn bản trong `{app}\docs\licenses\` | Có đủ mục 1.4; không còn dòng nào về mô hình bị loại trong NOTICES của bộ cài |
| K4 | **Bảo toàn dữ liệu** | U3–U8 tự động trên phiên dựng sẵn + chủ dự án kiểm phiên thật ở bước 4 | Không mất P/X, sao, ❤, nhóm tay, tên; ảnh gốc không đổi |
| K5 | **Chức năng còn chạy / bị giảm** (bảng dưới) | Test hiện có + kiểm tay | Chạy đúng; phần bị giảm hiện "chưa đánh giá" rõ ràng, **không** bịa số |
| K6 | Không mạng, cập nhật | Smoke test hiện có + U9 | Đạt |
| K7 | Bộ test đầy đủ | Linux + Windows CI | Xanh |

**Chức năng sau khi loại** (giả định MOD-3 = giữ mức B, LIC-6 = loại CLIP):

| Chức năng | 3.0.1 | Ghi chú |
|---|---|---|
| Nhập ảnh, lọc P/X, sao, so sánh, xuất, cập nhật | **chạy** | Không dùng mô hình |
| Dò người, dò mặt | **chạy** | YOLOX, YuNet |
| Gom người / trang phục | **giảm** | SFace + màu trang phục thay ArcFace + YoutuReID. Số lịch sử trên D1: gom đúng 0,808 so với 0,922 (có giới hạn so sánh). Quay lưng, che mặt, mặt nhỏ phải gom tay nhiều hơn |
| Gộp / tách tay, nhóm "khác nhau" | **chạy** | |
| Học nhận diện theo người dùng | **giảm** | Chỉ học từ SFace + màu |
| Chất lượng mặt | **chạy, giảm** | Còn eDifFIQA; mất TOPIQ-face |
| Nét ở mắt, sáng, bố cục | **chạy** | Mã của app |
| Mắt nhắm / mở | **chạy** nếu MOD-3 giữ MediaPipe; nếu không thì "chưa đánh giá" | |
| Điểm kỹ thuật tổng | **giảm** | Mất TOPIQ-KonIQ; dùng phép đo của app + eDifFIQA (Q-TECH) |
| Điểm thẩm mỹ | **mất** | Mất TOPIQ-IAA; mất CLIP + LAION nếu LIC-6 = loại |
| "Hợp gu" / học gu từ CLIP | **mất** nếu LIC-6 = loại | |
| Chọn ảnh thông minh (N ảnh, đa dạng dáng) | **chạy, giảm** | Xếp hạng chỉ dựa trên điểm kỹ thuật |
| Chế độ Media (Mốc 0) | **chạy** | Đã dùng `MediaRegistry` |

---

## 5. F-SF và Q-TECH đo được với thành phần nào

| Phép đo | Thành phần được nạp | Mức căn cứ | Ghi chú |
|---|---|---|---|
| **F-SF** (D1, 431 ảnh có nhãn) | YOLOX-S / -M, YuNet, SFace + màu trang phục (mã của app) | B (đo nội bộ: có) | Đo được ngay khi BM-0 = có. Chạy trên máy chủ dự án; ảnh không gửi đi |
| **Q-TECH** (D3, lịch sử P/X) | **Không nạp mô hình nào**. Chỉ đọc số đo đã lưu: nét, sáng, bố cục (app), eDifFIQA (A), mắt MediaPipe (B) | A + B | Phải đi qua cùng lớp chặn: **không đọc** cột TOPIQ đã lưu |
| **Q-TECH bỏ MediaPipe** | như trên, bỏ giá trị mắt | A | Cho biết mất bao nhiêu nếu MOD-3 loại MediaPipe |
| F-AU, Q-CL, F-SF+R | AuraFace / CLIP / YoutuReID | chờ BM-3, BM-4, BM-6, LIC-3 | Không làm trong 3.0.1 |

---

## 6. Quyết định cần chủ dự án chốt

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| **MOD-3** | Giữ nhóm **mức B** (YOLOX, YuNet, SFace, MediaPipe, LAION) trong cấu hình job có thu tiền và trong bộ cài 3.0.1, như **chấp nhận rủi ro** (chưa có thay thế đã xác minh)? | Giữ. Nếu không giữ thì app **không còn** dò người, gom người và kiểm mắt |
| **LIC-1** | Làm lớp chặn và test ở mục 2 cho cả hai chế độ? | Có |
| **LIC-2** | `inspect-release` thành bước bắt buộc **trước** khi đăng (K1, K3)? | Có |
| **LIC-3** | Liên hệ bên cấp quyền (InsightFace, tác giả TOPIQ, Tencent Youtu, Google về `.task`, Megvii về trọng số YOLOX) và đọc lại EULA NVIDIA? | Có, song song, không chặn 3.0.1 |
| **LIC-4** | Bản đang phân phối: (a) giữ / (b) thay asset theo mục 3.3 / (c) thêm chế độ thương mại nhưng vẫn phát file cũ / (d) chỉ xin phép | **(b)** |
| **LIC-5** | Bỏ DLL FFmpeg và TensorRT provider khỏi gói? | Có |
| **LIC-6** | CLIP + `clip_prompts` + LAION trong 3.0.1: loại khỏi bộ cài và cấu hình thương mại, hay giữ kèm ghi chấp nhận rủi ro? | **Loại** trong 3.0.1; xem lại khi có Q-CL và căn cứ |
| **REL-1** | 3.0.1 làm từ đâu: (i) từ tag `v3.0.0` (`e2fec9d`), chỉ có thay đổi giấy phép; hay (ii) từ `beta` hiện tại, có thêm màn chọn chế độ và Media Mốc 0 (chưa qua nghiệm thu của chủ dự án) | **(i)**: nhỏ, ít rủi ro. Sau đó đưa cùng thay đổi vào `beta` |
| **BM-0** | Cho chạy F-SF và Q-TECH (hai biến thể) trên máy chủ dự án? | Có |
