KiraPick giúp lọc ảnh cosplay / đường phố trên Windows 10/11. Ứng dụng chạy hoàn toàn trên máy bạn (offline) và
**không bao giờ sửa, xoá hay di chuyển ảnh gốc**.

### Bản này dành cho máy nào
- **Mọi máy Windows 10/11 64-bit.** Card đồ hoạ NVIDIA, AMD hay Intel đều dùng được (qua DirectX 12). Máy không có
  card thì app tự chạy bằng CPU.
- **Máy có card NVIDIA** nên dùng bản **3.0.0a – NVIDIA CUDA** để AI chạy nhanh hơn khoảng gấp đôi.

### Cài đặt
1. Tải `KiraPick-3.0.0-BoCai.zip`, nhấp phải → **Extract All**.
2. **Đang dùng KiraPick 2.2?** Hãy sao lưu trước: đóng KiraPick, chạy `owner_backup.ps1` có trong gói. Lệnh dán sẵn có
   trong `HUONG_DAN_CAI_DAT.txt`.
   - Bản 3.0 thay bản 2.2.
   - Sau khi mở bằng 3.0, các buổi chụp cũ không mở lại được bằng 2.2.
3. Chạy `KiraPick-Setup-3.0.0.exe`. Nếu Windows hiện "Windows protected your PC", bấm **More info → Run anyway**. Bộ cài
   chưa có chữ ký số; chỉ bấm khi mã SHA-256 khớp với mã ghi cạnh file trên trang này.

### KiraPick làm được gì
- **📂 Nhập ảnh:** RAW (NEF, CR2, CR3, ARW…) và JPEG. Cặp RAW+JPEG được xem như một ảnh.
- **🧠 Nhận diện chủ thể:**
  - AI gom ảnh theo từng nhân vật / trang phục, dựa trên khuôn mặt và dáng người, kể cả ảnh không thấy mặt.
  - Gộp tay bằng **🔗 Gộp**: chọn chủ thể giữ lại, đặt tên, xem ảnh trước khi gộp.
  - App học dần từ các lần bạn sửa.
- **📊 Phân tích ảnh:**
  - Chấm độ nét ở mắt (đo trên ảnh gốc), mắt nhắm/mở, khuôn mặt, ánh sáng, bố cục và thẩm mỹ.
  - Mỗi ảnh có giải thích điểm mạnh và điểm yếu.
- **⭐ Chọn ảnh:** chọn sẵn N ảnh đẹp nhất cho mỗi chủ thể, các ảnh khác dáng nhau.
  - Điểm **"Hợp gu"** học từ những ảnh bạn hay giữ hoặc hay loại.
- **Lọc nhanh bằng phím:**
  - **P** giữ, **X** loại, **1–5** sao, **F** yêu thích.
  - **So sánh** 2–4 ảnh cạnh nhau.
- **Hoàn tác (Ctrl+Z):**
  - Gộp, đổi tên, tách chủ thể: tối đa 50 bước, còn nguyên sau khi mở lại app.
  - P / X / sao / ❤: tối đa 200 bước, mất khi đóng app.
- **⤴ Xuất ảnh (chỉ sao chép):**
  - Nguồn: thư mục đã nhập, hoặc thẻ nhớ / ổ cứng khác.
  - Định dạng: RAW + JPEG, chỉ RAW hoặc chỉ JPEG.
  - Thư mục đích: tất cả vào một thư mục, hoặc mỗi chủ thể một thư mục.
  - Mỗi file chép được kiểm tra SHA-256, không ghi đè file có sẵn. **Dừng / Thử lại** không tạo file trùng.
  - Tick **"Xuất kèm danh sách ảnh đã chọn"** nếu muốn có thêm danh sách CSV/JSON.

### Lưu ý của bản DirectML
- Trên bản này, phần chấm thẩm mỹ và chất lượng kỹ thuật chạy bằng **CPU**, nên phân tích chậm hơn bản CUDA. Một buổi chụp
  thử mất khoảng 11 phút, bản CUDA khoảng 5 phút.
- Máy bị giật khi phân tích thì tắt nút **⚡ Dùng card đồ hoạ** để chạy hoàn toàn bằng CPU.

### Giới hạn đã biết
- AI gom theo **trang phục**, chưa gom theo người: một người mặc hai bộ sẽ thành hai nhóm, đôi khi còn bị tách thừa.
  Hãy gộp tay; gộp nhầm thì Ctrl+Z.
- Buổi chụp rất lớn (hàng chục nghìn ảnh) mở và phân tích lâu hơn.
- Các mô hình ArcFace, TOPIQ và CLIP chỉ dùng cá nhân, phi thương mại (xem `LICENSES.txt`).
