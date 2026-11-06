# Kế hoạch đo trước khi đổi mô hình nhận mặt và chấm thẩm mỹ (bản 2, 2026-11-06)

**Chủ dự án đã chốt (2026-11-06):**
- **Giữ cả bốn cấu hình** F-SF, F-AU, F-SF+R, F-AU+R.
- **Báo riêng phần cải thiện khi thêm YoutuReID** vào SFace và vào AuraFace, nhất là với ảnh quay lưng, che mặt và mặt quá
  nhỏ (mục 2.5).
- **Tách kết luận đo khỏi đề xuất đóng gói** (mục 4).
- **Xác minh quyền dùng và phân phối YoutuReID** trước khi đề xuất giữ nó trong bản thương mại (mục 4.2).
- Đổi cấu hình mặc định chờ chủ dự án duyệt.

- **Phạm vi:** nhánh `beta`, tài liệu.
- **Cấu hình mô hình đang chạy giữ nguyên** cho tới khi chủ dự án duyệt phương án thay thế.
- **Cần duyệt riêng:** thay cấu hình mặc định, đóng gói để phân phối, merge vào `main`, tag và phát hành.
- **Nguồn rà soát:** `docs/design/thay-the-arcface-topiq.md`.

**Quy ước:**
- **[Repo]**: đã xác minh trong mã nguồn hoặc tài liệu của repo.
- **[Thiếu]**: đầu vào chưa có.
- **[Chờ duyệt]**: cần chủ dự án quyết định.

## 1. Đầu vào của từng cấu hình

### 1.1 Trọng số

| Mã | Thành phần | File | Nguồn chính thức / revision | SHA-256 | Giấy phép / điều kiện phân phối | Nạp khi chạy (đo) | Có trong bộ cài hiện tại |
|---|---|---|---|---|---|---|---|
| W1 | Dò mặt YuNet 2023mar | `face_detection_yunet_2023mar.onnx` | opencv_zoo@48b10fa [Repo: manifest] | `8f2383e4…52fa4` [Repo] | MIT (opencv_zoo); huấn luyện trên WIDER FACE (dữ liệu chỉ cho nghiên cứu) | Có, mọi cấu hình | Có |
| W2 | Nhận mặt SFace 2021dec | `face_recognition_sface_2021dec.onnx` | opencv_zoo@48b10fa [Repo] | `0ba9fbfa…79` [Repo] | Apache-2.0; dữ liệu huấn luyện không công bố | Có (F-SF) | Có |
| W3 | Nhận mặt **AuraFace v1** | file nhận mặt trong `fal/AuraFace-v1` (tên file, revision, kích thước: **[Thiếu]**) | huggingface.co/fal/AuraFace-v1, ghi revision khi tải | **[Thiếu]** | Model card: Apache-2.0; dữ liệu "thương mại", không nêu tên. **Chỉ dùng file nhận mặt** | Có (F-AU) | **Không** (chỉ nằm trong máy đo) |
| W3x | Các file **dò mặt / căn chỉnh / tuổi-giới** đi kèm trong repo AuraFace | các file khác trong `fal/AuraFace-v1` | như W3 | **[Thiếu]** | Theo bản sao `imagent/auraface-onnx`: đây là mô hình InsightFace, **phi thương mại** | **Không bao giờ nạp**; không tải về | Không |
| W4 | Dáng người YoutuReID | `person_reid_youtu_2021nov.onnx` | opencv_zoo@48b10fa [Repo]; nguồn gốc ReID-Team/ReID_extra_testdata | `05796833…580d` [Repo] | **Quyền thương mại chưa rõ** (mục 4.2) | Có (F-SF+R, F-AU+R) | Có |
| W5 | ArcFace w600k_r50 (baseline) | `w600k_r50.onnx` | InsightFace v0.7 [Repo] | `4c06341c…9e43` [Repo] | **Phi thương mại**; dùng trong bản thương mại cần giấy phép của InsightFace cho đúng trọng số này | **Không chạy lại** (mục 2.2) | Có (Chụp cá nhân hiện tại) |
| W6 | CLIP ViT-L/14 ảnh | `clip_l14_image.onnx` (chuyển lúc build) | OpenAI ViT-L-14.pt, SHA nguồn `b8cca3fd…3836` [Repo] | theo file `.sha256` lúc build [Repo] | MIT (mã); model card "ngoài phạm vi"; **chủ dự án đã chấp nhận rủi ro** (2026-10-28, MOD-1) | Có (Q-CL) | Có |
| W7 | Đầu LAION aesthetic | `laion_aesthetic.onnx` (chuyển lúc build) | improved-aesthetic-predictor [Repo] | theo `.sha256` [Repo] | Apache-2.0; huấn luyện trên điểm AVA / SAC / LAION-Logos (**điều khoản dữ liệu chờ xác minh**) | Có (Q-CL) | Có |
| W8 | TOPIQ ×3 (baseline) | `topiq_*.onnx` | IQA-PyTorch [Repo] | theo `.sha256` [Repo] | **PolyForm Noncommercial** | **Không chạy lại**; dùng điểm đã lưu (mục 3) | Có |

