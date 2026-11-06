# Phương án 3.0.1 và tiêu chí nghiệm thu (bản trình 2, 2026-11-06)

**Trạng thái:** chỉ là phương án. **Chưa sửa mã ứng dụng, chưa build bộ cài, chưa đổi mặc định, chưa đụng tới release nào
trên GitHub.**

- Mọi thao tác dưới đây cần chủ dự án duyệt riêng: phạm vi sửa mã, phát hành, thay hoặc gỡ asset.
- Xác nhận của chủ dự án chỉ duyệt việc triển khai. **Quyền sử dụng** dựa trên điều khoản hoặc bên cấp quyền.
- **Nền đề xuất:** làm từ tag `v3.0.0` (`e2fec9d`), sau đó đưa cùng phần sửa vào `beta` (REL-1, mục 7).

**Thay đổi so với bản trình 1:**
- Bỏ MOD-3 (quyết định chung cho cả nhóm). Thay bằng **quyết định theo từng file** (mục 1).
- Thêm **hai cấu hình** (mục 2), mỗi cấu hình có tiêu chí nghiệm thu riêng (mục 5).
- Danh sách asset theo tag, tên, SHA-256 và run xác minh (Phụ lục A). Tách **hai mốc**: dừng cung cấp, và mở đường cập nhật
  (mục 4).
- Nghiệm thu theo từng gói DirectML / CUDA / portable. Tách **CI** khỏi **ca chủ dự án chạy** (mục 5).

**Nguồn bằng chứng:**

| Ký hiệu | Nghĩa |
|---|---|
| **[Bộ cài]** | Job CI `inspect-release`: tải asset, so digest GitHub, cài silent trên máy CI dùng xong là bỏ, liệt kê file + SHA-256. **Không chạy app.** Các run: **42199575662** (v3.0.0, v3.0.0a), **42208112442** (18 tag, gồm `portable.zip`), **42245312724** và **42245711312** (so bộ cài lẻ với bộ cài trong `BoCai.zip`) |
| **[Nguồn]** | Đọc trực tiếp nơi công bố, ngày 2026-11-06: opencv_zoo commit `48b10fa5` (file LICENSE từng thư mục, lịch sử commit, mã băm LFS); repo gốc của từng mô hình; model card Hugging Face; model card PDF của MediaPipe; file giấy phép trong gói NVIDIA và Microsoft |
| **[Mã]** | Đọc mã ứng dụng |

---

## 1. Quyết định theo từng file

### 1.1 Cách xét

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

### 1.2 Trọng số mô hình

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

### 1.3 Thư viện chạy kèm, theo gói

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

---

## 2. Hai cấu hình

| | **Cấu hình tối thiểu (T)** | **Cấu hình AI (A)** |
|---|---|---|
| Mô hình kèm theo | **không có** | `yolox_s`, `yolox_m`, `yunet`, `ediffiqa`, `mediapipe` ×2 (6 file "Giữ" ở mục 1.2) |
| Runtime | Qt, rawpy, OpenCV (không FFmpeg), Python. **Không cần** ONNX Runtime / DirectML / CUDA | + ONNX Runtime; DirectML (gói DirectML, portable) hoặc CUDA (gói CUDA, xem LIC-7) |
| Gói | Một gói chung cho mọi máy | DirectML, CUDA, portable |
| Nhập ảnh, RAW + JPEG, xem lưới / ảnh lớn, P/X, sao, ❤, so sánh, tìm tên file, nhập danh sách khách, xuất bản sao, cập nhật | **chạy** | **chạy** |
| Dò người | không | **chạy** (YOLOX-S; M khi GPU nhanh hơn) |
| Dò mặt | không | **chạy** (YuNet) |
| **Gom nhóm người tự động** | không | **không có trong 3.0.1**. Điều kiện để có: một mô hình nhận mặt **đủ căn cứ** (SFace có xác nhận của tác giả; hoặc AuraFace có xác nhận nguồn gốc; hoặc dlib sau khi kiểm), **và** benchmark F-* đạt |
| Chấm kỹ thuật: nét ở mắt (ảnh gốc), sáng, bố cục, chất lượng mặt | không | **chạy**. Cần YuNet (vị trí mắt), YOLOX (khung người), eDifFIQA |
| Kiểm mắt nhắm / mở | không | **chạy**. Cần YuNet + MediaPipe ×2 (sau khi khớp mã băm chuyển đổi) |
| Điểm thẩm mỹ, "Hợp gu" | không | **không có** (TOPIQ loại; CLIP chờ) |
| Chọn ảnh tự động | không | **chỉ theo ảnh**, xếp theo điểm kỹ thuật. Chọn theo **từng người** cần gom nhóm, nên chưa có |

