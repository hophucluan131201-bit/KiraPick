# Kế hoạch đo trước khi đổi mô hình nhận mặt và chấm thẩm mỹ (bản 3, 2026-11-06)

- **Phạm vi:** nhánh `beta`, chỉ là tài liệu. Chưa tải trọng số mới, chưa chạy phép đo nào.
- **Cấu hình mô hình đang chạy giữ nguyên.**
- **Nguồn rà soát:** `docs/design/thay-the-arcface-topiq.md`.
- **Kết quả đo và đề xuất thay mô hình là hai tài liệu riêng** (mục 4).

**Quy ước:**
- **[Repo]**: đã xác minh trong repo.
- **[Thiếu]**: đầu vào chưa có.
- **[Chờ duyệt]**: chờ chủ dự án quyết.

## 0. Trạng thái phê duyệt

| Việc | Trạng thái |
|---|---|
| Giữ **bốn cấu hình** F-SF, F-AU, F-SF+R, F-AU+R **trong kế hoạch** | **Chủ dự án đã xác nhận** (2026-11-06) |
| Yêu cầu báo riêng phần cải thiện của YoutuReID từng cặp, nhất là ảnh quay lưng / che mặt / mặt nhỏ | **Chủ dự án đã yêu cầu** (2026-11-06) |
| Tách kết luận đo khỏi đề xuất đóng gói | **Chủ dự án đã yêu cầu** (2026-11-06) |
| Xác minh quyền dùng và phân phối YoutuReID trước khi đề xuất giữ nó trong bản thương mại | **Chủ dự án đã yêu cầu**; kết quả xác minh ở mục 1.2 |
| Duyệt **tiêu chí** đo (BM-2) | [Chờ duyệt] |
| **Tải** trọng số AuraFace, mở mạng tới huggingface.co (BM-4) | [Chờ duyệt] |
| **Chạy** phép đo các cấu hình chỉ dùng mặt (BM-0) | [Chờ duyệt] |
| **Chạy** hai phép đo `+R`, cần căn cứ dùng YoutuReID cho việc đo nội bộ (BM-6) | [Chờ duyệt]; **đang chờ** |
| Chạy lại ArcFace (BM-1) | [Chờ duyệt]; đề xuất: không |
| LAION trong phép so thẩm mỹ (BM-3) | [Chờ duyệt] |
| **Thay cấu hình mặc định** (BM-7) | [Chờ duyệt]; chỉ trình sau khi có kết quả đo |
| **Đóng gói** để phân phối (BM-8) | [Chờ duyệt]; chỉ trình sau khi có kết quả đo và căn cứ quyền phân phối |

## 1. Đầu vào của từng cấu hình

### 1.1 Trọng số

| Mã | Thành phần | File | Nguồn / revision | SHA-256 | Giấy phép | Nạp khi đo | Có trong bộ cài hiện tại |
|---|---|---|---|---|---|---|---|
| W1 | Dò mặt YuNet 2023mar | `face_detection_yunet_2023mar.onnx` | opencv_zoo@48b10fa [Repo] | `8f2383e4…52fa4` [Repo] | MIT; dữ liệu WIDER FACE (chỉ cho nghiên cứu) | mọi cấu hình | có |
| W2 | Nhận mặt SFace 2021dec | `face_recognition_sface_2021dec.onnx` | opencv_zoo@48b10fa [Repo] | `0ba9fbfa…79` [Repo] | Apache-2.0; dữ liệu không công bố | F-SF, F-SF+R | có |
| W3 | Nhận mặt AuraFace v1 | file nhận mặt trong `fal/AuraFace-v1`: tên file, revision **[Thiếu]** | huggingface.co/fal/AuraFace-v1 | **[Thiếu]** | model card: Apache-2.0; dữ liệu "thương mại", không nêu tên | F-AU, F-AU+R | không |
| W3x | Dò mặt / căn chỉnh / tuổi-giới đi kèm AuraFace | các file khác trong repo đó | như W3 | — | theo bản sao `imagent/auraface-onnx`: mô hình InsightFace, **phi thương mại** | **không tải, không nạp** | không |
| W4 | Dáng người YoutuReID | `person_reid_youtu_2021nov.onnx` | opencv_zoo@48b10fa [Repo] | `05796833…580d` [Repo] | xem mục 1.2 | F-SF+R, F-AU+R (**đang chờ**) | có |
| W5 | ArcFace w600k_r50 | `w600k_r50.onnx` | InsightFace v0.7 [Repo] | `4c06341c…9e43` [Repo] | **phi thương mại** | **không chạy lại** (BM-1) | có (Chụp cá nhân) |
| W6 | CLIP ViT-L/14 ảnh | `clip_l14_image.onnx` (chuyển lúc build) | OpenAI ViT-L-14.pt [Repo] | theo `.sha256` [Repo] | MIT (mã); model card "ngoài phạm vi"; chủ dự án đã chấp nhận rủi ro (2026-10-28) | Q-CL | có |
| W7 | Đầu LAION aesthetic | `laion_aesthetic.onnx` | improved-aesthetic-predictor [Repo] | theo `.sha256` [Repo] | Apache-2.0; điều khoản dữ liệu **chờ xác minh** | Q-CL (BM-3) | có |
| W8 | TOPIQ ×3 | `topiq_*.onnx` | IQA-PyTorch [Repo] | theo `.sha256` [Repo] | **PolyForm Noncommercial** | **không chạy lại**; dùng điểm đã lưu | có |

