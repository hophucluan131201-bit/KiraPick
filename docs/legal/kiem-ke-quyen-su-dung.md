# Kiểm kê thành phần và quyền sử dụng (bản 2, 2026-11-06)

- **Phạm vi:** kiểm chứng và trình phương án.
  - Không đổi mã chạy, không đổi mặc định, không đóng gói, không chạy benchmark.
  - Sửa mã, thay mặc định và xử lý bản đang phân phối đều trình chủ dự án duyệt riêng.
- **Mình không phải luật sư.**
  - "Có căn cứ" nghĩa là có điều khoản hoặc văn bản của bên cấp quyền.
  - Xác nhận của chủ dự án chỉ duyệt việc **triển khai trong dự án**, không tạo ra quyền sử dụng.
- **Ký hiệu nguồn bằng chứng:**
  - **[Mã]:** đọc mã ở commit đã ghi.
  - **[Bộ cài]:** kiểm trực tiếp bộ cài đã phát hành (mục 2).
  - **[Log]:** log chạy trên Windows.
  - **[Điều khoản]:** văn bản giấy phép / model card gốc.
  - **[Script]:** suy từ script build, chưa kiểm trên bộ cài.

## 1. Đối tượng kiểm tra

| Đối tượng | SHA đầy đủ |
|---|---|
| Tag `v3.0.0` (DirectML) | `e2fec9d769d8eb26f9772cd5f5bd0bf04adab4a2` |
| Tag `v3.0.0a` (CUDA) | `e2fec9d769d8eb26f9772cd5f5bd0bf04adab4a2` (cùng commit) |
| `beta` khi viết bản 1 | `d19b9c342a7ec504b21509ba4235c4dc7b50fe5e` |
| `beta` khi kiểm bộ cài (job kiểm tra) | `c431f29d2f32e87ea884a271edddab8f0351b562` |
| `main` | `c8fcf9ed334ce8b315bef0f8c5f81b23262a3650` |

**Phạm vi câu "giống hệt" ở bản 1** (`git diff e2fec9d d19b9c3`):
- **Giống nhau:**
  - các thư mục `app/ai`, `app/workers`, `app/identity`, `app/quality`;
  - `configs/model-manifest.json`;
  - `scripts/build_windows.ps1`, `scripts/fetch_models.py`, `scripts/shrink_models.py`.
- **`beta` có thêm, bản 3.0.0 không có:**
  - **màn hình chọn chế độ**: `app/ui/mode_picker.py`, `app_shell.py`, `media_home.py`, và 2 ảnh trong
    `packaging/kirapick.spec`;
  - **lớp chặn Media**: `app/media/models.py` (`MediaRegistry`), `configs/media-models.json`,
    `scripts/media_model_report.py`;
  - **job kiểm tra bộ cài** trong `.github/workflows/build-windows.yml`;
  - tài liệu.
- Như vậy luồng **Chụp cá nhân** và các mô hình **giống nhau** giữa 3.0.0 và `beta`. Luồng **Media** chỉ có trên `beta`.

## 2. Kiểm trực tiếp hai bộ cài đã phát hành [Bộ cài]

**Cách kiểm:**
- CI job `inspect-release`, run **42199575662**, chạy trên mã `beta` commit `c431f29`.
- Tải asset của release; so SHA-256 với digest của GitHub.
- **Cài silent** trên máy CI dùng xong là bỏ, rồi liệt kê **mọi file đã cài**, kèm SHA-256.
- **Không chạy `KiraPick.exe`**, nên không mô hình nào được nạp.

**Asset đã phát hành** (mọi asset đều khớp digest của GitHub):

| Release | Asset | Byte | SHA-256 |
|---|---|---|---|
| v3.0.0 | `KiraPick-3.0.0-BoCai.zip` | 1 145 855 229 | `9c1e8678ed1eaffdfba4ca56e25e9b5ceda9e1a0880001c8e58d3a3dc0d2e92a` |
| v3.0.0 | `KiraPick-3.0.0-portable.zip` | 1 206 122 458 | `ba5833c396e198c28d1158d1de1aa97a6ea57e987802b1ac601acfd8c48c5d79` |
| v3.0.0a | `KiraPick-Setup-3.0.0a.exe` | 2 123 057 | `59dd2734984f7d748502d6e332e7203b2954d11466f782617fbefa854d6c94c9` |
| v3.0.0a | `KiraPick-Setup-3.0.0a-1.bin` | 1 797 876 736 | `4542bea179df002798474b58401234d7bc7a938c604e1003d28a2eaffb4e45c6` |
| v3.0.0a | `KiraPick-Setup-3.0.0a-2.bin` | 1 314 386 504 | `cdc39fee7aa0241ae93a7a4692003f471cb2de69e40fcbd9fb3a1b7d20b4249f` |
| v3.0.0a | `owner_backup.ps1`, `HUONG_DAN_CAI_DAT.txt` | 6 265 / 6 291 | `67dc1097…f51` / `298697d8…bc9` |