**Hai danh sách tách riêng:**
- **"Nạp khi chạy"** do máy đo ghi lại: tên file và SHA-256 của từng file thực sự được mở, giống báo cáo A của Media.
- **"Có trong bộ cài"** lấy từ `scripts/media_model_report.py` (báo cáo B) chạy trên thư mục `models\` của bản cài.
- AuraFace **không** vào bộ cài ở giai đoạn đo.

### 1.2 Pipeline nhận mặt dùng chung (cho phép so cố định)

Cố định ba thành phần sau cho **mọi** cấu hình nhận mặt:
- **Dò mặt:** YuNet (W1), cùng ngưỡng.
- **Căn chỉnh:** 5 điểm mốc của YuNet, đưa về mẫu 112×112 chuẩn ArcFace. Hàm `align_face` (`app/quality/measure.py`) là
  mã của app [Repo]. Không dùng bộ căn chỉnh của InsightFace.
- **Gom nhóm:** cùng logic `app/identity/cluster.py`. Ngưỡng **chỉnh riêng cho từng cấu hình trên tập chỉnh ngưỡng**,
  với điều kiện độ chính xác = 1,000.

Riêng **SFace** hiện dùng hàm căn chỉnh của OpenCV (`FaceRecognizerSF.alignCrop`). Trong phép so cố định, SFace được chạy
**hai cách**: căn chỉnh của OpenCV (như app đang làm) và căn chỉnh dùng chung. Cả hai đều được báo.

### 1.3 Dữ liệu

| Mã | Bộ ảnh | Nhãn | Trạng thái |
|---|---|---|---|
| D1 | Buổi chụp cosplay "20261025 - Aki" (439 NEF) | `scripts/calibration/labels_aki_20261025.py`: 46 look, 431 ảnh [Repo]. Nhãn theo **look** (trang phục), không theo người | Ảnh **không có trong repo** (riêng tư). Chạy trên máy chủ dự án, hoặc chủ dự án gửi một gói chỉ có vector |
| D2 | Ảnh **sự kiện** có nhãn người (cho kết luận riêng về Media) | **[Thiếu]** | Cần chủ dự án cung cấp |
| D3 | Lịch sử P/X và sao của các buổi chụp cá nhân | nằm trong dữ liệu phiên trên máy chủ dự án | Ở máy chủ dự án; số liệu chỉ ra dạng số |

**Tách tập trên D1:**
- Chia theo **look**, không theo ảnh lẻ: khoảng 40 % số look làm **tập chỉnh ngưỡng**, khoảng 60 % làm **tập chấm**.
- Look được chia theo thứ tự cố định: look thứ 1, 4, 7… vào tập chỉnh ngưỡng.
- Danh sách chia được ghi trong file, để ai chạy lại cũng ra cùng kết quả.

## 2. Phép so nhận mặt

### 2.1 Phép so A: chỉ đổi mô hình nhận mặt

Pipeline cố định như mục 1.2. Chỉ thay vector mặt.

| Cấu hình | Nhận mặt | Dáng người | Ghi chú |
|---|---|---|---|
| **F-SF** | SFace (hai cách căn chỉnh) | không | Tương đương 0.2.x |
| **F-AU** | AuraFace | không | Ứng viên |
| **F-SF+R** | SFace | YoutuReID | Tổ hợp dùng thương mại được của mã và trọng số |
| **F-AU+R** | AuraFace | YoutuReID | Ứng viên đầy đủ |

### 2.2 Phép so B: pipeline hoàn chỉnh so với số đã ghi trước đây

- Không chạy lại ArcFace. Baseline lấy từ số **đã ghi** trên D1 (`docs/IMPLEMENTATION_STATUS.md`, gói gỡ lỗi 3, vector do
  app tính ở 1600 px) [Repo]:
  - **ArcFace + ReID (0.3.0b3):** độ chính xác **1,000**, độ phủ **0,922**.
  - **SFace + màu trang phục:** **1,000 / 0,808**. Bản 0.2.x ghi 1,000 / 0,817.
- **Giới hạn:** số này đo trên **toàn bộ 431 ảnh**, ngưỡng đã chỉnh trên chính bộ đó. Vì vậy nó **lạc quan hơn** số của
  tập chấm mới. Khi báo cáo, mình ghi cả hai.
- **Muốn chạy lại ArcFace trên tập chấm mới** (để so công bằng) thì cần chủ dự án **xác nhận quyền dùng trọng số này cho
  việc đo nội bộ** **[Chờ duyệt: BM-1]**. Mặc định là **không chạy lại**.

### 2.3 Đo gì

**Trên tập chấm của D1:**
- **Độ chính xác** theo cặp ảnh.
- **Độ phủ** theo cặp ảnh.
- **Số gộp nhầm:** số nhóm chứa hơn một look thật.
- **Số tách nhầm:** số look thật bị chia thành nhiều nhóm.
- **Ảnh chưa gom được:** ảnh có người nhưng không vào nhóm nào.
- **Tỉ lệ dò được mặt** (giống nhau giữa các cấu hình, vì cùng YuNet). Ghi để biết giới hạn.

**Thời gian:**
- **Thời gian đầu cuối** của bước nhận diện chủ thể, trên **Windows/CUDA** (máy chủ dự án). Báo hai mốc: lần chạy đầu
  (chưa có cache) và lần chạy lại.
- **Thời gian mỗi khuôn mặt** của riêng mô hình nhận mặt.

**Media (D2):** báo **riêng**, cùng các số đo trên. Nếu chưa có D2 thì **không kết luận** cho Media.

### 2.5 Phần cải thiện của YoutuReID (báo riêng từng cặp)

**Hai cặp so:**
- **SFace** (F-SF) → **SFace + YoutuReID** (F-SF+R);
- **AuraFace** (F-AU) → **AuraFace + YoutuReID** (F-AU+R).

Trong mỗi cặp, mọi thứ khác giữ nguyên. Cả hai cấu hình "chỉ mặt" **vẫn có** mô tả màu trang phục; đây là mã của app,
không có trọng số. Ngưỡng của từng cấu hình chỉnh riêng trên tập chỉnh ngưỡng.

**Nhóm ảnh khó** (trên tập chấm của D1), xác định từng ảnh theo người chính:

| Nhóm | Cách xác định | Nguồn |
|---|---|---|
| **Quay lưng** | có người, YuNet **không** dò được mặt, và nhãn ghi "quay lưng" | nhãn bổ sung **[Thiếu]** |
| **Che mặt** | mặt nạ, kigurumi, mũ giáp, tay hoặc đạo cụ che; YuNet không dò được mặt, hoặc dò được với độ tin cậy thấp | nhãn bổ sung **[Thiếu]** |
| **Mặt quá nhỏ** | mặt dò được nhưng cao **< 40 px** trên ảnh 1600 px | tự động, từ số đo YuNet |
| **Mặt thấy rõ** | các ảnh còn lại | tự động |

**Cách lấy nhãn "quay lưng / che mặt":**
- Nhãn hiện tại (`labels_aki_20261025.py`) chỉ ghi look, chưa ghi các ý này.
- Đề xuất: app tự liệt kê các ảnh "có người nhưng không thấy mặt". Chủ dự án chỉ cần đánh dấu **Q** (quay lưng) hoặc
  **C** (che mặt) cho các ảnh đó, khoảng vài chục ảnh.
- Nếu chưa có nhãn bổ sung, hai nhóm này được báo gộp là **"không thấy mặt"**.

**Báo cáo cho mỗi cặp, theo từng nhóm ảnh và tổng:**

| Số đo | F-SF | F-SF+R | Chênh | F-AU | F-AU+R | Chênh |
|---|---|---|---|---|---|---|
| Độ phủ gom nhóm (theo cặp ảnh) | | | | | | |
| Gộp nhầm (số nhóm chứa > 1 look) | | | | | | |
| Tách nhầm (số look bị chia nhiều nhóm) | | | | | | |
| Ảnh chưa gom được | | | | | | |
| Thời gian bước nhận diện (Windows/CUDA, lần đầu / lần chạy lại) | | | | | | |
| Thời gian thêm do YoutuReID (mỗi người) | — | | | — | | |

- Mỗi ô ghi kèm **số mẫu**. Nhóm có **dưới 15 ảnh** ghi "chưa đủ mẫu".
- Số liệu được điền sau khi đo.

### 2.4 Tiêu chí đạt (đề xuất) [Chờ duyệt: BM-2]

| Chế độ | Đạt khi |
|---|---|
| Chụp cá nhân | độ chính xác **1,000** (0 gộp nhầm) **và** độ phủ ≥ **0,90** trên tập chấm **và** thời gian bước nhận diện ≤ **1,2 ×** bản hiện tại |
| Media sự kiện (D2) | 0 gộp nhầm giữa người đã đặt tên; độ phủ báo số, ngưỡng đặt sau khi có D2 |

## 3. Phép so bỏ TOPIQ

| Cấu hình | Thành phần điểm |
|---|---|
| **Q-BASE** (hiện tại) | phép đo kỹ thuật + TOPIQ + LAION. Dùng **điểm đã lưu** trong dữ liệu phiên; **không chạy lại TOPIQ** |
| **Q-TECH** | chỉ phép đo kỹ thuật của KiraPick: nét ở mắt, mắt nhắm / mở, mặt, sáng, bố cục |
| **Q-CL** | phép đo kỹ thuật + CLIP + LAION (W6, W7). **Điều kiện:** W7 đủ điều kiện dùng **[Chờ duyệt: BM-3]**, vì điều khoản dữ liệu của LAION còn chờ xác minh |

**Cách so:** tính lại điểm Q-TECH và Q-CL từ các phép đo đã lưu. Không cần chạy lại mô hình nào, trừ CLIP / LAION nếu ảnh
chưa có điểm.

**Đo gì** (trên D3, chỉ ra số):
- **Khớp với P/X lịch sử:** trong mỗi loạt ảnh (cùng chủ thể, cách nhau ≤ 3 giây), ảnh xếp đầu có phải ảnh bạn đã **P**
  không. Báo tỉ lệ cho Q-BASE, Q-TECH, Q-CL.
- **Thay đổi thứ tự:** hệ số tương quan thứ hạng (Spearman) giữa từng cấu hình mới và Q-BASE, trong từng chủ thể.
- **Ca sai đáng chú ý:** liệt kê **tên file**, không gửi ảnh. Gồm:
  - ảnh bạn đã **X** mà cấu hình mới đưa lên đầu;
  - ảnh bạn đã **P** mà cấu hình mới tụt xuống dưới cùng.

  Bạn tự mở ảnh xem trên máy.
- **Thời gian** chấm mỗi ảnh: có cache (CLIP đã tính) và chưa có cache.

**Tiêu chí đạt (đề xuất) [BM-2]:** tỉ lệ ảnh đầu loạt khớp P của cấu hình mới **không thấp hơn Q-BASE quá 5 điểm phần
trăm**.

## 4. Báo cáo sau khi đo: hai phần tách riêng

### 4.1 Kết luận đo (chỉ về chất lượng và tốc độ)

- Bảng mục 2.3, mục 2.5 và mục 3 cho từng cấu hình, kèm số mẫu.
- **Bằng chứng:** mã commit của máy đo, log Windows/CUDA, file JSON chỉ có số, danh sách "nạp khi chạy" có SHA-256.
- Phần này **không** kèm đề xuất đóng gói.

### 4.2 Đề xuất đóng gói (quyền dùng và phân phối từng file)

**Kết quả xác minh YoutuReID (2026-11-06):**
- **opencv_zoo**: README ghi "All files in this directory are licensed under Apache 2.0 License". File LICENSE là văn bản
  Apache-2.0 nguyên mẫu, **không ghi tên người giữ bản quyền**, và **không nhắc tới trọng số hay dữ liệu**.
- **Nguồn gốc** (`ReID-Team/ReID_extra_testdata`, "Youtu ReID Baseline" của Tencent Youtu Lab): **không có giấy phép**,
  không nói gì về dùng thương mại.
- **Dữ liệu huấn luyện** theo README nguồn gồm Market-1501, DukeMTMC, CUHK03, MSMT17. Đây là các bộ dữ liệu **dành cho
  nghiên cứu**. DukeMTMC đã bị **rút khỏi phát hành** năm 2019 vì lý do quyền riêng tư.
- **Kết luận:** quyền dùng thương mại và phân phối YoutuReID **chưa rõ**. Mình **không đề xuất** giữ YoutuReID trong bản
  thương mại cho tới khi có căn cứ: Tencent Youtu xác nhận, hoặc chủ dự án chấp nhận rủi ro bằng văn bản.

**Vì quyền dùng chưa rõ, báo cáo luôn có thêm phần sau:**
- **Chất lượng của cấu hình chỉ dùng mặt** (F-SF, F-AU) trên **cùng tập ảnh**, đặt cạnh cấu hình có YoutuReID.
- **Danh sách ca sẽ cần gom thủ công** nếu bỏ YoutuReID: các look mà cấu hình "chỉ mặt" tách nhầm hoặc để ảnh chưa gom
  được, nhưng cấu hình có YoutuReID gom đúng. Danh sách ghi tên file và nhóm ảnh khó (quay lưng / che mặt / mặt nhỏ).
  App đã có công cụ gộp / tách tay, có hoàn tác.

**Bảng đề xuất đóng gói** (điền sau khi đo):

| Cấu hình | File phải có trong bộ cài | Quyền dùng thương mại | Quyền phân phối | Đề xuất |
|---|---|---|---|---|
| F-SF | YuNet, SFace | MIT / Apache-2.0 (dữ liệu: xem `docs/model-licenses.md`) | có | |
| F-AU | YuNet, file nhận mặt AuraFace | Apache-2.0 theo model card; **chờ xác minh file thật** | chờ xác minh | |
| F-SF+R | + YoutuReID | **chưa rõ** | **chưa rõ** | không đề xuất cho tới khi rõ |
| F-AU+R | + YoutuReID | **chưa rõ** | **chưa rõ** | không đề xuất cho tới khi rõ |
| ArcFace (hiện tại) | w600k_r50 | **không** (cần giấy phép InsightFace) | không | không dùng cho bản thương mại |

**Nếu không cấu hình nào đạt, các lựa chọn để chủ dự án quyết:**
- **(a)** SFace hoặc AuraFace "chỉ mặt", kèm số đo và danh sách ca gom tay;
- **(b)** như (a), cộng gom thủ công ở ca khó;
- **(c)** giữ ArcFace kèm giấy phép InsightFace.

Đổi cấu hình mặc định **chờ chủ dự án duyệt**.

## 5. Cách chạy (đề xuất)

- **Lệnh mới**, chỉ đọc, không dùng mạng, chỉ ghi số:
  ```
  KiraPick.exe --benchmark-models <thư mục buổi chụp> <report.json> --labels aki_20261025
  ```
  Lệnh này dùng lại cơ chế chụp dữ liệu an toàn của `--diagnose-grouping`, không mở file gốc ở chế độ ghi [Repo].
- **AuraFace:** chỉ có trong một **bản đo nội bộ**, không phải bản phát hành. File được tải một lần lúc build (cần mở
  mạng tới huggingface.co cho CI hoặc phiên làm việc **[Thiếu]**), rồi ghim SHA-256.

## 6. Đầu vào còn thiếu

1. **AuraFace:** tên file, revision và SHA-256 của file nhận mặt; xác nhận các file đi kèm là của InsightFace. Cần mở mạng
   tới **huggingface.co**.
2. **D1:** chủ dự án chạy bản đo trên máy mình (ảnh không rời máy), hoặc gửi gói chỉ có vector.
3. **D2:** một bộ ảnh **sự kiện** có nhãn người. Không có bộ này thì không kết luận cho Media.
3b. **Nhãn "quay lưng / che mặt"** cho các ảnh "có người không thấy mặt" của D1 (mục 2.5): chủ dự án đánh dấu, khoảng vài
    chục ảnh.
4. **D3:** chạy trên máy chủ dự án, nơi có lịch sử P/X.
5. **Điều khoản dữ liệu của LAION (W7):** cần xác minh, hoặc chủ dự án chấp nhận rủi ro (BM-3).
6. **Quyết định BM-1, BM-2, BM-3.**

## 7. Quyết định cần duyệt

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| **BM-0** | Duyệt kế hoạch đo này? | **Đã duyệt bốn cấu hình** (2026-11-06) |
| **BM-5** | Có chấp nhận rủi ro dùng YoutuReID trong bản thương mại không? | **Chưa đề xuất.** Quyết sau khi có số đo mục 2.5 và căn cứ quyền dùng |
| **BM-1** | Có chạy lại ArcFace trên tập chấm mới để so công bằng không (cần xác nhận quyền dùng cho việc đo nội bộ)? | Không. Dùng số đã ghi và ghi rõ giới hạn |
| **BM-2** | Tiêu chí đạt ở mục 2.4 và mục 3 | Đồng ý |
| **BM-3** | LAION (W7) có đủ điều kiện dùng cho Q-CL không? | Chấp nhận rủi ro như CLIP, hoặc chỉ đo Q-TECH |
| **BM-4** | Có mở mạng tới huggingface.co để lấy AuraFace cho bản đo nội bộ không? | Có (chỉ để tải một lần, rồi ghim SHA-256) |