**Hai danh sách tách riêng:**
- **"Nạp khi đo":** máy đo ghi tên file và SHA-256 của từng file thực sự được mở.
- **"Có trong bộ cài":** lấy từ `scripts/media_model_report.py` [Repo].

### 1.2 Căn cứ dùng: đo nội bộ khác với đóng gói / phân phối

| Trọng số | Căn cứ để **đo nội bộ** | Căn cứ để **đóng gói / phân phối** |
|---|---|---|
| YuNet, SFace | Giấy phép MIT / Apache-2.0 của opencv_zoo cho phép dùng và đánh giá | Cùng giấy phép; dữ liệu huấn luyện ghi ở `docs/model-licenses.md` |
| AuraFace (W3) | Model card ghi Apache-2.0, **chưa đọc được file thật** (huggingface.co bị chặn). **Có căn cứ khi tải xong**, đã ghim revision và SHA-256, đọc được giấy phép đi kèm (BM-4) | Chờ xác minh file thật; dữ liệu "thương mại" không nêu tên |
| **YoutuReID (W4)** | **Chưa đủ căn cứ.** Xem phần xác minh dưới bảng. Vì vậy hai phép đo **F-SF+R** và **F-AU+R** đang **chờ** BM-6 | **Chưa rõ.** Không đề xuất đóng gói cho bản thương mại |
| ArcFace (W5) | Giấy phép chỉ cho nghiên cứu phi thương mại. **Không chạy lại** (BM-1) | **Không**, trừ khi có giấy phép InsightFace cho đúng trọng số này |

**Xác minh YoutuReID (2026-11-06):**
- **opencv_zoo:** README ghi "All files in this directory are licensed under Apache 2.0 License". Nhưng file LICENSE là văn
  bản mẫu, **không ghi người giữ bản quyền** và **không nhắc tới trọng số**.
- **Nguồn gốc** (`ReID-Team/ReID_extra_testdata`, Tencent Youtu Lab): **không có giấy phép**.
- **Dữ liệu huấn luyện:** Market-1501, DukeMTMC, CUHK03, MSMT17. Đều là bộ dữ liệu nghiên cứu; DukeMTMC đã bị **rút khỏi
  phát hành** năm 2019.
- **BM-6:** chủ dự án quyết có coi dòng Apache-2.0 của opencv_zoo là đủ căn cứ để **đo nội bộ** hay không.
  - Nếu **không**, hai phép đo `+R` không chạy. Mình chỉ trình **phương án đo chỉ dùng mặt** (F-SF, F-AU), kèm danh sách
    ca cần gom tay.

### 1.3 Pipeline dùng chung

Mọi cấu hình nhận mặt dùng chung ba thành phần:
- **Dò mặt:** YuNet, cùng ngưỡng.
- **Căn chỉnh:** 5 điểm mốc, đưa về mẫu 112×112, bằng hàm `align_face` của app [Repo].
  - SFace báo thêm một kết quả với căn chỉnh `alignCrop` của OpenCV, như app đang làm.
- **Gom nhóm:** `app/identity/cluster.py`, cộng mô tả màu trang phục (mã của app, không có trọng số).
  - Ngưỡng chỉnh riêng cho từng cấu hình **trên tập chỉnh ngưỡng**, với điều kiện độ chính xác = 1,000.

## 2. Hai mục tiêu đánh giá tách riêng

| | **D1: gom theo look (Chụp cá nhân)** | **D2: gom cùng người (Media sự kiện)** |
|---|---|---|
| Câu hỏi | Các ảnh cùng **look** (cùng người, cùng trang phục) có vào cùng một nhóm không? | Các ảnh cùng **một người**, kể cả khác hoạt động, có vào cùng một nhóm không? |
| Bộ ảnh | "20261025 - Aki", 439 NEF; nhãn 46 look / 431 ảnh trong `scripts/calibration/labels_aki_20261025.py` [Repo] | **[Thiếu]**: ảnh sự kiện có nhãn người |
| Nơi chạy | Máy chủ dự án (ảnh không rời máy), hoặc gói chỉ có vector | Như D1 |
| Kết luận | Chỉ cho Chụp cá nhân | Chỉ cho Media; **không suy từ D1** |