**Trọng số đã cài.** Hai bản DirectML và CUDA giống hệt nhau: 15 file mô hình, SHA-256 trùng từng file.

| File | Byte | SHA-256 file đã cài | Ghi chú (file `.sha256` đi kèm) |
|---|---|---|---|
| `w600k_r50.onnx` (**ArcFace**) | 87 294 184 | `761eefe54163826056724d073554d3db4db8ba8631b1d0e991b483c7735df5c3` | float16 của file gốc `4c06341c…9e43` |
| `person_reid_youtu_2021nov.onnx` (**YoutuReID**) | 53 568 625 | `16d61f9bf243d9bd4d38ac208f437c02273909518619a40c4c0b06505351dc55` | float16 của `05796833…580d` |
| `topiq_iaa_res50.onnx` (**TOPIQ**) | 140 617 320 | `3b7ebfd805796e73d0b0af29d3816c86e8965d4acccf84ffaed4fd5ffaf7b3e4` | float16 của ONNX `9ee44c6d…9233` (chuyển từ `cfanet_iaa_ava_res50-3cd62bb3.pth`) |
| `topiq_nr_koniq_res50.onnx` (**TOPIQ**) | 90 006 430 | `240a406808fe0c0b61d066c2a7bab2a3458f6960d76e05cb514ef09523a2148f` | float16 của `4114729d…ff7d` |
| `topiq_nr_face_res50.onnx` (**TOPIQ**) | 89 992 299 | `4394bd18382ad47fe9193e2d10445cb3cc03b58cfb3d847946363218ee5440f1` | float16 của `b5798716…c8ad` |
| `clip_l14_image.onnx` (CLIP) | 610 037 113 | `223bd17288a5d33f105209f45973e1f2455d14e97a8cf7bcdb2f453ee24e587c` | float16 của ONNX `452e2306…158d` (chuyển từ `ViT-L-14.pt b8cca3fd…3836`) |
| `clip_prompts_v1.npz` | 143 018 | `cbe112ddff60fb3e5e9bf17c3422d6da9e9bc29fe16e9def785859f23607bd6d` | tính lúc build |
| `laion_aesthetic.onnx` | 3 721 267 | `5a5e04813c758e18cad2d45c919096e5e552a422620022e48353598722614f53` | chuyển từ `sac+logos+ava1-l14-linearMSE.pth 21dd590f…f1e0` |
| `face_recognition_sface_2021dec.onnx` | 19 448 517 | `f55a362e04742de60c22a70389d8495f1e5c695f59c8b086549482e999ad45c5` | float16 của `0ba9fbfa…79` |
| `face_detection_yunet_2023mar.onnx` | 232 589 | `8f2383e4…52fa4` | đúng file gốc |
| `yolox_s.onnx` | 35 858 002 | `c5c2d13e…8063` | đúng file gốc |
| `yolox_m.onnx` | 50 705 453 | `be329495ec618a375a6b9bf04c155aea364863e4ef15e02561c9b062a8096aaf` | float16 của `21ff6cfd…b3f` |
| `ediffiqa_tiny_jun2024.onnx` | 7 272 678 | `9426c899…fc6a` | đúng file gốc |
| `mediapipe_face_landmarks_v2.onnx` | 4 921 000 | `a044fec2…f56` | chuyển đổi, lưu trong repo |
| `mediapipe_face_blendshapes_v2.onnx` | 1 883 551 | `ce56bc10…d77` | chuyển đổi, lưu trong repo |

**Thư viện runtime đã cài** (lọc theo tên):
- **Cả hai bản:**
  - Qt6 Core / Gui / Widgets / Svg / **Network**;
  - `onnxruntime.dll`;
  - **`opencv_videoio_ffmpeg4140_64.dll` (FFmpeg)**.
