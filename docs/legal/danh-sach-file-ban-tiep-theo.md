# Danh sách file được bật, cấu hình bộ cài, file cũ dọn khi nâng cấp (bản trình 2, 2026-11-06)

> **Bản trình 2:** đã triển khai trên `beta` (C1, C12), theo kết luận review: CLEAN-1 là **danh sách file do bộ cài cũ quản lý** (không xoá cả thư mục), YoutuReID để `pending`, YOLOX-M chỉ ghim bản float16 (không có nhu cầu tương thích nào cần bản fp32). LIST-1, PKG-1, CLEAN-1 vẫn chờ chủ dự án duyệt riêng.

**Trạng thái:** đề xuất, trình riêng theo kết luận review "TRÌNH DUYỆT TRIỂN KHAI PHẦN NỀN TRÊN `beta`".
- **Chưa** có `configs/model-policy.json`, chưa sửa script build hay bộ cài.
- Số phiên bản: **chờ chốt** (VER-1).
- Căn cứ của từng file: `docs/legal/phuong-an-3.0.1.md`, Phụ lục B.

---

## 1. Danh sách cho phép (`configs/model-policy.json`, dự kiến)

**Quy tắc:**
- Chỉ file có trạng thái `verified` **và** đúng SHA-256 ghi dưới đây mới được mở.
- Mọi file khác bị từ chối:
  - `pending` / `never`;
  - mã băm khác (kể cả bản float16 của file khác);
  - file lạ trong thư mục.
- Mã băm được **ghim trong danh sách**. App **không còn** tin vào file `<tên>.sha256` đi kèm.
  - [Mã] Hiện `app/ai/models.py:97-103` chấp nhận mã băm ghi trong file `.sha256` cho file chuyển đổi lúc build. Người
    dùng sửa file đó là hợp thức hoá được một file bất kỳ.

### 1.1 `verified` (được bật)