**Phần mã cần sửa cho cấu hình A** (phạm vi sửa mã, chờ duyệt):
- [Mã] Hiện nay bước phân tích chỉ chạy khi nhóm `identity` sẵn sàng (`main_window.py:1211` `ready("identity")`). Nhóm này
  gồm cả `face_embedder` (SFace).
- Phải tách thành hai nhóm:
  - **dò** (YOLOX, YuNet): bắt buộc cho cấu hình A;
  - **nhận mặt**: tuỳ chọn. Khi thiếu, app không gom nhóm và hiện "chưa có trong bản này".
- Cấu hình T: app đã có đường "chưa có mô hình". Cần kiểm lại để mọi màn hình đều nói rõ "bản này không có AI", không lỗi,
  không bịa số.

**Dữ liệu cũ của 3.0.0** (áp dụng cho cả T và A, quyết định DATA-1):
- Nhóm người trong phiên cũ được gom bằng **ArcFace + YoutuReID**, tức là kết quả của mô hình bị loại.
- Đề xuất:
  - **nhóm tự động chưa được người dùng chỉnh**: ẩn trong cấu hình mới, không xoá khỏi DB;
  - **nhóm người dùng đã gộp / tách / đặt tên**: giữ và hiện, vì đó là quyết định của người dùng.
- Chủ dự án chọn.

---

## 3. Chặn (cả hai chế độ, cả hai cấu hình)

Không đổi so với bản trình 1, chỉ nêu lại các điểm chính:
- **Một danh sách cho phép theo SHA-256**, dùng chung cho Chụp cá nhân và Media. Cấu hình T có danh sách rỗng. Đổi tên
  file hoặc trỏ `KIRAPICK_MODELS_DIR` sang chỗ khác vẫn bị chặn.
- Các đường đều đi qua cùng một cửa kiểm:
  - chạy thường;
  - dự phòng GPU → CPU, YOLOX-M → S, thiếu file;
  - `--self-test`;
  - đọc `clip_prompts`.
- **Báo cáo A** ghi từng file đã mở: id, SHA-256, provider. Ghi cả file **bị bỏ qua**.
- **Cache phiên:**
  - không đọc vector `face_arc`, `body`, `clip`;
  - không đọc điểm `aesthetic_mos`, `tech_iqa`, `face_iqa` (TOPIQ);
  - nhóm tự động cũ xử lý theo DATA-1;
  - **không xoá** dữ liệu.
- **`learning.db`:** không đọc và không ghi các cột trên; không xoá cột. Cấu hình A không học nhận diện, vì chưa có mô hình
  nhận mặt.
- **Bộ cài nâng cấp** xoá các file mô hình không có trong danh sách khỏi `{app}\models` (`[InstallDelete]`). Đây là file
  của app, không phải ảnh hay dữ liệu người dùng. Mã vẫn chặn nếu file còn sót hoặc được chép lại.

---

## 4. Bản đã phát hành: asset và hai mốc xử lý

### 4.1 Đối chiếu số release

| Nguồn | Số release |
|---|---|
| GitHub (gọi API ngày 2026-11-06) | **19**: v0.2.0b1–b4, v0.3.0b1–b4, v2.0.0–v2.0.6, v2.2.0a, v2.2.1, v3.0.0, v3.0.0a |
| Run 42208112442 | 18 (mọi tag trừ v3.0.0a) |
| Run 42199575662 | 2 (v3.0.0, v3.0.0a) |
| Gộp hai run | **19 tag**, mỗi tag ít nhất một run. v3.0.0 có trong cả hai run, mã băm asset trùng |
| Run 42245312724 + 42245711312 | 15 tag có bộ cài lẻ (v0.2.0b1 … v2.0.6): so `Setup-*.exe` lẻ với file trong `BoCai.zip` |

