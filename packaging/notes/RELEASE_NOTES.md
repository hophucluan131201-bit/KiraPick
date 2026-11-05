## KiraPick 3.0.0

**Hai bản cài** (chọn một; xem `HUONG_DAN_CAI_DAT.txt`):
- **KiraPick 3.0.0 (DirectML) – bản chính thức:** mọi máy Windows 10/11; dùng card đồ hoạ bất kỳ, không được thì CPU.
  Tải `KiraPick-3.0.0-BoCai.zip`.
- **KiraPick 3.0.0a – NVIDIA CUDA:** máy có card NVIDIA (driver mới). Bộ cài khoảng 3 GB: tải `KiraPick-Setup-3.0.0a.exe`
  và mọi file `KiraPick-Setup-3.0.0a-*.bin` vào cùng một thư mục.

**Nâng cấp từ 2.2.x:** bộ cài 3.0 thay bản 2.2.x (cùng một ứng dụng). **Sao lưu trước** bằng `owner_backup.ps1` có
trong gói: mở một buổi chụp cũ bằng 3.0 sẽ nâng cấp dữ liệu của buổi đó, và 2.2.x không mở lại được nữa (xem "Giới hạn
đã biết"). Nút "Cập nhật KiraPick" trong 2.2.x cũng đưa bạn lên 3.0.

### Mới trong 3.0

**Gộp chủ thể và Hoàn tác (Ctrl+Z)**
- **🔗 Gộp** mở hộp thoại: chọn chủ thể giữ lại, đặt tên, xem ảnh của từng chủ thể trước khi gộp.
- Hai chủ thể đã đánh dấu "khác nhau" thì không gộp được, trừ khi tick "Bỏ dấu…".
- **Chỉnh sửa → Hoàn tác** hoặc **Ctrl+Z** lùi lại từng bước, theo thứ tự ngược:
  - gộp, đổi tên, tách, đánh dấu chủ thể: tối đa 50 bước, **còn nguyên sau khi đóng và mở lại app**;
  - P / X / số sao / ❤ của ảnh: tối đa 200 bước, **mất khi đóng app**.
- Ctrl+Z trong ô tìm kiếm chỉ xoá chữ vừa gõ. Phím **Z** khi xem ảnh lớn vẫn là phóng to.
- Nếu đã bấm **⭐ Chọn ảnh** trước khi gộp, app báo "cần chọn lại".

**Xuất ảnh (RAW + JPEG và tuỳ chọn nâng cao)**
- **① Nguồn:** thư mục đã nhập, hoặc nguồn khác (thẻ nhớ, ổ cứng).
  - Với nguồn khác, app tìm từng ảnh theo nội dung, rồi theo giờ chụp.
  - Ảnh nào chưa chắc thì nằm ở tab "Cần xem lại" để bạn xác nhận.
- **② Định dạng:**
  - **RAW + JPEG** (mặc định): cặp RAW+JPEG giữ cùng một tên;
  - **Chỉ RAW**;
  - **Chỉ JPEG/JPG**.
- **③ Thư mục đích:** "Tất cả vào một thư mục" hoặc "Mỗi chủ thể một thư mục".
- **Ô tick mới "Xuất kèm danh sách ảnh đã chọn"** (mặc định tắt):
  - **Không tick:** thư mục đích chỉ có ảnh.
  - **Có tick:** có thêm thư mục con `_kirapick_danh_sach` chứa danh sách CSV + JSON (cả file bị bỏ qua).
  - Dù tick hay không, KiraPick vẫn giữ một nhật ký xuất trong dữ liệu của app: `%LOCALAPPDATA%\KiraPick`.
- **An toàn:**
  - chỉ sao chép, không bao giờ ghi đè (file trùng tên thì đặt tên mới);
  - mỗi bản chép được so SHA-256 với ảnh gốc;
  - **Dừng** thì xoá file đang chép dở;
  - **Thử lại các file chưa chép** kiểm tra lại các file đã có rồi bỏ qua chúng.

**AI chạy trên card NVIDIA (bản CUDA)**
- Mọi mô hình chạy trên card NVIDIA.
- Đo trên máy chủ dự án (một buổi chụp): phân tích hết khoảng **4 phút 52 giây** với CUDA, khoảng 10 phút 41 giây với
  DirectML.

### Giới hạn đã biết

- **Bộ cài chưa có chữ ký số.** Windows SmartScreen có thể chặn: chỉ bấm **More info → Run anyway** khi mã SHA-256
  của file khớp với mã GitHub ghi cạnh file trên trang phát hành.
- **CUDA và DirectML:**
  - Bản DirectML chạy TOPIQ, CLIP và chấm chất lượng kỹ thuật bằng **CPU** (card không chạy được các mô hình này), nên
    chậm hơn.
  - Bản CUDA chỉ dùng cho card NVIDIA và nặng khoảng 3 GB.
  - Máy không có card NVIDIA thì bản CUDA chạy bằng CPU.
- **Gom theo "trang phục / look", chưa gom theo người:**
  - Một người mặc hai bộ cosplay sẽ thành **hai chủ thể**. Chưa có lớp "cùng một người" (PERSON); dự kiến làm sau.
  - Bạn có thể gộp tay, rồi Ctrl+Z nếu gộp nhầm.
  - Một buổi chụp có thể bị tách thừa vài nhóm.
- **Phiên làm việc được nâng cấp:**
  - Mở một thư mục ảnh bằng bản 3.0 sẽ nâng cấp phiên làm việc của thư mục đó (phiên bản 7).
  - Sau đó KiraPick 2.2.x **không mở được** thư mục đó nữa.
  - Bản cũ được giữ ở file `project.snorlu.db.v5.bak` (hoặc `.v6.bak`).
  - Muốn quay lại 2.2.x thì khôi phục bản sao lưu (xem `HUONG_DAN_CAI_DAT.txt`).
- **Tốc độ:**
  - Trên máy kiểm tra của GitHub (10.000 ảnh), bấm P/X mất khoảng 30–46 ms.
  - Thỉnh thoảng có một lần chậm hơn 100 ms khi Python dọn bộ nhớ.
  - Buổi chụp rất lớn mở và phân tích lâu hơn.
- **Quay lại 2.2.x:** gỡ 3.0, cài lại bản 2.2.1 (hoặc 2.2.0a) từ trang phát hành, rồi khôi phục bản sao lưu
  (`owner_backup.ps1 -Restore …`, xem `HUONG_DAN_CAI_DAT.txt`).
- **Đã cài bản thử "KiraPick Beta" / "KiraPick Internal Test":** các bản đó nằm riêng, không bị bản 3.0 thay; gỡ khi
  không cần nữa (Start → "Gỡ cài đặt KiraPick Beta…").
- **Giấy phép:** ArcFace, TOPIQ và CLIP chỉ dùng phi thương mại / cá nhân (xem `LICENSES.txt`).

### Không đổi

- Ảnh gốc không bao giờ bị sửa, xoá, đổi tên hay di chuyển.
- Chạy hoàn toàn offline. Ngoại lệ duy nhất là nút "Cập nhật KiraPick", chỉ chạy khi bạn bấm.
- Dữ liệu học, phiên làm việc và cài đặt chỉ nằm trên máy bạn.
