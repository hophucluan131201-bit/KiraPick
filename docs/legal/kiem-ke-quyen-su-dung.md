# Kiểm kê thành phần và quyền sử dụng: bản 3.0.0 và cấu hình dự kiến trên `beta` (2026-11-06)

- **Phạm vi:** chỉ kiểm kê và trình phương án.
  - Không đổi mặc định, không đóng gói, không chạy benchmark.
  - Đổi mặc định, đóng gói phân phối, merge vào `main`, tag và phát hành đều cần chủ dự án duyệt riêng.
- **Mình không phải luật sư.** "Có căn cứ" nghĩa là có điều khoản hoặc văn bản của bên cấp quyền cho phép việc đó.
  - **Xác nhận của chủ dự án** chỉ phê duyệt việc **triển khai trong dự án**. Nó **không** tạo ra quyền sử dụng.
  - Mục nào chưa có căn cứ thì ghi **chưa xác minh**.
- **Bằng chứng:** commit `e2fec9d` (tag `v3.0.0` / `v3.0.0a`).
  - Mã AI, manifest, `scripts/build_windows.ps1`, `scripts/fetch_models.py` và `scripts/shrink_models.py` của commit này
    **giống hệt** nhánh `beta` hiện tại (`git diff e2fec9d HEAD`).
  - Chỗ khác duy nhất là `packaging/kirapick.spec` thêm 2 ảnh của màn hình chọn chế độ.

---

## A. Danh sách A: thành phần thực sự được nạp khi chạy

Nguồn: đọc mã ([Repo]). Chưa có log ghi lại các file đã nạp trên máy thật; mục E đề xuất cách ghi.

### A.1 Luồng Chụp cá nhân (bản 3.0.0)

| Bước | Trọng số nạp | Điều kiện nạp | Đường dự phòng khi thiếu | Dữ liệu còn lưu lại (cache) |
|---|---|---|---|---|
| Dò người | YOLOX-S (CPU); YOLOX-M (GPU, nếu card chạy nhanh hơn) | luôn có (`app/ai/detect.py:69-73`) | YOLOX-M thiếu → YOLOX-S | khung người trong `occurrences` |
| Dò mặt | YuNet | luôn có (`detect.py:123`, `face_quality.py:19`) | không có (bắt buộc) | — |
| Nhận mặt cơ bản | SFace | luôn có (`detect.py:161`) | không có (bắt buộc) | vector `face` trong `occurrence_vectors` |
| **Nhận mặt mạnh + dáng người** | **ArcFace w600k_r50 + YoutuReID** | **tự nạp khi cả hai file có mặt** (`embed_job.py:53`, `registry.ready("identity_plus")`) | thiếu một trong hai → bỏ bước này, gom bằng SFace + màu trang phục | vector **`face_arc`** và **`body`** trong `occurrence_vectors`; giá trị `face_arc`, `body` trong `learning.db` (bảng `identity_feedback`) |
| **Chọn cách gom** | — | `session_profile()` (`cluster.py:153`) chọn **ArcFace+ReID nếu phiên đã có vector `face_arc`**, kể cả khi file ArcFace đã bị gỡ | — | **Cache cũ quyết định cách gom**: phiên đã phân tích bằng ArcFace sẽ tiếp tục gom bằng vector ArcFace đã lưu |
| Chất lượng mặt | eDifFIQA(T) | nếu có (`quality_job.py:186`) | thiếu → "chưa đánh giá" | giá trị trong `measurements` |
| Mắt nhắm / mở | MediaPipe face mesh + blendshapes | nếu có (`quality_job.py:190`) | thiếu → "chưa đánh giá" | `measurements` |
| **Thẩm mỹ** | **TOPIQ-IAA** | nếu có (`quality_job.py:195`) | thiếu → "chưa đánh giá" | **`aesthetic_mos`** trong `measurements` |
| **Chất lượng kỹ thuật, chất lượng mặt** | **TOPIQ-NR, TOPIQ-face** | nếu có (`load_extras`) | thiếu → bỏ | **`tech_iqa`, `face_iqa`** trong `measurements` |
| Thẩm mỹ CLIP, gu, nhãn phong cách | CLIP ViT-L/14 + LAION + `clip_prompts` | nếu có | thiếu → bỏ | vector `clip` trong `asset_vectors`; vector CLIP trong `learning.db` (học gu) |
| **Tính điểm** | — | `app/quality/score.py` **đọc các giá trị đã lưu**: `aesthetic_mos`, `tech_iqa`, `face_iqa`, LAION | — | **Điểm của phiên cũ vẫn dùng kết quả TOPIQ đã lưu**, kể cả khi file TOPIQ đã bị gỡ |
| Gợi ý nhận mặt khi học | — | `learning.db` lưu cả độ giống SFace, ArcFace, màu trang phục, ReID | — | học từ dữ liệu ArcFace / ReID cũ |