**Chia tập** (cho cả D1 và D2):
- Chia theo **look** (D1) hoặc theo **người** (D2), không theo ảnh lẻ.
- Khoảng 40 % làm **tập chỉnh ngưỡng**, khoảng 60 % làm **tập chấm**, theo thứ tự cố định ghi trong file.

### 2.1 Nhãn ảnh khó: ghi theo nội dung, báo riêng kết quả dò mặt

**Nhãn nội dung** do chủ dự án ghi theo **những gì nhìn thấy trong ảnh** (người chính), không theo kết quả của AI:
- **Q:** quay lưng;
- **C:** mặt bị che (mặt nạ, kigurumi, mũ giáp, tay, đạo cụ);
- **N:** mặt nhỏ (nhìn thấy mặt nhưng rất nhỏ trong khung);
- **R:** mặt rõ.

**Ảnh cần ghi nhãn** (để không lệch theo kết quả dò mặt):
- mọi ảnh trên tập chấm mà YuNet **không** dò được mặt, hoặc mặt cao dưới 60 px trên ảnh 1600 px;
- cộng **một mẫu ngẫu nhiên 10 %** các ảnh còn lại, để kiểm tra xem nhãn R có đúng không.
- Ước tính vài chục đến khoảng một trăm ảnh **[Thiếu]**.

**Báo riêng kết quả dò mặt** cho từng nhóm nội dung: số ảnh YuNet dò được mặt, số ảnh không dò được, và chiều cao mặt
trung vị. Kết quả này giống nhau ở mọi cấu hình, vì cùng YuNet.

### 2.2 Số đo

