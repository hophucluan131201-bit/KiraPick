# Rà soát mô hình thay ArcFace và TOPIQ (2026-11-06)

**Yêu cầu của chủ dự án:** tìm mô hình **dùng thương mại được**, **tốt hơn và nhanh hơn** ArcFace (nhận mặt) và TOPIQ (chấm
thẩm mỹ / chất lượng). Lý do: chủ dự án có thu tiền khi chụp, cả chụp cá nhân lẫn sự kiện.

**Cách kiểm:** đọc trang GitHub / model card gốc, theo ba tiêu chí:
- giấy phép của **mã**, của **trọng số** và của **dữ liệu huấn luyện**;
- độ chính xác do tác giả công bố;
- tốc độ.

**Lưu ý:** chưa chạy thử mô hình nào trên ảnh của KiraPick. Mọi con số dưới đây là **số tác giả công bố**, chưa phải số đo
của mình.

## Kết luận ngắn

- **Không tìm thấy** mô hình nào vừa **tốt hơn và nhanh hơn** ArcFace / TOPIQ, vừa có **điều khoản thương mại rõ ràng** cho
  cả trọng số lẫn dữ liệu huấn luyện.
- Gần như mọi mô hình nhận mặt mạnh đều được huấn luyện trên MS1M / WebFace. Hai bộ dữ liệu này **chỉ cho nghiên cứu**, nên
  vướng cùng vấn đề với ArcFace.
- **Ứng viên thực tế nhất:**
  - **Nhận mặt:** **AuraFace** (trọng số Apache-2.0, tác giả nói huấn luyện trên "bộ dữ liệu thương mại"). Có thể **tốt hơn
    SFace** nhưng **kém ArcFace** khi mặt nghiêng.
  - **Chấm thẩm mỹ:** **bỏ TOPIQ**. Dùng **CLIP + LAION** (đã có trong app; CLIP bạn đã chấp nhận rủi ro) cộng các phép đo
    kỹ thuật app tự làm. Có thể thêm **NIMA** (Apache-2.0, rất nhanh nhưng yếu hơn).
- Muốn biết thật sự tốt hay không thì phải **đo trên buổi chụp mẫu** (mục 3).

## 1. Nhận mặt (thay ArcFace)

| Mô hình | Giấy phép mã / trọng số | Dữ liệu huấn luyện | Độ chính xác công bố (LFW / CFP-FP / AgeDB) | Tốc độ | Nhận xét |
|---|---|---|---|---|---|
| **ArcFace w600k_r50** (đang dùng) | Mã MIT; **trọng số chỉ cho nghiên cứu phi thương mại** | WebFace600K (nghiên cứu) | mạnh nhất trong bảng (tham chiếu) | ResNet-50, trung bình | **Không dùng thương mại được** |
| **AuraFace v1** (fal) | **Apache-2.0** (model card) | "bộ dữ liệu thương mại", **không nêu tên** | 99,65 / 95,19 / 96,10 | chưa rõ; dùng chung kiến trúc với InsightFace | **Ứng viên số 1.** Kém ArcFace rõ ở CFP-FP (mặt nghiêng) và AgeDB. Chỉ lấy phần nhận mặt; phần dò mặt và điểm mốc đi kèm là của InsightFace (phi thương mại) |
| **SFace** (OpenCV, đang có) | Apache-2.0 | không nêu | LFW ≈ 99,4 | rất nhanh | Đo trên KiraPick: gom đúng **81 %**, so với **92 %** của ArcFace + dáng người |
| **GhostFaceNets** | Mã MIT; trọng số không ghi giấy phép riêng | **MS1MV2 / MS1MV3** (nghiên cứu) | 99,73 / 96,83 / 98,0; IJB-C 94,9 | **nhanh, nhẹ** | Tốt và nhanh, nhưng **dữ liệu huấn luyện vướng giống ArcFace** |
| **dlib ResNet** | **CC0** (tác giả đưa vào phạm vi công cộng) | FaceScrub + VGG Face + ảnh thu thập từ mạng | LFW ≈ 99,38 | nhanh trên CPU | Giấy phép rõ nhất, nhưng **yếu hơn**; ngang SFace |
| **EdgeFace** (Idiap) | **CC BY-NC-SA** | — | — | rất nhanh | **Loại**: cấm thương mại |