**Kết quả kiểm:**
- Mọi asset khớp digest GitHub.
- Mọi `portable.zip` chứa **đúng cùng các file mô hình** (cùng SHA-256) với bản cài của cùng tag.
- Bộ cài lẻ `KiraPick-Setup-x.exe` **trùng SHA-256** với bộ cài trong `BoCai.zip` của cùng tag (Phụ lục A, cột cuối).

### 4.2 Nhóm ảnh hưởng

| Nhóm | Tag | Trọng số chưa đủ căn cứ trong gói | Số asset có trọng số |
|---|---|---|---|
| **Đã xác nhận bị ảnh hưởng** | v0.3.0b1 | TOPIQ-IAA | 3 |
| | v0.3.0b2–b4, v2.0.0–v2.0.6 | ArcFace, YoutuReID, TOPIQ-IAA | 3 × 10 = 30 |
| | v2.2.0a | ArcFace, YoutuReID, TOPIQ ×3, CLIP + prompts (+ LAION) | 3 (`.exe`, `-1.bin`, `-2.bin`) |
| | v2.2.1, v3.0.0 | như trên | 2 × 2 = 4 |
| | v3.0.0a | như trên | 3 |
| | **Tổng** | **15 tag, 43 asset** | |
| Không chứa trọng số bị loại | v0.2.0b1–b4 | không (SFace có trong cả 4: chờ xác minh) | 12 |
| Không chứa trọng số | `HUONG_DAN_CAI_DAT.txt` (v2.2.0a, v3.0.0a), `owner_backup.ps1` (v3.0.0a) | — | — |

**Lưu ý:**
- Mọi bản đều có SFace (chờ xác minh) và DLL FFmpeg không ghi thông báo, và đều thiếu toàn văn giấy phép.
- Bản CUDA (v2.2.0a, v3.0.0a) còn có DLL cuDNN 9 (chờ xác minh).
- Vì vậy **v0.2.0b1–b4 cũng chưa đủ căn cứ phân phối**, dù không chứa ArcFace / TOPIQ.

### 4.3 Hai mốc

| Mốc | Việc | Phụ thuộc |
|---|---|---|
| **D: dừng cung cấp** | Xoá 43 asset ở mục 4.2 (đề xuất xoá cả 12 asset của v0.2.0b1–b4). Giữ trang release, tag và ghi chú, thêm một dòng giải thích | **Không** phụ thuộc 3.0.1, làm được ngay khi chủ dự án duyệt |
| **U: mở đường cập nhật** | Đăng v3.0.1 (DirectML) và v3.0.1a (CUDA) | Sau khi 3.0.1 đạt nghiệm thu (mục 5) và có lệnh phát hành |

**Tác động trong khoảng giữa hai mốc:**

| Thứ tự | Trong khoảng giữa | Ưu | Nhược |
|---|---|---|---|
| **D trước, U sau** (đề xuất) | Không có bộ cài KiraPick nào để tải. Trình cập nhật trong app (2.2.x, 3.0.0, 3.0.0a) báo "không có bản mới" [Mã: bỏ release không còn file cài]. Máy đã cài **vẫn chạy bình thường**, không mất dữ liệu, nhưng **vẫn còn** các file cũ trên máy người dùng. Người cần cài lại máy thì không có bộ cài | Dừng phân phối sớm nhất | Khoảng trống không có bộ cài; nhãn "Latest" vẫn ở v3.0.0 nhưng trang đó không còn file |
| U trước, D ngay sau | Bộ cài cũ vẫn tải được tới khi 3.0.1 xong | Không có khoảng trống | Tiếp tục phân phối các file chưa đủ căn cứ trong thời gian làm 3.0.1 |

**Từ mốc U:**
- Trình cập nhật mời 2.2.x / 3.0.0 lên 3.0.1, và 3.0.0a lên 3.0.1a.
- Tag beta (`3.0.1b…`) không khớp mẫu, nên không bị mời.
- Bộ cài 3.0.1 xoá các file mô hình cũ khi nâng cấp.
- Bản trước 2.2 và bản portable không tự cập nhật; người dùng phải tải lại.
- **Bản CUDA:** nếu LIC-7 chưa xong, 3.0.1a **không đăng được** (cuDNN). Máy CUDA hoặc chuyển sang gói DirectML (chạy được
  trên card NVIDIA), hoặc chờ.

