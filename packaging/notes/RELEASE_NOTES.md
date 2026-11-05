## KiraPick 3.0.0

Lọc ảnh cosplay / đường phố trên Windows 10/11, chạy offline, không bao giờ đụng tới ảnh gốc.

### Tải bản nào
- **KiraPick 3.0.0 (DirectML)**: mọi máy. Tải `KiraPick-3.0.0-BoCai.zip`, giải nén, chạy `KiraPick-Setup-3.0.0.exe`.
- **KiraPick 3.0.0a (NVIDIA CUDA)**: máy có card NVIDIA. Tải `KiraPick-Setup-3.0.0a.exe`, **mọi** file
  `KiraPick-Setup-3.0.0a-*.bin` và `owner_backup.ps1` vào cùng một thư mục, rồi chạy file `.exe`.

Hướng dẫn từng bước: `HUONG_DAN_CAI_DAT.txt`, có trong gói tải về.

### Đang dùng 2.2.x? Sao lưu trước
- Bản 3.0 thay bản 2.2.x. Sau khi mở bằng 3.0, các buổi chụp cũ **không mở lại được bằng 2.2.x**.
- Đóng KiraPick, chạy `owner_backup.ps1` có trong gói. Lệnh dán sẵn nằm trong `HUONG_DAN_CAI_DAT.txt`.
- Muốn quay lại 2.2.x: gỡ 3.0, cài lại 2.2.x, rồi khôi phục bản sao lưu.

### Mới trong 3.0
- **Gộp chủ thể rõ ràng hơn:** chọn chủ thể giữ lại, đặt tên, xem ảnh của từng bên trước khi gộp.
- **Hoàn tác (Ctrl+Z):**
  - **Gộp, đổi tên, tách chủ thể:** tối đa 50 bước, còn nguyên sau khi mở lại app.
  - **P / X / sao / ❤:** tối đa 200 bước, mất khi đóng app.
- **Xuất ảnh nâng cao:**
  - **Nguồn:** thư mục đã nhập, hoặc thẻ nhớ / ổ cứng khác.
  - **Định dạng:** RAW + JPEG, chỉ RAW hoặc chỉ JPEG.
  - **Thư mục đích:** tất cả vào một thư mục, hoặc mỗi chủ thể một thư mục.
  - Mỗi bản chép được kiểm tra SHA-256 và không ghi đè file có sẵn.
  - **Dừng** / **Thử lại** không tạo file trùng.
  - Tick **"Xuất kèm danh sách ảnh đã chọn"** nếu muốn có thêm danh sách CSV/JSON. Mặc định thư mục đích chỉ có ảnh.
- **Bản CUDA:** mọi mô hình AI chạy trên card NVIDIA. Một buổi chụp thử phân tích hết khoảng 5 phút, bản DirectML mất khoảng 11 phút.

### Giới hạn đã biết
- **Bộ cài chưa có chữ ký số.** Nếu Windows chặn, bấm **More info → Run anyway**, nhưng chỉ khi mã SHA-256 khớp với mã ghi
  cạnh file trên trang này.
- **AI gom theo trang phục, chưa gom theo người:** một người mặc hai bộ sẽ thành hai nhóm, đôi khi còn bị tách thừa.
  Hãy gộp tay; gộp nhầm thì Ctrl+Z.
- **Bản DirectML** chấm thẩm mỹ và chất lượng bằng CPU, nên chậm hơn bản CUDA.
- **Buổi chụp rất lớn** (hàng chục nghìn ảnh) mở và phân tích lâu hơn; thỉnh thoảng có một nhịp khựng ngắn.
- **Giấy phép:** các mô hình ArcFace, TOPIQ và CLIP chỉ dùng cá nhân, phi thương mại (xem `LICENSES.txt`).