## 2. Chấm thẩm mỹ / chất lượng (thay TOPIQ)

| Mô hình | Giấy phép | Dữ liệu huấn luyện | Độ chính xác công bố | Tốc độ | Nhận xét |
|---|---|---|---|---|---|
| **TOPIQ** (đang dùng) | **PolyForm Noncommercial**; bộ công cụ pyiqa cũng phi thương mại | AVA, KonIQ… (nghiên cứu) | mạnh (tham chiếu) | ResNet-50 | **Không dùng thương mại được** |
| **CLIP ViT-L/14 + đầu LAION** (đã có trong app) | CLIP: MIT, model card "ngoài phạm vi" (bạn **đã chấp nhận rủi ro**); đầu LAION: Apache-2.0 | LAION: điểm AVA và các bộ khác | chưa có số tác giả trên AVA để so | nặng (CLIP) nhưng **đã tính sẵn** cho mỗi ảnh | **Đề xuất làm điểm thẩm mỹ chính** khi bỏ TOPIQ; không tốn thêm thời gian |
| **NIMA** (idealo) | **Apache-2.0** | AVA (thẩm mỹ), TID2013 (kỹ thuật) | AVA SRCC **0,609** | **MobileNet, rất nhanh** | Nhanh, giấy phép rõ, nhưng **yếu hơn TOPIQ khá nhiều** (TOPIQ trên AVA cao hơn) |
| **MUSIQ** (Google) | trang mô hình **không ghi** giấy phép | AVA, KonIQ, SPAQ, PaQ2PiQ | — | trung bình | Chưa đủ căn cứ |
| **Phép đo kỹ thuật của KiraPick** | mã của app | — | — | nhanh | Nét ở mắt (ảnh gốc), mắt nhắm / mở, sáng, bố cục. Không cần TOPIQ |

## 3. Đề xuất: đo thử rồi mới đổi

1. **Nhận mặt:** đo **AuraFace** và **SFace + dáng người** trên buổi chụp mẫu đã có nhãn (431 ảnh của lần chẩn đoán gom
   nhóm), so với ArcFace. Báo:
   - tỉ lệ gom đúng;
   - số lần gộp nhầm;
   - thời gian mỗi ảnh.

   Nếu AuraFace đạt **≥ 90 % và không gộp nhầm** thì thay ArcFace. Nếu không, chọn giữa mức kém hơn của SFace hoặc giữ
   ArcFace.
2. **Thẩm mỹ:** tắt TOPIQ, so **danh sách ảnh app tự chọn** trước và sau với **các ảnh bạn đã P / X** trong lịch sử. Báo
   mức trùng. Thử thêm NIMA nếu cần.
3. **Điều kiện:**
   - Tải AuraFace cần mở mạng tới **huggingface.co** cho phiên làm việc này. Hiện bị chặn; mình sẽ đề nghị mở khi tới bước
     đo.
   - Đo cần một bản sao buổi chụp đã có nhãn. Ảnh chỉ dùng trên máy, không gửi đi đâu.

## Nguồn

- InsightFace (giấy phép mô hình): https://github.com/deepinsight/insightface, https://www.insightface.ai/
- AuraFace: https://huggingface.co/fal/AuraFace-v1 (đọc qua bản sao https://huggingface.co/imagent/auraface-onnx)
- GhostFaceNets: https://github.com/HamadYA/GhostFaceNets
- dlib models: https://github.com/davisking/dlib-models
- EdgeFace: https://huggingface.co/Idiap/EdgeFace-Base
- NIMA (idealo): https://github.com/idealo/image-quality-assessment
- MUSIQ: https://github.com/google-research/google-research/tree/master/musiq
- Các công cụ chấm chất lượng mã nguồn mở: https://www.forasoft.com/learn/video-quality/articles-vqm/open-source-no-reference-tools
- Nhận mặt và giấy phép: https://localai.io/docs/features/face-recognition/index.html