**Thư viện nạp khi chạy:**
- Python 3.12;
- PySide6 / Qt 6.12;
- OpenCV 4.14 (YuNet, SFace, eDifFIQA, YoutuReID chạy qua `cv2.dnn`);
- ONNX Runtime 1.24.4: bản DirectML hoặc bản GPU; bản CUDA kèm DLL CUDA / cuDNN của NVIDIA;
- NumPy, Pillow, rawpy + LibRaw, ExifRead, PyYAML;
- bootloader PyInstaller.

### A.2 Luồng Media sự kiện

| Phiên bản | Nạp gì |
|---|---|
| **3.0.0** | **Không có luồng Media** (chưa có trong bản 3.0.0) |
| **`beta`** | Chỉ có màn hình "đang phát triển": **không nạp mô hình nào**. Lớp chặn `MediaRegistry` (commit `703ad8d`) chỉ cho nạp các trọng số trong `configs/media-models.json` có trạng thái `verified` / `approved_with_risk`. Hiện chỉ có CLIP. Media chưa có mã phân tích |

### A.3 Các đường khác

- **`--self-test`:** nạp mọi mô hình có mặt để kiểm tra (`app/selftest.py`).
- **`--diagnose-grouping`:** chỉ đọc dữ liệu đã lưu, không nạp mô hình.
- **Cập nhật app:** tải **bộ cài** từ GitHub Release khi người dùng bấm. Không tải mô hình.

## B. Danh sách B: những gì có trong bộ cài và gói tải thêm

Nguồn: script build ([Repo]). **Chưa kiểm trực tiếp** bên trong bộ cài 3.0.0 đã phát hành (mục E đề xuất cách kiểm).