| id | File | Byte | SHA-256 | Chế độ | Ghi chú |
|---|---|---|---|---|---|
| `person_detector_s` | `yolox_s.onnx` | 35 858 002 | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` | Cá nhân, Media | file gốc |
| `person_detector_m` | `yolox_m.onnx` | 50 705 453 | `be329495ec618a375a6b9bf04c155aea364863e4ef15e02561c9b062a8096aaf` | Cá nhân, Media | float16 của `21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f`. **Chỉ ghim bản float16** (bản fp32 không được mở: app dùng YOLOX-S) |
| `face_detector` | `face_detection_yunet_2023mar.onnx` | 232 589 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | Cá nhân, Media | file gốc |
| `face_quality` | `ediffiqa_tiny_jun2024.onnx` | 7 272 678 | `9426c899cc0f01665240cb7d9e7f98e18e24e456c178326c771a43da289bfc6a` | Cá nhân | file gốc |
| `face_mesh` | `mediapipe_face_landmarks_v2.onnx` | 4 921 000 | `a044fec26cd90125566eb8703258dd7a211cca60423801462663af8f13636f56` | Cá nhân | S9 **đạt** (C10, `scripts/convert_mediapipe.py --check`): chuyển lại từ `.task` `64184e22…c9ff` cho 257 trọng số bằng nhau, đầu ra trùng tuyệt đối trên 3 đầu vào (tf2onnx không cho file trùng từng byte) |
| `face_blendshapes` | `mediapipe_face_blendshapes_v2.onnx` | 1 883 551 | `ce56bc10f1b0306701b8bdb5cd05661a37a380f62638db7102bb61d6bc0d1a77` | Cá nhân | S9 đạt: 67 trọng số bằng nhau, đầu ra trùng tuyệt đối |

### 1.2 `pending` (chưa bật; chỉ đổi trạng thái khi có căn cứ)

| id | File | SHA-256 (bản 3.0.0) | Căn cứ còn thiếu |
|---|---|---|---|
| `face_embedder` | `face_recognition_sface_2021dec.onnx` | `f55a362e04742de60c22a70389d8495f1e5c695f59c8b086549482e999ad45c5` (float16 của `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`) | xác nhận của tác giả (R1) |
| `clip_l14_image` | `clip_l14_image.onnx` | `223bd17288a5d33f105209f45973e1f2455d14e97a8cf7bcdb2f453ee24e587c` | xác nhận của OpenAI (R2) |
| `clip_prompts` | `clip_prompts_v1.npz` | `cbe112ddff60fb3e5e9bf17c3422d6da9e9bc29fe16e9def785859f23607bd6d` | theo CLIP |
| `laion_aesthetic` | `laion_aesthetic.onnx` | `5a5e04813c758e18cad2d45c919096e5e552a422620022e48353598722614f53` | cần CLIP |
| `body_reid` | `person_reid_youtu_2021nov.onnx` | `16d61f9bf243d9bd4d38ac208f437c02273909518619a40c4c0b06505351dc55` | công bố của Tencent (R4); không đề xuất bật |

### 1.3 `never`

Mọi mã băm đều bị từ chối, theo id:

| id | File |
|---|---|
| `face_embedder_arcface` | `w600k_r50.onnx` |
| `aesthetic`, `tech_iqa`, `face_iqa` | `topiq_iaa_res50.onnx`, `topiq_nr_koniq_res50.onnx`, `topiq_nr_face_res50.onnx` |

YoutuReID (`body_reid`) để **`pending`** theo kết luận review (không đề xuất bật).

---

## 2. Cấu hình bộ cài

### 2.1 Mô hình đóng gói

| Gói | File trong `{app}\models` |
|---|---|
| DirectML, CUDA, portable | Đúng các file ở 1.1 (6 file nếu S9 đạt, 4 file nếu không). **Không** có file `.sha256` đi kèm (mã băm đã ghim) |
| Gói tối thiểu (nếu CFG-1 chọn) | không có thư mục `models` |

**Thay đổi build** (`scripts/build_windows.ps1`):
- Bỏ bước chép **mọi** `models\weights\*.onnx` (dòng 97-99): hiện có thể chép cả file lạ có trên máy build.
- `fetch_models.py` chỉ tải id `verified`.
- Bỏ các bước chuyển TOPIQ, CLIP + LAION (dòng 104-118).
- `shrink_models.py` chỉ chạy cho YOLOX-M, và kiểm kết quả trùng mã băm đã ghim.
- **Cổng build** (mở rộng `scripts/media_model_report.py` thành báo cáo cho cả danh sách): build **lỗi** nếu `dist\models`
  có file không phải `verified`, hoặc mã băm lệch.

### 2.2 Thư viện chạy kèm

| Thành phần | DirectML | CUDA | portable | Cách làm |
|---|---|---|---|---|
| `opencv_videoio_ffmpeg4140_64.dll` | **bỏ** | **bỏ** | **bỏ** | thêm vào `_UNUSED` trong `packaging/kirapick.spec` |
| `onnxruntime_providers_tensorrt.dll` | — | **bỏ** | — | như trên |
| Bản sao DLL NVIDIA trong `_internal\nvidia\…\bin\` | — | **bỏ** | — | lọc `a.binaries` theo tên; giữ một bản ở `_internal\` |
| `cudnn*64_9.dll` (10 file) | — | **theo LIC-7** | — | (a) không đăng gói CUDA; (b) bỏ khỏi gói, người dùng tự cài |
| `DirectML.dll` | giữ | — | giữ | — |
| Qt, ONNX Runtime, OpenCV, rawpy, Python | giữ | giữ | giữ | — |

### 2.3 Giấy tờ (`{app}\docs\licenses\`)

| File | Gói |
|---|---|
| `Apache-2.0.txt` (YOLOX, MediaPipe, OpenCV, ORT phần Apache), `MIT-YuNet.txt` + `BSD-3-libfacedetection.txt`, `CC-BY-4.0-eDifFIQA.txt` (ghi công) | mọi gói có AI |
| `LGPL-3.0.txt` + `GPL-3.0.txt` (Qt / PySide6), `LGPL-2.1.txt` (LibRaw), `PSF.txt`, `python-packages.txt` (sinh tự động), ORT `LICENSE` + `ThirdPartyNotices.txt` | mọi gói |
| `DirectML-LICENSE.txt` | DirectML, portable |
| `NVIDIA-CUDA-EULA.txt` (+ cuDNN SLA nếu có) | CUDA |
| `THIRD_PARTY_NOTICES.md`, `model-licenses.md`: viết lại; **xoá** các dòng về mô hình không có trong gói | mọi gói |

---

## 3. File cũ dọn khi nâng cấp (CLEAN-1, `[InstallDelete]` trong `packaging/installer.iss`)

**Nguồn:** `configs/clean-on-upgrade.json`, 26 đường dẫn chính xác, **không có ký tự đại diện**, không xoá thư mục.
Đây đúng là các file mà bộ cài v3.0.0 / v3.0.0a đã cài (kiểm kê run 42199575662) mà bản này không còn đóng gói:

| Thư mục | File |
|---|---|
| `models\` | `w600k_r50.onnx`, `person_reid_youtu_2021nov.onnx`, `topiq_iaa_res50.onnx`, `topiq_nr_koniq_res50.onnx`, `topiq_nr_face_res50.onnx`, `face_recognition_sface_2021dec.onnx`, `clip_l14_image.onnx`, `clip_prompts_v1.npz`, `laion_aesthetic.onnx`, và file `.sha256` đi kèm của 9 file đó + `yolox_m.onnx.sha256` |
| `_internal\cv2\` | `opencv_videoio_ffmpeg4140_64.dll` |
| `_internal\onnxruntime\capi\` | `onnxruntime_providers_tensorrt.dll` |
| `_internal\nvidia\…\bin\` | bản trùng: `cublas64_12.dll`, `cublasLt64_12.dll`, `cudnn_graph64_9.dll`, `cudnn_ops64_9.dll`, `cufft64_11.dll` |

**Không bị đụng:**
- file người dùng tự đặt vào thư mục cài (vì chỉ xoá đúng tên);
- dữ liệu ở `%LOCALAPPDATA%\KiraPick`;
- ảnh gốc.

Ca test (Linux, mô phỏng đúng cách Inno Setup xoá từng tên) trên bản sao thư mục 3.0.0 có thêm file lạ: file cũ bị xoá,
file lạ còn nguyên (`tests/unit/test_packaging.py`). Ca nâng cấp **trên bộ cài thật** (P8) cần build nội bộ (BUILD-1).

**Không dọn được:**
- bản cài của AppId khác (kênh beta, nội bộ, bản cũ tên `Snorlu-AI-Culling`);
- bản portable;
- bản sao người dùng tự chép.

App vẫn chặn các file đó theo danh sách cho phép.

## 4. Cần duyệt

| Mã | Nội dung |
|---|---|
| LIST-1 | Danh sách 1.1–1.3 |
| PKG-1 | Cấu hình bộ cài 2.1–2.3 |
| CLEAN-1 | Dọn `{app}\models` và `{app}\_internal` khi nâng cấp (mục 3) |