- **Chỉ DirectML:** `DirectML.dll`.
- **Chỉ CUDA:**
  - `onnxruntime_providers_cuda.dll` và **`onnxruntime_providers_tensorrt.dll`**;
  - cuBLAS / cuBLASLt / cuFFT / cuRAND / NVRTC / cudart / cuDNN 9;
  - một số DLL NVIDIA có **hai bản sao**, ở `_internal\` và `_internal\nvidia\…\bin\`.

**Giấy tờ đã cài** (`{app}\docs`): `HUONG_DAN_CAI_DAT.txt`, `HUONG_DAN.txt`, `LICENSE.md`, `LICENSES.txt`,
`model-licenses.md`, `RELEASE_NOTES.md`, `THIRD_PARTY_NOTICES.md`.
- **Không file nào chứa toàn văn** Apache-2.0, LGPL-3.0, LGPL-2.1 hoặc CC BY 4.0 (kiểm bằng cụm chữ đặc trưng của từng
  văn bản).
- Có nhắc PolyForm và InsightFace (các dòng thông báo).

**Chưa kiểm:**
- **Nội dung `KiraPick-3.0.0-portable.zip`**: job chỉ cài từ `BoCai.zip`. Theo [Script], file này nén cùng thư mục
  `dist\KiraPick`; cần kiểm riêng.
- **Mô hình nào được nạp theo từng luồng trên Windows [Log]**: **chưa kiểm**.
  - Chạy thử bộ cài 3.0.0 sẽ nạp ArcFace / TOPIQ. Việc chạy chúng cho mục đích đo của một dịch vụ có thu tiền **chưa có
    căn cứ** (mục 4).
  - Danh sách "nạp khi chạy" ở mục 3 vì vậy là **[Mã]**.
- **Các release cũ** (v0.3.0b1 tới v2.2.1, v2.2.0a): **chưa kiểm bộ cài**.
  - Theo lịch sử repo, TOPIQ có từ 0.3.0b1, ArcFace + YoutuReID từ 0.3.0b2. Nên khả năng cao các bản này cũng chứa
    chúng [Script].

## 3. Bảng 1: bản 3.0.0 đã phát hành

### 3.1 Nạp khi chạy (luồng Chụp cá nhân) [Mã: `e2fec9d`]

| Bước | Trọng số | Điều kiện | Dự phòng | Dữ liệu lưu lại |
|---|---|---|---|---|
| Dò người | YOLOX-S; YOLOX-M nếu GPU nhanh hơn | luôn có | M → S | khung người |
| Dò mặt | YuNet | luôn có | — | — |
| Nhận mặt | SFace | luôn có | — | vector `face` |
| **Nhận mặt + dáng người** | **ArcFace + YoutuReID** | **tự nạp khi cả hai file có mặt** (`embed_job.py:53`); bộ cài có cả hai [Bộ cài] | thiếu → SFace + màu trang phục | vector `face_arc`, `body`; giá trị trong `learning.db` |
| Chọn cách gom | — | **theo vector `face_arc` đã lưu trong phiên** (`cluster.py:153`) | — | phiên cũ vẫn gom bằng vector ArcFace |
| Chất lượng mặt | eDifFIQA | nếu có | "chưa đánh giá" | `measurements` |
| Mắt | MediaPipe | nếu có | "chưa đánh giá" | `measurements` |
| **Thẩm mỹ, kỹ thuật** | **TOPIQ ×3** | nếu có; bộ cài có cả ba [Bộ cài] | "chưa đánh giá" | `aesthetic_mos`, `tech_iqa`, `face_iqa`, được **đọc lại khi tính điểm** (`score.py:91-98`) |
| CLIP / LAION / gu | CLIP + LAION + `clip_prompts` | nếu có | bỏ | vector `clip`; CLIP trong `learning.db` |
| `--self-test` | **mọi mô hình có mặt** | — | — | — |

### 3.2 Kết luận cho 3.0.0

| Câu hỏi | Kết luận | Bằng chứng |
|---|---|---|
| Luồng Chụp cá nhân dùng được cho job có thu tiền? | **Không có căn cứ**: tự nạp ArcFace + YoutuReID và TOPIQ | [Mã] `embed_job.py:53`, `quality_job.py:195`; [Bộ cài] có đủ 5 file; [Điều khoản] ArcFace "non-commercial research purposes only", TOPIQ PolyForm Noncommercial |
| Gỡ file ArcFace / TOPIQ có đủ không? | **Không**: phiên cũ vẫn dùng vector và điểm đã lưu | [Mã] `cluster.py:153`, `score.py:91-98` |
| Luồng Media | Không có trong 3.0.0 | [Mã] |
| Bộ cài phân phối trọng số chỉ cho phép phi thương mại? | **Có**: ArcFace và TOPIQ ×3 nằm trong cả hai bộ cài công khai | [Bộ cài] mục 2 |
| Giấy tờ đi kèm đủ chưa? | **Thiếu toàn văn** Apache-2.0, LGPL-3.0 / 2.1, CC BY 4.0. **Chưa ghi FFmpeg** (`opencv_videoio_ffmpeg`) trong THIRD_PARTY_NOTICES | [Bộ cài] mục 2; [Điều khoản] Apache-2.0 §4(a), LGPL, CC BY 4.0 §3 |

## 4. Ba trạng thái quyền cho từng thành phần [Điều khoản]

| Thành phần | Đo nội bộ | Job có thu tiền | Phân phối | Nghĩa vụ |
|---|---|---|---|---|
| YuNet | có (MIT) | có theo giấy phép trọng số; dữ liệu WIDER FACE **chưa xác minh** | có (MIT) | thông báo MIT |
| SFace | có (Apache-2.0) | như trên; dữ liệu **chưa xác minh** | có | toàn văn Apache-2.0; ghi rõ đã đổi sang float16 |
| YOLOX-S / -M | có (LICENSE Apache-2.0 của repo) | **căn cứ chưa đầy đủ** (mức B, xem `phuong-an-3.0.1.md` mục 1.1): LICENSE nằm ở repo mã; phạm vi với trọng số **chưa xác minh** | như cột trước | toàn văn Apache-2.0; ghi rõ float16 (M) |
| eDifFIQA | có (CC BY 4.0) | có | có | ghi công + đường dẫn giấy phép (đã có ghi công) |
| MediaPipe mesh / blendshapes | có (model card Apache-2.0) | **chưa xác minh** (giấy phép của file `.task`) | **chưa xác minh** | ghi rõ đã chuyển sang ONNX |
| **ArcFace** | **chưa xác minh** | **không có căn cứ** | **không có căn cứ** cho người dùng thương mại | — |
| **YoutuReID** | **chưa xác minh** | **chưa xác minh** | **chưa xác minh** | — |
| **TOPIQ ×3** | **chưa xác minh** (PolyForm chỉ cho nghiên cứu "không nhằm ứng dụng thương mại") | **không có căn cứ** | không có căn cứ cho người dùng thương mại | thông báo bản quyền |
| CLIP | có (mã MIT) | **chưa xác minh** (model card: triển khai "ngoài phạm vi"). Việc chủ dự án chấp nhận rủi ro **không phải** căn cứ quyền | như cột trước | thông báo MIT |
| LAION head | có (Apache-2.0) | có theo giấy phép trọng số; dữ liệu **chưa xác minh** | có | toàn văn Apache-2.0 |
| Qt 6 / PySide6 | có | có | có, kèm **nghĩa vụ LGPL-3.0**: toàn văn, DLL thay được, chỉ nguồn | **thiếu toàn văn** |
| LibRaw (trong rawpy) | có | có | có, kèm LGPL-2.1 / CDDL | thiếu toàn văn |
| **FFmpeg** (`opencv_videoio_ffmpeg`) | có | có | có, kèm nghĩa vụ LGPL-2.1 | **chưa ghi trong NOTICES**; app không dùng video, có thể bỏ DLL này khi đóng gói |
| ONNX Runtime | có | có | có | thông báo MIT |
| ORT TensorRT provider (CUDA) | có | có | có (MIT) | không kèm TensorRT; không dùng |
| DirectML.dll | có | có | có (điều khoản tái phân phối của Microsoft) | theo điều khoản |
| DLL NVIDIA CUDA / cuDNN | có | có | **cần đọc lại EULA** của đúng phiên bản (CUDA 12, cuDNN 9) | theo EULA |

## 5. Bảng 2: cấu hình đề xuất cho job có thu tiền trên `beta` (chưa làm)

| Phần | Thành phần | Đo nội bộ | Job có thu tiền | Đóng gói | Ảnh hưởng |
|---|---|---|---|---|---|
| Dò người / mặt | YOLOX-S / -M, YuNet | có | có theo giấy phép trọng số (dữ liệu chưa xác minh) | có | không đổi |
| Nhận mặt | **SFace** | có | như trên | có | gom kém hơn ArcFace (số lịch sử 0,808 so với 0,922, có giới hạn so sánh) |
| Nhận mặt (ứng viên) | AuraFace, **chỉ file nhận mặt** | chờ tải và kiểm file thật | chờ | chờ | — |
| Dáng người | **không dùng YoutuReID** | — | — | — | quay lưng / che mặt / mặt nhỏ cần gom tay nhiều hơn |
| Chấm điểm | **Q-TECH**: nét ở mắt, sáng, bố cục (mã của app) + eDifFIQA | có | có | có | mất điểm TOPIQ |
| Mắt nhắm / mở | MediaPipe | có | **chưa xác minh** | **chưa xác minh** | nếu chưa xác minh: "chưa đánh giá" trong cấu hình thương mại |
| Thẩm mỹ CLIP + LAION, gu | CLIP, LAION | có | **chưa xác minh** (CLIP) | chưa xác minh | không có: mất điểm thẩm mỹ CLIP và "Hợp gu" |

**Chặn trong cấu hình thương mại** (đề xuất, LIC-1):
1. **Lớp chặn chung** (mở rộng `MediaRegistry` thành chặn theo cấu hình). Mọi chỗ gọi `require` / `ready` đi qua lớp này:
   - `detect.py`, `face_quality.py`, `eyes.py`;
   - `quality_job.load_extras`, `embed_job.available`;
   - `selftest`, và chỗ đọc `clip_prompts` trong `main_window.py`.
2. **Bọc các hàm mở file mô hình** trong test: `create_session`, `cv2.dnn.readNet*`, `FaceRecognizerSF.create`.
   - Test chạy cấu hình thương mại trên thư mục `models\` có **đủ cả 15 file**.
   - Khẳng định chỉ các file được phép bị mở: đường chạy thường, dự phòng GPU → CPU, YOLOX-M → S, và khi thiếu file.
3. **`--self-test --commercial`:** ghi mọi file đã mở kèm SHA-256 (báo cáo A). CI lỗi nếu có file ngoài danh sách.
4. **Cache phiên:**
   - cấu hình thương mại **không đọc** vector `face_arc` / `body` và giá trị `aesthetic_mos` / `tech_iqa` / `face_iqa`;
   - `session_profile` trả SFace (hoặc mô hình thay thế) **bất kể** phiên có vector ArcFace.
   - **Không xoá** dữ liệu cũ.
5. **`learning.db`:** chỉ học từ SFace và màu trang phục; bỏ qua cột `face_arc`, `body`. Không xoá cột.
6. **Bảo toàn dữ liệu** (test bắt buộc), trên một phiên 3.0.0 có sẵn ArcFace và TOPIQ, mở bằng cấu hình thương mại:
   - **P/X, sao, ❤** giữ nguyên;
   - **nhóm đã chỉnh tay** (gộp, tách, "khác nhau", tên) giữ nguyên, vì `subjects` / `occurrences` không bị gom lại khi
     chỉ mở phiên;
   - **ảnh gốc** không đổi (so SHA-256 trước và sau);
   - mở lại bằng cấu hình cũ: mọi dữ liệu cũ còn nguyên.

**Bản phân phối** (đề xuất, LIC-2):
- Giữ job `inspect-release` (đã chạy được). Thêm:
  - kiểm `portable.zip`;
  - đối chiếu từng file mô hình với danh sách cho phép của cấu hình đóng gói;
  - kiểm toàn văn giấy phép bắt buộc;
  - lỗi nếu thiếu.
- Chạy cùng loại kiểm tra trên mọi bộ cài mới **trước** khi đăng release.

## 6. Phương án khắc phục bản đang phân phối (trình riêng, LIC-4)

**Asset bị ảnh hưởng** (có ArcFace + TOPIQ):
- **v3.0.0:** `KiraPick-3.0.0-BoCai.zip` [Bộ cài], `KiraPick-3.0.0-portable.zip` [Script; chưa kiểm].
- **v3.0.0a:** `KiraPick-Setup-3.0.0a.exe` cùng `-1.bin`, `-2.bin` [Bộ cài].
- **Có khả năng bị ảnh hưởng, chưa kiểm:** v2.2.1, v2.2.0a, v2.0.0–v2.0.6, v0.3.0b1–b4 [Script / lịch sử repo].

**Đường cập nhật:**
- `app/updates/app_update.py` đọc danh sách release công khai.
- Người dùng 2.2.x bấm "Cập nhật KiraPick" sẽ được mời tải v3.0.0 / v3.0.0a, tức là đang được dẫn tới đúng các asset trên.

**Các phương án (chủ dự án chọn):**

| Phương án | Làm gì | Ảnh hưởng |
|---|---|---|
| (a) Giữ nguyên | Không đổi gì | Tiếp tục phân phối trọng số chỉ cho phép phi thương mại |
| (b) Thay asset | Phát hành **3.0.1** không chứa ArcFace / YoutuReID / TOPIQ (cấu hình mục 5), kèm đủ giấy tờ; **gỡ asset** của v3.0.0 / v3.0.0a (và bản cũ nếu kiểm thấy cùng vấn đề) hoặc đặt về nháp | Người dùng mất ArcFace / TOPIQ; cập nhật trỏ sang 3.0.1. Gỡ release là thao tác ra ngoài, cần lệnh riêng |
| (c) Giữ bộ cài, thêm chế độ thương mại | Bộ cài vẫn chứa các file đó; chế độ thương mại không nạp chúng | **Không giải quyết quyền phân phối**: phân phối được kiểm độc lập với việc có nạp hay không |
| (d) Xin giấy phép | Liên hệ InsightFace, tác giả TOPIQ, Tencent Youtu | Tuỳ kết quả |

## 7. Đầu vào benchmark

| Phép đo | Thành phần nạp | Căn cứ đo nội bộ | Chỉ số đo được | Còn chờ |
|---|---|---|---|---|
| **F-SF** (D1) | YOLOX-S/M, YuNet, SFace; màu trang phục (mã của app) | có | độ chính xác, độ phủ, gộp nhầm, tách nhầm, chưa gom được, thời gian; theo nhóm Q / C / N / R | nhãn Q / C / N / R; chạy trên máy chủ dự án; log thời gian 3.0.0 |
| **Q-TECH** (D3) | **không nạp mô hình**: tính lại từ số đo đã lưu (nét, sáng, bố cục, mắt, eDifFIQA) | có (chỉ đọc dữ liệu) | tỉ lệ ảnh đầu loạt trùng **P**, tương quan thứ hạng, ca sai đáng chú ý | chạy trên máy chủ dự án |
| **Q-TECH không có MediaPipe** | như trên, bỏ giá trị mắt | có | như trên; cho biết mất bao nhiêu nếu MediaPipe không được xác minh cho job | — |
| F-AU | + AuraFace (chỉ file nhận mặt) | chờ tải và kiểm | — | BM-4 |
| F-SF+R, F-AU+R | + YoutuReID | chưa xác minh | — | BM-6, LIC-3 |
| Q-CL | + CLIP, LAION | có cho đo; job chưa xác minh | — | BM-3 |
| Chạy lại ArcFace / TOPIQ | — | chưa xác minh | — | BM-1 (đề xuất không) |

## 8. Quyết định cần chủ dự án chốt

| Mã | Câu hỏi |
|---|---|
| **LIC-1** | Làm "cấu hình thương mại" với các lớp chặn và test ở mục 5 (đường chạy thường, dự phòng, `--self-test`, cache phiên, `learning.db`, bảo toàn dữ liệu)? |
| **LIC-2** | Giữ và mở rộng job `inspect-release` thành bước kiểm bắt buộc trước khi đăng release (gồm `portable.zip`, danh sách cho phép, toàn văn giấy phép)? |
| **LIC-3** | Liên hệ bên cấp quyền: InsightFace, tác giả TOPIQ, Tencent Youtu, Google (file `.task` của MediaPipe), và đọc lại EULA NVIDIA? |
| **LIC-4** | Bản đang phân phối: (a) / (b) / (c) / (d) ở mục 6? |
| **BM-0** | Cho chạy F-SF và Q-TECH (hai biến thể) trên máy chủ dự án? |