**Trọng số**, đều có trong **cả hai bản** DirectML 3.0.0 và CUDA 3.0.0a:
- `fetch_models.py --purpose identity,identity_plus,quality,gpu`;
- cộng các mô hình chuyển đổi lúc build;
- tất cả copy vào `models\` (`build_windows.ps1`).

| Trọng số | File trong bộ cài | Nguồn chính thức | Revision / file gốc | SHA-256 file gốc | Bản ONNX / chuyển đổi |
|---|---|---|---|---|---|
| YuNet | `face_detection_yunet_2023mar.onnx` | opencv/opencv_zoo | commit `48b10fa` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | ONNX gốc |
| SFace | `face_recognition_sface_2021dec.onnx` | opencv/opencv_zoo | `48b10fa` | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` | ONNX gốc; **lưu dạng float16** (`shrink_models.py`, ghi `fp16w-of:<sha gốc>`) |
| YOLOX-S | `yolox_s.onnx` | Megvii-BaseDetection/YOLOX | release 0.1.1rc0 | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` | ONNX gốc |
| YOLOX-M | `yolox_m.onnx` | như trên | 0.1.1rc0 | `21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f` | ONNX gốc; float16 |
| eDifFIQA(T) | `ediffiqa_tiny_jun2024.onnx` | opencv_zoo | `48b10fa` | `9426c899cc0f01665240cb7d9e7f98e18e24e456c178326c771a43da289bfc6a` | ONNX gốc |
| MediaPipe face mesh | `mediapipe_face_landmarks_v2.onnx` | Google `face_landmarker.task` float16 v1 (storage.googleapis.com) | file `.task` v1 | ONNX: `a044fec26cd90125566eb8703258dd7a211cca60423801462663af8f13636f56` | **chuyển đổi** bằng tf2onnx 1.16.1 (`scripts/convert_mediapipe.py`), lưu trong repo |
| MediaPipe blendshapes | `mediapipe_face_blendshapes_v2.onnx` | như trên | như trên | ONNX: `ce56bc10f1b0306701b8bdb5cd05661a37a380f62638db7102bb61d6bc0d1a77` | chuyển đổi như trên |
| **ArcFace** | `w600k_r50.onnx` | deepinsight/insightface, `buffalo_l.zip` | release v0.7 | `4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43` | ONNX gốc; float16 |
| **YoutuReID** | `person_reid_youtu_2021nov.onnx` | opencv_zoo (gốc: ReID-Team / Tencent Youtu) | `48b10fa` | `0579683334d4b9440221606dcb461656dd0dc64143b18f48faedaced9b4f580d` | ONNX gốc; float16 |
| **TOPIQ-IAA** | `topiq_iaa_res50.onnx` | chaofengc/IQA-PyTorch, release v0.1-weights | `cfanet_iaa_ava_res50-3cd62bb3.pth` | `3cd62bb33f9933ed7c6e3d5e79129e81c898eba78b7a2af516a0b0b974616975` | **chuyển đổi lúc build** (`convert_topiq.py`); SHA của ONNX trong file `.sha256`; float16 |
| **TOPIQ-NR (KonIQ)** | `topiq_nr_koniq_res50.onnx` | huggingface.co/chaofengc/IQA-PyTorch-Weights | `cfanet_nr_koniq_res50-9a73138b.pth` | `9a73138beb3748dd6a83365610ac88fa1cd53225342c77fc9ed44a3be461354c` | chuyển đổi lúc build; float16 |
| **TOPIQ-face** | `topiq_nr_face_res50.onnx` | như trên | `topiq_nr_cgfiqa_res50-0a8b8e4f.pth` | `0a8b8e4f458c782301b9940e15699d2b5b8919252c973f52e7060d8070997898` | chuyển đổi lúc build; float16 |
| CLIP ViT-L/14 ảnh | `clip_l14_image.onnx` | openaipublic.azureedge.net | `ViT-L-14.pt` | `b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836` | chuyển đổi lúc build (`convert_clip.py`); float16 |
| CLIP mô tả chữ | `clip_prompts_v1.npz` | tính từ tháp chữ của CLIP | như trên | (`.sha256` lúc build) | tính lúc build |
| LAION aesthetic | `laion_aesthetic.onnx` | christophschuhmann/improved-aesthetic-predictor, nhánh `main` | `sac+logos+ava1-l14-linearMSE.pth` | `21dd590f3ccdc646f0d53120778b296013b096a035a2718c9cb0d511bff0f1e0` | chuyển đổi lúc build |

- **SHA-256 của các file ONNX chuyển đổi lúc build** không cố định (ghi trong `.sha256` cạnh file). Cần đọc từ bản build
  thật (mục E).
- **Thư viện trong bộ cài:** như A.1. Bản CUDA có thêm DLL CUDA / cuBLAS / cuFFT / cuRAND / NVRTC / cuDNN, lấy từ các gói
  pip của NVIDIA (`kirapick.spec:34-35`). Có thêm DLL Visual C++ runtime.
- **Giấy tờ kèm theo** (`build_windows.ps1:180-182`): `LICENSE.md`, `THIRD_PARTY_NOTICES.md`,
  `docs/model-licenses.md`, `packaging/notes/LICENSES.txt`, vào `{app}\docs`.
- **Gói tải thêm:** **không có.** App không tải mô hình khi chạy (`THIRD_PARTY_NOTICES.md` và test chặn mạng). Nút cập nhật
  chỉ tải bộ cài mới.

## C. Ba trạng thái quyền cho từng thành phần

**Cột:**
- **Đo nội bộ:** chạy benchmark trên máy chủ dự án.
- **Job có thu tiền:** dùng để xử lý ảnh giao khách.
- **Phân phối:** đưa vào bộ cài cho người khác.
- **Nghĩa vụ:** những gì phải làm khi dùng hoặc phân phối.

| Thành phần | Điều khoản (nguồn) | Đo nội bộ | Job có thu tiền | Phân phối | Nghĩa vụ |
|---|---|---|---|---|---|
| YuNet | MIT (opencv_zoo); dữ liệu WIDER FACE chỉ cho nghiên cứu | **có căn cứ** (MIT) | **có căn cứ theo giấy phép trọng số**; rủi ro dữ liệu **chưa xác minh** | có căn cứ (MIT) | giữ thông báo MIT |
| SFace | Apache-2.0 (opencv_zoo); dữ liệu không công bố | có căn cứ | có căn cứ theo giấy phép trọng số; dữ liệu **chưa xác minh** | có căn cứ | giữ LICENSE Apache-2.0; ghi rõ đã đổi sang float16 |
| YOLOX-S / -M | Apache-2.0 (LICENSE của repo; **không nêu riêng trọng số**) | có căn cứ | có căn cứ theo LICENSE repo; phạm vi với trọng số **chưa xác minh** | như cột trước | giữ LICENSE Apache-2.0; NOTICE nếu có |
| eDifFIQA(T) | CC BY 4.0 | có căn cứ | **có căn cứ** (CC BY cho phép thương mại) | có căn cứ | **ghi công** tác giả (đã có trong THIRD_PARTY_NOTICES) |
| MediaPipe mesh / blendshapes | model card ghi Apache-2.0; **không thấy giấy phép của file `.task`** | có căn cứ theo model card | **chưa xác minh** (giấy phép file `.task`) | **chưa xác minh** | Apache-2.0; ghi rõ đã chuyển sang ONNX |
| **ArcFace w600k_r50** | "available for **non-commercial research purposes only**" (InsightFace) | **chưa xác minh**: benchmark của bên làm dịch vụ có thu tiền có được coi là "nghiên cứu phi thương mại" không | **không có căn cứ**; cần giấy phép InsightFace cho đúng trọng số này | **không có căn cứ** cho bản dùng thương mại | — |
| **YoutuReID** | opencv_zoo ghi Apache-2.0 nhưng LICENSE không ghi người giữ quyền, không nhắc trọng số; nguồn gốc **không có giấy phép**; dữ liệu nghiên cứu (có DukeMTMC đã bị rút) | **chưa xác minh** | **chưa xác minh** | **chưa xác minh** | — |
| **TOPIQ ×3** | PolyForm Noncommercial 1.0.0 (Chaofeng Chen) | **chưa xác minh**: PolyForm cho phép "research… without any anticipated commercial application"; đo để chọn mô hình cho việc có thu tiền **khó coi là không có ứng dụng thương mại** | **không có căn cứ** | **không có căn cứ** cho người dùng thương mại | giữ thông báo bản quyền; chỉ phi thương mại |
| CLIP ViT-L/14 | mã MIT; model card: "deployed use… out of scope", loại trừ nhận diện khuôn mặt | có căn cứ (MIT); model card là khuyến cáo | **chưa xác minh**: MIT cho phép, model card khuyến cáo không triển khai. **Chủ dự án chấp nhận rủi ro** (2026-10-28), nhưng đó **không phải** căn cứ quyền | như cột trước | giữ thông báo MIT |
| LAION aesthetic | Apache-2.0 (repo); dữ liệu điểm AVA / SAC / LAION-Logos | có căn cứ | theo giấy phép trọng số: có; dữ liệu **chưa xác minh** | có căn cứ | giữ thông báo Apache-2.0 |
| Qt / PySide6 | LGPL-3.0 | có | có | có, **kèm nghĩa vụ LGPL**: DLL thay được (đã làm), kèm văn bản LGPL, chỉ nguồn | giữ LGPL; THIRD_PARTY_NOTICES đã ghi |
| LibRaw (qua rawpy) | LGPL-2.1 hoặc CDDL-1.0 | có | có | có, kèm nghĩa vụ LGPL / CDDL | giữ thông báo |
| ONNX Runtime | MIT | có | có | có | giữ thông báo MIT |
| DirectML.dll | giấy phép tái phân phối của Microsoft | có | có | có (được phép đi kèm ứng dụng) | theo điều khoản Microsoft |
| DLL CUDA / cuDNN (bản CUDA) | giấy phép NVIDIA; được tái phân phối kèm ứng dụng | có | có | **cần đọc lại** điều khoản cuDNN / CUDA EULA cho đúng phiên bản | theo EULA của NVIDIA |
| OpenCV, NumPy, Pillow, ExifRead, PyYAML | Apache / BSD / HPND / MIT | có | có | có | giữ thông báo |
| PyInstaller bootloader | GPL-2.0 với ngoại lệ bootloader | có | có | có (theo ngoại lệ) | — |
| VC++ runtime DLL | điều khoản Microsoft VC++ Redistributable | có | có | có | theo điều khoản |

**Ghi chú về giấy tờ:** `THIRD_PARTY_NOTICES.md` đã có các dòng trên. Nhưng bộ cài **chưa kèm toàn văn** các giấy phép
(Apache-2.0, LGPL-3.0, CC BY 4.0…). Cần kiểm trực tiếp trong `{app}\docs` (mục E).

## D. Kết luận cho bản 3.0.0

| Luồng | Dùng được cho job có thu tiền? | Bằng chứng |
|---|---|---|
| **Chụp cá nhân** (mặc định 3.0.0) | **Không có căn cứ.** Luồng này **tự nạp ArcFace + YoutuReID** khi file có mặt (bộ cài có sẵn cả hai), và **TOPIQ ×3** để chấm. Điểm của phiên cũ còn dùng kết quả TOPIQ đã lưu | A.1: `embed_job.py:53`, `quality_job.py:195` và `load_extras`, `score.py`; B: build tải `identity_plus` và chuyển đổi TOPIQ |
| Chụp cá nhân **sau khi tự xoá file** ArcFace / YoutuReID / TOPIQ | **Không được hỗ trợ và không đủ**: phiên đã phân tích trước đó vẫn gom bằng vector ArcFace đã lưu và chấm bằng điểm TOPIQ đã lưu | `cluster.py:153` (`session_profile`), `score.py` |
| **Media sự kiện** | **Không có trong 3.0.0** | A.2 |
| `--diagnose-grouping` | Không xử lý ảnh giao khách (chỉ chẩn đoán) | A.3 |

**Tóm lại:** **chưa luồng nào của bản 3.0.0 có căn cứ đầy đủ để dùng cho job có thu tiền.** Riêng phân phối: bộ cài 3.0.0
đang chứa ArcFace và TOPIQ. Đây là phân phối cho người khác những trọng số chỉ được dùng phi thương mại. Việc này **cần chủ
dự án quyết hướng xử lý** (mục F, LIC-4).

## E. Cơ chế chặn và cách kiểm (đề xuất)

**Cho cấu hình dùng job có thu tiền:**
1. **Danh sách cho phép theo cấu hình** (mở rộng `configs/media-models.json` thành danh sách cho mọi cấu hình "thương mại").
   - Mọi chỗ gọi `registry.require` / `ready` trong cấu hình đó đi qua lớp chặn, kể cả `load_extras`, `embed_job` và
     `selftest`. Hiện chỉ Media có lớp chặn.
2. **Đường dự phòng:** test chạy cấu hình thương mại khi thư mục `models\` chứa **đủ** mọi file, kể cả ArcFace / TOPIQ.
   Khẳng định không file ngoài danh sách nào được mở. Kiểm bằng cách bọc `create_session`, `cv2.dnn.readNet*` và
   `FaceRecognizerSF.create`, rồi ghi lại mọi đường dẫn được mở.
3. **Cache cũ:** khi mở phiên ở cấu hình thương mại, **bỏ qua** vector `face_arc` / `body` và giá trị `aesthetic_mos`,
   `tech_iqa`, `face_iqa` đã lưu. Không xoá dữ liệu: chỉ không đọc. Test: phiên có sẵn vector ArcFace → cách gom phải là
   SFace (hoặc mô hình thay thế), và điểm không dùng giá trị TOPIQ.
4. **`learning.db`:** chỉ học từ các giá trị được phép (không dùng `face_arc`, `body`) trong cấu hình thương mại.
5. **Báo cáo A khi chạy:** `--self-test` có thêm chế độ "thương mại". Chế độ này ghi mọi file đã mở kèm SHA-256 vào
   `selftest.json`. CI lỗi nếu có file ngoài danh sách.

**Cho bản phân phối:**
1. **Kiểm trực tiếp bộ cài:** bước CI cài silent bộ cài vừa build, rồi liệt kê `{app}\models\` (tên, kích thước,
   SHA-256), đối chiếu manifest và `configs/media-models.json` (`scripts/media_model_report.py`). Ghi kết quả vào
   thông báo CI.
2. **Đối chiếu giấy tờ:** kiểm `{app}\docs` có `THIRD_PARTY_NOTICES.md`, `docs/model-licenses.md`, và **toàn văn** các
   giấy phép bắt buộc (Apache-2.0, LGPL-3.0, LGPL-2.1, CC BY 4.0, MIT). CI lỗi nếu thiếu.
3. **Gói tải thêm:** không có. Test chặn mạng đã khẳng định chỉ `app/updates/` dùng mạng; nút cập nhật chỉ tải bộ cài.
4. **Bộ cài 3.0.0 đã phát hành:** chạy bước 1–2 trên file đã phát hành để có bằng chứng trực tiếp. Hiện mới suy từ script
   build.

## F. Cấu hình thay thế trên `beta` (trình duyệt, chưa làm)

| Phần | Cấu hình đề xuất cho job có thu tiền | Căn cứ | Ảnh hưởng tính năng |
|---|---|---|---|
| Thẩm mỹ / chất lượng | **Q-TECH**: chỉ phép đo kỹ thuật của KiraPick, cộng eDifFIQA (CC BY 4.0) | mã của app; eDifFIQA có căn cứ | **Mất** điểm thẩm mỹ TOPIQ và điểm kỹ thuật TOPIQ. Còn nét ở mắt, mắt nhắm / mở, sáng, bố cục, chất lượng mặt (eDifFIQA). CLIP + LAION chỉ dùng nếu chủ dự án chấp nhận phần **chưa xác minh** của CLIP (C) |
| Nhận mặt | **SFace** (có căn cứ theo giấy phép trọng số), hoặc **AuraFace** sau khi kiểm file thật và **chỉ dùng file nhận mặt** | C; AuraFace chờ tải và kiểm | Gom người kém hơn ArcFace: SFace đo được 0,808 so với 0,922 (số lịch sử, có giới hạn so sánh) |
| Dáng người | **Không dùng YoutuReID** cho tới khi xác minh được quyền | C | Ảnh quay lưng, che mặt, mặt nhỏ dễ tách nhầm hơn → cần gom tay |
| Mắt nhắm / mở | MediaPipe **chỉ khi** xác minh được giấy phép của file `.task` | C | Nếu chưa xác minh: mắt nhắm / mở thành "chưa đánh giá" |
| Học gu | chỉ khi dùng CLIP | C | Nếu không: không có điểm "Hợp gu" |
| Media | như đặc tả bản 5 (YOLOX, YuNet, SFace, CLIP theo trạng thái) | C | — |

**Phần benchmark đủ điều kiện chạy ngay** (khi chủ dự án cho chạy BM-0):
- **F-SF** trên D1;
- **Q-TECH** trên lịch sử P/X.

Cả hai chỉ dùng thành phần **có căn cứ đo nội bộ**: YuNet, SFace, YOLOX, eDifFIQA và mã của app.

**Chưa đủ điều kiện:**
- **F-AU**: chờ tải và kiểm file thật;
- **F-SF+R / F-AU+R**: YoutuReID chưa xác minh;
- **Q-CL**: CLIP / LAION, phần job có thu tiền chưa xác minh;
- **chạy lại ArcFace / TOPIQ**: đo nội bộ chưa xác minh.

## G. Quyết định cần chủ dự án

| Mã | Câu hỏi |
|---|---|
| LIC-1 | Làm cơ chế chặn ở mục E cho Chụp cá nhân ("chế độ thương mại"), cùng test đường dự phòng và cache? |
| LIC-2 | Thêm bước CI kiểm trực tiếp bộ cài và giấy tờ giấy phép (E, phân phối 1–4), và chạy trên bộ cài 3.0.0 đã phát hành? |
| LIC-3 | Có liên hệ bên cấp quyền không: InsightFace (ArcFace), Tencent Youtu (YoutuReID), tác giả TOPIQ, Google (file `.task` của MediaPipe)? |
| LIC-4 | Bộ cài 3.0.0 đang phân phối ArcFace và TOPIQ: (a) giữ nguyên; (b) phát hành bản không chứa chúng; (c) để chế độ thương mại bỏ qua chúng, còn bộ cài giữ nguyên. Chủ dự án quyết; mình chỉ ghi lại căn cứ |
| BM-0 | Cho chạy F-SF và Q-TECH (đủ điều kiện)? |
