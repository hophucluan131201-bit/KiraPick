# Kết quả test ngắn REG-3 trên máy chủ dự án (2026-11-09)

## A. Đo nhập ảnh (bước 2)

Nguồn: `KiraPick-do-nhap.zip` của chủ dự án (bước 2, `do-nhanh`).

| | |
|---|---|
| Máy | Core i7-10750H, 32 GB, Windows 11 Pro, Defender realtime **bật** |
| Ổ ảnh | C:, NVMe SSD, còn trống 50 GB |
| Thư mục | **236 file, toàn bộ là JPEG** (3 137 MB, khoảng 13 MB một ảnh); không có RAW |
| Commit | 3.0.0 `e2fec9d` · đã thử `d45548b` · Beta `743b76a` |
| Cache | **ấm**: máy đã bật 43 phút, không đo ngay sau khi khởi động lại |
| Thư mục ảnh sau khi đo | `unchanged=True` (không bị sửa) |

## Bảng 2 (đã điền từ file)

| Bản | Chế độ | Lần | Thẻ ảnh / cặp | Ảnh đầu (s) | Mở/đánh dấu được (s) | Nhập xong (s) |
|---|---|---|---|---|---|---|
| 3.0.0 | cá nhân | mở đầu | 236 / 0 | 1,57 | 1,60 | **25,10** |
| 3.0.0 | cá nhân | chạy lại | 236 / 0 | 0,00 | 0,03 | 0,08 |
| Đã thử | cá nhân | mở đầu | 236 / 0 | 1,59 | 1,62 | **23,76** |
| Đã thử | **Media** | mở đầu | 236 / 0 | **24,17** | **24,17** (lưới trống tới khi nhập xong) | 24,17 |
| Beta đã sửa | cá nhân | mở đầu | 236 / 0 | 1,57 | 1,61 | **24,36** |
| Beta đã sửa | **Media** | mở đầu | 236 / 0 | **1,57** | **1,63** | 24,30 |
| (mọi bản) | | chạy lại | 236 / 0 | 0,00 | 0,02–0,04 | 0,08–0,10 |

## Đọc kết quả

1. **Chụp cá nhân không chậm hơn 3.0.0.** Thời gian nhập xong là 25,1 s (3.0.0), 23,8 s (bản đã thử) và 24,4 s (Beta
   đã sửa). Chênh nhau dưới 1,5 s, tức khoảng 5 %, và bản Beta không chậm hơn. Cả ba bản đều cho thao tác sau khoảng
   1,6 s.
2. **Đã thấy đúng chỗ chậm của bản đã thử: cửa sổ Media.** Trong bản đó, lưới trống suốt **24 s**, tới khi nhập xong mới
   có ảnh để mở hay đánh dấu. Nhiều khả năng đây chính là chỗ anh thấy chậm. Bản đã sửa cho thao tác sau **1,6 s**, như
   3.0.0. Tổng thời gian nhập không đổi.
3. **Mất thời gian ở đâu.** Khoảng 98 % thời gian nằm ở bước đọc ảnh và tạo ảnh thu nhỏ: khoảng 0,1 s một ảnh JPEG
   13 MB, như nhau ở cả ba bản. App đã giải mã JPEG ở cỡ nhỏ khi tạo ảnh thu nhỏ. Defender bật cũng làm mỗi lần đọc file
   chậm hơn một chút.
4. **Mở lại** cùng thư mục: dưới 0,1 s ở mọi bản.

## Chưa đo được trong lượt này

- **Ghép RAW+JPEG:** thư mục chỉ có JPEG, nên số cặp là 0 và tốc độ ghép cặp chưa đo trên máy anh.
- **Cache lạnh:** máy đã bật 43 phút trước khi đo.

Cả hai mục đều làm được bằng **một lượt bổ sung ngắn**: dùng một thư mục có cả RAW (NEF) và JPEG cùng tên, khởi động lại
máy, rồi chạy `do-nhanh` ngay. Lượt này tuỳ anh: kết quả hiện có đã trả lời câu hỏi "Beta có chậm hơn 3.0.0 không" cho
JPEG.

## B. Luồng Media theo 3.0.0 (bước 3, bảng 3)

Bản: Beta `743b76a`, chạy từ mã nguồn trên profile test riêng, sự kiện `KIEM MEDIA`. Chủ dự án tự thao tác trên máy của
mình.

| Thao tác | Kết quả của chủ dự án | Bằng chứng |
|---|---|---|
| Chọn / loại (P, X; U bỏ) | Đạt | CI + chủ dự án |
| Sao (1–5, 0 xoá) | Đạt | CI + chủ dự án |
| Yêu thích (F) | Đạt | CI + chủ dự án |
| So sánh 2–4 ảnh (C, Esc) | Đạt | CI + chủ dự án |
| Xoay khi xem; ảnh gốc mở bằng phần mềm khác không bị xoay | Đạt | CI + chủ dự án |
| Hoàn tác Ctrl+Z sau P, sao, nhãn | Đạt | CI + chủ dự án |
| Xuất bản sao vào `xuat\kiem-media`; ảnh gốc còn nguyên | Đạt | CI + chủ dự án |
| ✂ Tách khoảnh khắc rồi Ctrl+Z | Đạt | CI + chủ dự án |
| Gộp khoảnh khắc rồi Ctrl+Z | Đạt | CI + chủ dự án |
| Phím 0–5 / Alt+1–5 khi đang gõ ô tìm tên file: không đổi sao hay nội dung | Đạt | CI + chủ dự án |

**10/10 đạt.** Luồng Media kế thừa 3.0.0 đã có xác nhận trên máy thật.

## C. Còn chờ

- Bước 4: thử A/B gợi ý ảnh gần trùng (`KiraPick-thu-phan-loai.zip` và bảng 4).
- Tuỳ chọn: một lượt đo nhập bằng thư mục có RAW+JPEG, đo ngay sau khi khởi động lại máy (cache lạnh).
- Nghiệm thu bốn nhóm phân loại Media: mục riêng, chưa bắt đầu.