**Trên tập chấm, cho từng cấu hình, chia theo nhóm Q / C / N / R và tổng, mỗi số kèm số mẫu (dưới 15 thì ghi "chưa đủ
mẫu"):**
- độ chính xác và độ phủ theo cặp ảnh;
- **gộp nhầm:** số nhóm chứa hơn một look (D1) hoặc hơn một người (D2);
- **tách nhầm:** số look / người bị chia thành nhiều nhóm;
- **ảnh chưa gom được**;
- **thời gian:**
  - bước nhận diện, đầu đến cuối, trên Windows/CUDA, lần đầu và lần chạy lại;
  - thời gian mỗi khuôn mặt;
  - thời gian YoutuReID mỗi người.

### 2.3 Phần cải thiện của YoutuReID (chỉ khi BM-6 cho phép)

| Cặp | So | Trên cùng |
|---|---|---|
| SFace | F-SF → F-SF+R | tập chấm, theo nhóm Q / C / N / R và tổng |
| AuraFace | F-AU → F-AU+R | như trên |

- **Báo chênh lệch:** độ phủ, gộp nhầm, tách nhầm, ảnh chưa gom được, thời gian.
- **Nếu BM-6 = không:** bảng này ghi "chờ"; báo cáo chỉ có F-SF và F-AU, kèm **danh sách ca cần gom tay**, tức các ảnh
  nhóm Q / C / N bị tách nhầm hoặc chưa gom được.

### 2.4 Baseline lịch sử (chỉ để tham khảo)

- Số **đã ghi** trên D1 (`docs/IMPLEMENTATION_STATUS.md`, gói gỡ lỗi 3) [Repo]:
  - ArcFace + ReID (0.3.0b3): độ chính xác 1,000, **độ phủ 0,922**;
  - SFace + màu trang phục: 1,000 / 0,808.
- **Giới hạn khi so:**
  - đo trên **toàn bộ** 431 ảnh, không phải tập chấm mới;
  - ngưỡng chỉnh **trên chính bộ đó**, nên số lạc quan;
  - phiên bản app và vector khác (bản 0.3.0b3, vector ở 1600 px);
  - không có số tách nhầm và thời gian theo cách đo mới.
- Vì vậy **92,2 % là số lịch sử có giới hạn so sánh**. Không dùng làm ngưỡng đạt; chỉ đặt cạnh kết quả mới để tham khảo.

### 2.5 Tiêu chí (BM-2, chờ chủ dự án chốt)

| Loại | Chụp cá nhân (D1) | Media (D2) |
|---|---|---|
| **Ngưỡng chấp nhận chất lượng** | 0 gộp nhầm; độ phủ ≥ **0,90** trên tập chấm | 0 gộp nhầm giữa người đã đặt tên; ngưỡng độ phủ đặt sau khi có D2 |
| **Ngưỡng chấp nhận tốc độ** | thời gian bước nhận diện **≤ 1,2 ×** bản hiện tại (3.0.0), cùng máy, cùng bộ ảnh | như D1 |
| **Mục tiêu tốc độ** (không phải điều kiện đạt) | **nhanh hơn** bản hiện tại; báo mức nhanh / chậm theo % | như D1 |

- **Thời gian của bản hiện tại** lấy từ log `kirapick.log` của bản 3.0.0 chạy trên cùng buổi chụp trên máy chủ dự án.
  Cách này không phải chạy lại ArcFace **[Thiếu]**: cần log đó.

## 3. Phép so bỏ TOPIQ

| Cấu hình | Thành phần điểm |
|---|---|
| **Q-BASE** (hiện tại) | đo kỹ thuật + TOPIQ + LAION, dùng **điểm đã lưu**; không chạy lại TOPIQ |
| **Q-TECH** | chỉ phép đo kỹ thuật của KiraPick |
| **Q-CL** | đo kỹ thuật + CLIP + LAION; chờ BM-3 |

- **Dữ liệu:** lịch sử P/X trên máy chủ dự án; chỉ ra số và tên file.
- **Số đo:**
  - tỉ lệ ảnh xếp đầu loạt (cùng chủ thể, cách nhau ≤ 3 giây) trùng ảnh đã **P**;
  - tương quan thứ hạng với Q-BASE;
  - danh sách ca sai đáng chú ý: ảnh **X** lên đầu, ảnh **P** xuống cuối;
  - thời gian chấm, có cache và chưa có cache.
- **Tiêu chí (BM-2):** tỉ lệ trùng **P** không thấp hơn Q-BASE quá 5 điểm phần trăm.

## 4. Hai tài liệu kết quả tách riêng

1. **Báo cáo đo** (`docs/benchmark/ket-qua-*.md`):
   - các bảng mục 2 và 3, kèm số mẫu;
   - mã commit, log Windows/CUDA, file JSON chỉ có số, danh sách "nạp khi đo" có SHA-256;
   - **không có đề xuất thay mô hình**.
2. **Đề xuất thay mô hình mặc định và đóng gói** (tài liệu riêng, viết **sau** báo cáo đo):
   - cho từng cấu hình: chất lượng (dẫn từ báo cáo đo), tốc độ, file phải có trong bộ cài, căn cứ dùng thương mại và
     phân phối (mục 1.2), phần còn thiếu bằng chứng;
   - **lựa chọn nếu không cấu hình nào đạt:** (a) SFace hoặc AuraFace chỉ dùng mặt, kèm danh sách ca gom tay; (b) như (a)
     cộng gom thủ công ở ca khó; (c) giữ ArcFace kèm giấy phép InsightFace.
   - Thay mặc định (BM-7) và đóng gói (BM-8) chờ chủ dự án duyệt.

## 5. Điều kiện còn thiếu để chạy từng cấu hình

| Cấu hình | Có thể chạy khi |
|---|---|
| **F-SF** (D1) | BM-0, BM-2; chủ dự án chạy trên máy mình (hoặc gửi gói vector); nhãn Q / C / N / R; log thời gian bản 3.0.0 |
| **F-AU** (D1) | Như F-SF, **cộng** BM-4 (mở huggingface.co, tải, ghim SHA-256, đọc giấy phép file thật) |
| **F-SF+R** (D1) | Như F-SF, **cộng** BM-6 |
| **F-AU+R** (D1) | Như F-AU, **cộng** BM-6 |
| Mọi cấu hình trên **D2** | Như trên, **cộng** bộ ảnh sự kiện có nhãn người |
| **Q-TECH** | BM-0, BM-2; lịch sử P/X trên máy chủ dự án |
| **Q-CL** | Như Q-TECH, **cộng** BM-3 |

## 6. Quyết định cần chủ dự án chốt

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| **BM-0** | Cho chạy phép đo các cấu hình **chỉ dùng mặt** (F-SF, F-AU) và Q-TECH? | Có |
| **BM-1** | Chạy lại ArcFace? | Không; dùng số lịch sử, ghi rõ giới hạn |
| **BM-2** | Tiêu chí ở mục 2.5 và mục 3, gồm **ngưỡng chấp nhận tốc độ 1,2×** và **mục tiêu "nhanh hơn"** tách riêng | Đồng ý |
| **BM-3** | Dùng LAION trong Q-CL? | Chấp nhận rủi ro như CLIP, hoặc chỉ đo Q-TECH |
| **BM-4** | Mở huggingface.co, tải file nhận mặt AuraFace cho máy đo nội bộ? | Có |
| **BM-6** | Coi dòng Apache-2.0 của opencv_zoo là đủ căn cứ để **đo nội bộ** YoutuReID (không phải đóng gói)? | Chủ dự án quyết; nếu không, chỉ đo chỉ dùng mặt |
| **BM-7** | Thay cấu hình mặc định | Trình sau khi có báo cáo đo |
| **BM-8** | Đóng gói để phân phối | Trình sau khi có báo cáo đo và căn cứ phân phối |
