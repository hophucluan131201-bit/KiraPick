# Media — rà lại thiết kế phân loại: phương án trình chủ dự án (bản nháp, 2026-11-07)

**Trạng thái:** trình để chủ dự án chốt. **Chưa sửa logic phân loại** cho tới khi có quyết định.

**Giới hạn của bản trình này (nói thẳng):** máy phát triển **không có ảnh sự kiện thật**. Trang album VNNIC bị chặn mạng;
ảnh mẫu trong repo là ảnh cosplay chân dung. Vì vậy bảng "app làm được gì" dưới đây dựa trên **mã hiện tại + test ảnh
tổng hợp**, chưa phải trên ảnh sự kiện. Mục 5 là cách rà trên ảnh thật **tại máy chủ dự án**, bằng công cụ đã có, trước
khi chốt.

---

## 1. Hiện trạng (bản 3.0.1b1)

| Bước | App tự làm | Người dùng làm | Căn cứ |
|---|---|---|---|
| Chia khoảnh khắc | Theo **khoảng nghỉ ≥ 5 phút** của giờ đã chỉnh (không có CLIP: không biết "đổi cảnh") | Tách / gộp / đổi tên; ⚠ lệch giờ: Chuyển / Giữ | MT-F1 |
| Cỡ cảnh | Toàn / Trung / Cận từ **tỉ lệ mặt** (có mặt) hoặc **khung người** (không mặt: chỉ Toàn hoặc Chưa xác định) | Sửa sai: Alt+T / U / C | §5, ngưỡng chưa chỉnh trên ảnh thật |
| Lỗi nét | Out nét / Trật nét trên ảnh gốc | Q / W / R | §6, chưa chấm trên ảnh thật |
| Nội dung | **Không** (CLIP pending) | Gán tay Alt+1–5, cho nhiều ảnh một lúc | CT-F1/F2 |
| Tên booth | Gợi ý trong cùng khoảnh khắc | Đặt tên | BT-F1 |
| Chọn ảnh giao khách | **Không** (UX-2 = chưa) | P / X như 3.0.0 | — |

**Điểm yếu đoán trước được (cần ảnh thật để xác nhận):**
- Sự kiện liền mạch (hội nghị nhiều phiên không nghỉ 5 phút) → **một khoảnh khắc rất lớn**; người dùng phải tự tách.
- Ảnh sân khấu xa: mặt nhỏ < 24 px → không dò được mặt → nhiều ảnh **Chưa xác định** hoặc Toàn.
- Ảnh đông người (khán phòng): "chủ thể chính" là người lớn nhất, có thể là khán giả gần máy.
- Màn LED có viền mờ, phản sáng: luật loại LED chỉ thử trên ảnh tổng hợp.
- Nội dung (sân khấu / booth / sản phẩm) **hoàn toàn gán tay**: nhiều thao tác nhất của luồng Media.

## 2. Ba phương án

### A. Giữ thứ tự hiện tại, giảm thao tác (đề xuất)
1. Nhập → app chia khoảnh khắc + cỡ cảnh + nét (như hiện nay).
2. **Rà theo khoảnh khắc:** mỗi lần làm việc với **một** khoảnh khắc (dải khoảnh khắc là bước chính, không phải bộ lọc phụ):
   - đặt tên khoảnh khắc + **nội dung cho cả khoảnh khắc bằng một phím** (ví dụ cả "Khai mạc" là Sân khấu), rồi chỉ sửa
     ngoại lệ;
   - cỡ cảnh: xem ba cột Toàn / Trung / Cận của khoảnh khắc đó; sửa ảnh sai bằng kéo hoặc Alt+T/U/C;
   - cảnh báo nét: một bộ lọc "có cảnh báo" trong khoảnh khắc; Q bỏ cảnh báo, X loại.
3. P / X như 3.0.0; xuất theo khoảnh khắc.
- **App tự làm:** chia khoảnh khắc, cỡ cảnh, cảnh báo nét, gợi ý nội dung **kế thừa** từ khoảnh khắc (không cần AI).
- **Người xác nhận / sửa:** ranh giới khoảnh khắc, nội dung của khoảnh khắc, ảnh sai cỡ cảnh, cảnh báo nét sai.
- **Thay đổi logic:** thêm "nội dung theo khoảnh khắc" (gán một lần, ảnh trong khoảnh khắc nhận nhãn ở trạng thái
  "theo khoảnh khắc", sửa riêng được). Không cần mô hình mới.