**Không thu hồi được:** bản đã tải, đã cài, hoặc bản sao ở nơi khác. Gỡ asset chỉ dừng việc phân phối tiếp.

Mình **không có quyền** sửa release trong phiên này (GitHub trả 403). Mốc D và U do chủ dự án bấm, hoặc cấp quyền riêng.

---

## 5. Nghiệm thu bản đóng gói

**Ai chạy:**
- **CI:** máy Windows Server 2022 của GitHub, **không có GPU**. Ảnh dùng là ảnh tổng hợp / ảnh mẫu công khai, **không** dùng
  ảnh của chủ dự án.
- **Chủ dự án:** máy i7-10750H, RTX 2080 Super Max-Q.

### 5.1 Cấu hình T (gói chung)

| # | Kiểm | Ai | Đạt khi |
|---|---|---|---|
| T1 | File đã cài | CI | **Không có** file `.onnx` / `.pth` / `.pt` / `.npz` / `.task` nào; không ONNX Runtime, DirectML, CUDA, FFmpeg |
| T2 | Giấy tờ | CI | Có toàn văn: LGPL-3.0 + GPL-3.0 (Qt), LGPL-2.1 (LibRaw), Apache-2.0 (OpenCV), PSF và bảng gói Python. Không còn dòng nào về mô hình |
| T3 | `--self-test` | CI | Đạt; báo "không có mô hình", không mở file mô hình nào |
| T4 | Luồng thủ công: nhập thư mục JPEG + RAW, xem, P/X, sao, ❤, so sánh, xuất bản sao | CI (GUI offscreen, test có sẵn) + chủ dự án (bấm tay) | Chạy đủ; màn AI nói rõ "bản này không có AI" |
| T5 | Tắt mạng | CI (test chặn socket) + chủ dự án (rút mạng) | Như T4 |
| T6 | Nâng cấp từ 3.0.0 (cài v3.0.0 thật, có phiên đã phân tích và `learning.db`, rồi cài T đè lên) | CI | Toàn bộ 15 file mô hình cũ **không còn**; chép lại bằng tay → không mở; P/X, sao, ❤, nhóm chỉnh tay giữ nguyên; nhóm tự động cũ theo DATA-1; dòng cũ trong DB **còn nguyên**; SHA-256 ảnh gốc không đổi |
| T7 | Nâng cấp trên phiên thật của chủ dự án | Chủ dự án | Như T6, kiểm bằng mắt |

### 5.2 Cấu hình A (gói DirectML, CUDA, portable)

| # | Kiểm | DirectML | CUDA | portable | Ai | Đạt khi |
|---|---|---|---|---|---|---|
| A1 | File mô hình | ✔ | ✔ | ✔ | CI | Đúng **6 file** của cấu hình A (tên + SHA-256), không thừa không thiếu |
| A2 | DLL | ✔ | ✔ | ✔ | CI | Không FFmpeg. CUDA: không TensorRT, không bản trùng; cuDNN theo LIC-7 |
| A3 | Giấy tờ theo gói | ✔ | ✔ | ✔ | CI | Như T2, cộng: Apache-2.0 (YOLOX, MediaPipe, ORT), MIT + BSD-3 (YuNet), ghi công CC BY 4.0 (eDifFIQA), ghi đổi float16 / ONNX. DirectML: điều khoản Microsoft. CUDA: EULA NVIDIA |
| A4 | `--self-test` + báo cáo A | ✔ (CPU) | ✔ (CPU dự phòng) | ✔ (CPU) | CI | Chỉ 6 file được mở, đúng SHA-256 |
| A5 | Phân tích thư mục mẫu: log nạp mô hình | ✔ (CPU) | ✔ (CPU) | ✔ (CPU) | CI | Log chỉ có 6 file; có khung người, khung mặt, điểm kỹ thuật, mắt nhắm / mở; gom nhóm báo "chưa có" |
| A5-GPU | Như A5 trên GPU thật | ✔ DirectML | ✔ CUDA | ✔ | **Chủ dự án** | Log ghi provider DirectML / CUDA; 6 file; thời gian mỗi ảnh |
| A6 | Nâng cấp từ 3.0.0 / 3.0.0a | ✔ (từ v3.0.0) | ✔ (từ v3.0.0a) | giải nén đè | CI | Như T6. Ngoài ra: 9 file bị loại không còn; chép lại → log "bỏ qua"; phân tích lại phiên cũ không dùng vector / điểm cũ |
| A7 | Nâng cấp trên phiên thật | ✔ | ✔ | — | **Chủ dự án** | Như T7 |
| A8 | Tắt mạng | ✔ | ✔ | ✔ | CI + chủ dự án | Như A5 |
| A9 | Trình cập nhật | ✔ | ✔ | — | CI (danh sách release giả) + chủ dự án (release thật, sau mốc U) | 3.0.0 → 3.0.1; 3.0.0a → 3.0.1a; beta không bị mời |
| A10 | Chuyển đổi MediaPipe | ✔ | | | CI | Chạy lại `scripts/convert_mediapipe.py` từ `.task` `64184e22…c9ff` → SHA-256 trùng file trong repo; nếu không trùng thì bỏ MediaPipe khỏi cấu hình A |

