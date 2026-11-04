# Thử bản RC KiraPick Beta CUDA 3.0.0b1a — từ đầu đến cuối

Đây là bản ứng viên beta (RC), không phải bản phát hành. Bước nào ra khác mô tả dưới đây thì **dừng lại**, chụp màn
hình và gửi mình.

## 0. Chuẩn bị

- **Một buổi chụp thật đã sao lưu.**
  - Chép cả thư mục ảnh của buổi chụp (RAW + JPEG) sang `D:\RC\BuoiChup`.
  - Chỉ làm việc trên bản chép này. Bản gốc để yên ở chỗ khác.
  - KiraPick không tự mở thư mục nào của bạn.
- **Một thư mục trống để xuất:** `D:\RC\Xuat`.
- **Sao lưu dữ liệu KiraPick.**
  - Đóng mọi KiraPick trước.
  - Chạy lệnh dưới. Cuối cùng phải có dòng xanh "SHA-256: khớp".
  - Ghi lại đường dẫn bản sao lưu.
  ```powershell
  powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
  ```
- **Tải và kiểm tra mã:** xem mục "Tải về" ở cuối file này.
- **Cài:**
  - Chạy `KiraPick-Beta-CUDA-3.0.0b1a-Setup.exe`.
  - SmartScreen hiện ra thì bấm **More info → Run anyway**, chỉ khi mã đã khớp và màn hình ghi "Unknown publisher".
  - Start Menu phải có thêm **KiraPick Beta CUDA**. Các lối tắt KiraPick cũ vẫn còn.

## 1. Bảng kiểm tra

Ghi **Đạt** hoặc **Không** cho từng dòng, ghi chú nếu có.

| # | Làm | Phải thấy | Đạt? |
|---|---|---|---|
| 1 | Mở **KiraPick Beta CUDA** → 📂 Nhập ảnh → `D:\RC\BuoiChup` | Tiêu đề ghi 3.0.0b1a; đủ số ảnh; cặp RAW+JPEG hiện thành một ảnh | |
| 2 | 🧠 Nhận diện chủ thể, rồi 📊 Phân tích ảnh | Chạy xong, không báo lỗi; dòng trạng thái ghi GPU CUDA; ghi lại thời gian | |
| 3 | Xem cột **Chủ thể** | Mỗi "look" là một nhóm; ghi lại số nhóm thừa (tách sai) và nhóm gộp nhầm, nếu có | |
| 4 | Tick 2 chủ thể của cùng một người → **🔗 Gộp** → **Ctrl+Z** | Gộp được; Ctrl+Z trả lại đúng như cũ (ảnh, tên, số) | |
| 5 | Lọc ảnh: **P** / **X** / số sao / **F**, rồi **Ctrl+Z** vài lần | Phản hồi nhanh; Ctrl+Z lùi từng bước | |
| 6 | Tick 2–4 ảnh → **So sánh** (Compare), bấm P/X trong đó | Ảnh hiện đúng; P/X áp đúng ảnh đang trỏ | |
| 7 | ⤴ Xuất ảnh → "Ảnh đã Giữ", **RAW + JPEG**, đích `D:\RC\Xuat`, **không** tick "Xuất kèm danh sách ảnh đã chọn" | Đích chỉ có ảnh (RAW + JPEG cùng tên), **không** có thư mục `_kirapick_danh_sach` | |
| 8 | Xuất lại vào đích mới `D:\RC\Xuat2`, bấm **Dừng** giữa chừng → **Thử lại các file chưa chép** | Dừng được; thử lại chép nốt phần còn thiếu, không có file trùng " (1)" | |
| 9 | Xuất lại vào `D:\RC\Xuat3`, lần này **có** tick ô danh sách | Có thêm thư mục `_kirapick_danh_sach` (một file CSV, một file JSON) | |
| 10 | Đóng app → mở lại → mở lại `D:\RC\BuoiChup` | Giữ/Loại, sao, ❤, chủ thể đã gộp vẫn còn; Ctrl+Z vẫn hoàn tác được thao tác chủ thể | |
| 11 | So "dấu vân tay" ảnh gốc (lệnh dưới) | Hai file CSV giống hệt nhau | |

Lệnh cho dòng 11: chạy dòng đầu **trước bước 1**, chạy dòng sau **sau bước 10**, rồi so sánh.
```powershell
Get-ChildItem -Recurse -File D:\RC\BuoiChup | Get-FileHash | Select-Object Path, Hash | Export-Csv D:\RC\truoc.csv
Get-ChildItem -Recurse -File D:\RC\BuoiChup | Get-FileHash | Select-Object Path, Hash | Export-Csv D:\RC\sau.csv
(Compare-Object (Get-Content D:\RC\truoc.csv) (Get-Content D:\RC\sau.csv)) -eq $null
```
Dòng cuối phải in ra `True`.

Gửi lại bảng này, kèm file `%LOCALAPPDATA%\KiraPick\logs\kirapick.log`. Chép file log ra chỗ khác trước khi gỡ cài đặt
hoặc khôi phục.

## 2. Quay lại như cũ

1. Gỡ bản thử: Start → **Gỡ cài đặt KiraPick Beta CUDA**.
2. Muốn dùng lại 2.2.x cho các thư mục đã mở bằng bản 3.0 thì khôi phục bản sao lưu làm **trước lần cài bản thử đầu
   tiên**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
   ```