### B. Khoảnh khắc trước, nhãn sau
Người dùng **dựng dòng thời gian trước** (tách / đặt tên khoảnh khắc trên một màn hình dải thời gian có ảnh thu nhỏ), rồi mới
lọc. App chỉ gợi ý ranh giới (khoảng nghỉ + đổi nguồn máy + đổi cỡ cảnh đột ngột).
- Ít sai ranh giới hơn với sự kiện liền mạch; nhưng thêm một bước bắt buộc trước khi lọc.

### C. Tối giản cho bản thử
Ẩn cỡ cảnh và lỗi nét AI cho tới khi chấm trên ảnh thật đạt §11; chỉ giữ khoảnh khắc theo giờ + nhãn tay + P/X + xuất.
- Ít rủi ro "AI sai làm chậm người dùng"; nhưng Media gần như chỉ là 3.0.0 có thêm thư mục theo khoảnh khắc.

## 3. Đo thời gian và số thao tác tiết kiệm

**Mốc so sánh:** cùng một sự kiện, cùng người, hai cách:
- **Cách cũ (3.0.0):** P / X trong Chụp cá nhân, rồi tự chép ảnh P vào thư mục theo phần chương trình (Explorer).
- **Cách mới (Media, phương án được chọn):** tới khi có thư mục giao khách theo khoảnh khắc.

**Số đo** (app tự ghi, chỉ số, không tên ảnh):
| Số đo | Cách lấy |
|---|---|
| Thời gian tới khi lưới thao tác được / nhập xong / phân tích xong | đồng hồ trong app (đã đo trên máy phát triển, xem báo cáo) |
| Thời gian làm việc thực (từ mở sự kiện tới xuất xong) | dấu thời gian trong nhật ký |
| Số thao tác theo loại: P/X, sao, nhãn cỡ cảnh, nhãn nội dung, tách / gộp / đổi tên khoảnh khắc, Ctrl+Z | đếm dòng nhật ký `media action: kind=…` (cần thêm, giống GRP-1) |
| Tỉ lệ AI đúng (cỡ cảnh, nét, ranh giới khoảnh khắc) | 🏷 Dán nhãn mẫu + `--media-score` (đã có) |
| Số ảnh AI xếp sai mà người phải sửa | = số lần Alt+T/U/C, Q/W/R trên ảnh AI đã gợi ý (từ nhật ký) |

**Chỉ tiêu đề xuất để chủ dự án chốt:** Media đáng dùng khi tổng thời gian từ nhập tới thư mục giao khách **ngắn hơn ít
nhất 30 %** so với cách cũ trên cùng sự kiện, và số thao tác sửa nhãn AI **ít hơn** số thao tác AI tiết kiệm được.

## 4. Việc kỹ thuật cần cho mục 3 (chưa làm, chờ duyệt cùng phương án)
- Một dòng nhật ký cho mỗi thao tác Media (`kind` + dấu thời gian, không tên ảnh), và `KiraPick.exe --media-counts`
  (giống `--grp1-counts`) để in bảng số.

## 5. Rà trên ảnh sự kiện thật (tại máy chủ dự án, trước khi chốt)
1. Chọn **một** sự kiện thật 300–500 ảnh, tốt nhất từ 2 máy, có sân khấu + booth + khán phòng.
2. Mở bằng KiraPick Beta → Media → nhập → 🧠 Phân tích. Ghi lại ba mốc thời gian (lưới, nhập xong, phân tích xong).
3. 🏷 Dán nhãn mẫu 100–150 ảnh (cỡ cảnh, nét, B ranh giới khoảnh khắc, nội dung) → `--media-score` → gửi `cham.json`.
4. Ghi tay 5 câu: khoảnh khắc nào app chia sai (thừa / thiếu); loại ảnh nào cỡ cảnh hay sai; cảnh báo nét có làm phiền
   không; nhãn nội dung nào dùng nhiều nhất; bước nào mất thời gian nhất.
5. Gửi lại: tôi tổng hợp thành bảng "app tự làm được / người phải sửa" thật, rồi chủ dự án chốt A / B / C.

## 6. Cần chủ dự án quyết định
1. Chọn phương án **A**, **B** hay **C** (hoặc chờ kết quả mục 5 rồi chọn).
2. Duyệt mục 4 (đếm thao tác trong nhật ký, chỉ số).
3. Chỉ tiêu ở mục 3 (≥ 30 % thời gian) có hợp lý không.