**Kết quả nộp:**
- Báo cáo CI gồm: danh sách file từng gói, báo cáo A, log nạp mô hình, kết quả T1–T6 / A1–A6, A8, A9, A10.
- Phần chủ dự án chạy (T7, A5-GPU, A7) ghi **riêng**: chưa có thì ghi "chưa chạy", không gộp với kết quả CI.

---

## 6. F-SF và Q-TECH

| Phép đo | Thành phần | Đo được không |
|---|---|---|
| **F-SF** (gom nhóm, D1) | YOLOX, YuNet, **SFace** + màu trang phục | Chỉ **đo nội bộ** trên máy chủ dự án. SFace chờ xác minh, nên kết quả F-SF **không** dẫn tới việc đưa SFace vào 3.0.1 cho tới khi có xác nhận. Đo được để biết có đáng xin xác nhận không |
| **Q-TECH** (chấm kỹ thuật, D3) | Không nạp mô hình. Đọc số đo đã lưu: nét, sáng, bố cục (app), eDifFIQA, mắt MediaPipe | **Đo được**. Không đọc cột TOPIQ. Thành phần đều thuộc cấu hình A |
| Q-TECH bỏ MediaPipe | như trên, bỏ giá trị mắt | Đo được; dùng nếu A10 không đạt |

---

## 7. Quyết định cần chủ dự án duyệt

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| **REL-1** | Nền 3.0.1: tag `v3.0.0` rồi đưa sang `beta` | Đồng ý |
| **CFG-1** | 3.0.1 phát hành cấu hình nào: chỉ T; chỉ A; hay cả hai | **A** (DirectML + portable), có T làm phương án dự phòng nếu A chưa đạt |
| **LIC-1** | Phạm vi sửa mã: danh sách cho phép, tách "dò" khỏi "nhận mặt", chặn cache / `learning.db`, `[InstallDelete]`, báo cáo A | Đồng ý |
| **LIC-2** | `inspect-release` thành bước bắt buộc trước khi đăng (T1–T2, A1–A3) | Đồng ý |
| **LIC-3** | Hỏi xác nhận: tác giả SFace (Yaoyao Zhong); fal (nguồn gốc `glintr100`); Tencent (YoutuReID); OpenAI (CLIP); NVIDIA (cuDNN 9) | Đồng ý, làm song song |
| **LIC-5** | Bỏ DLL FFmpeg, TensorRT provider và bản DLL NVIDIA trùng | Đồng ý |
| **LIC-7** | Gói CUDA khi cuDNN 9 chưa rõ: (a) không đăng 3.0.1a; (b) gói CUDA không kèm cuDNN, người dùng tự cài; (c) chờ NVIDIA | **(a)** cho 3.0.1; máy NVIDIA dùng gói DirectML |
| **DATA-1** | Nhóm tự động cũ (gom bằng ArcFace) trong phiên 3.0.0: ẩn, giữ nhóm người dùng đã chỉnh | Đồng ý |
| **LIC-4D** | Mốc D: xoá 43 asset (+12 asset v0.2.0b1–b4?) và thời điểm làm | Xoá cả 55, ngay khi duyệt |
| **LIC-4U** | Mốc U: đăng 3.0.1 sau khi nghiệm thu đạt | Lệnh phát hành riêng |
| **BM-0** | Chạy F-SF (nội bộ) và Q-TECH trên máy chủ dự án | Đồng ý |

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

