KiraPick giúp lọc ảnh cosplay / đường phố trên Windows 10/11. Ứng dụng chạy hoàn toàn trên máy bạn (offline) và
**không bao giờ sửa, xoá hay di chuyển ảnh gốc**. Bản này dành riêng cho **card NVIDIA**.

### Bản này dành cho máy nào
- **Windows 10/11 64-bit có card NVIDIA** (GTX 10xx trở lên) và **driver NVIDIA mới**.
- Cần khoảng 3 GB để tải và khoảng 6 GB ổ trống.
- **Máy không có card NVIDIA:** hãy dùng bản **KiraPick 3.0.0 (DirectML)**. Bản CUDA trên máy đó chỉ chạy được bằng
  CPU.

### Cài đặt
1. Tải **tất cả** các file sau vào **cùng một thư mục**:
   - `KiraPick-Setup-3.0.0a.exe`;
   - `KiraPick-Setup-3.0.0a-1.bin` và `KiraPick-Setup-3.0.0a-2.bin`;
   - `owner_backup.ps1` và `HUONG_DAN_CAI_DAT.txt`.
2. **Đang dùng KiraPick 2.2?** Hãy sao lưu trước: đóng KiraPick, chạy `owner_backup.ps1`. Lệnh dán sẵn có trong
   `HUONG_DAN_CAI_DAT.txt`.
   - Bản 3.0 thay bản 2.2.
   - Sau khi mở bằng 3.0, các buổi chụp cũ không mở lại được bằng 2.2.
3. Chạy `KiraPick-Setup-3.0.0a.exe`. Hai file `.bin` phải nằm cạnh file `.exe`. Nếu Windows hiện "Windows protected
   your PC", bấm **More info → Run anyway**. Bộ cài chưa có chữ ký số; chỉ bấm khi mã SHA-256 khớp với mã ghi cạnh file
   trên trang này.

### Điểm riêng của bản CUDA
- **Mọi mô hình AI chạy trên card NVIDIA:** nhận diện người, khuôn mặt, dáng người, thẩm mỹ, chất lượng kỹ thuật.
- **Nhanh hơn khoảng gấp đôi:** một buổi chụp thử phân tích hết khoảng **5 phút**, bản DirectML mất khoảng 11 phút
  (RTX 2080 Super Max-Q).
- Dòng trạng thái trong app ghi **GPU CUDA** khi card đang được dùng.

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

### Giới hạn đã biết
- AI gom theo **trang phục**, chưa gom theo người: một người mặc hai bộ sẽ thành hai nhóm, đôi khi còn bị tách thừa.
  Hãy gộp tay; gộp nhầm thì Ctrl+Z.
- Buổi chụp rất lớn (hàng chục nghìn ảnh) mở và phân tích lâu hơn.
- Các mô hình ArcFace, TOPIQ và CLIP chỉ dùng cá nhân, phi thương mại (xem `LICENSES.txt`).
