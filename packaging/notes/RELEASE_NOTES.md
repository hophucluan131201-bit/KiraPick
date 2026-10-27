## KiraPick 2.0 – bản chính thức

Ứng dụng lọc ảnh cosplay / đường phố, chạy **hoàn toàn offline** trên Windows 10/11.
Không cần cài Git hay Python — mọi thứ đã nằm trong bộ cài. Có card đồ hoạ (NVIDIA, AMD, Intel) thì AI tự dùng card qua DirectML; không có thì chạy bằng CPU.

### Có gì trong bản 2.0
- **Gom ảnh theo chủ thể** bằng khuôn mặt **ArcFace** và dáng người **YoutuReID**, kể cả ảnh chụp cách xa nhau
  hay ảnh không thấy mặt. Buổi chụp thử 431 ảnh: không gộp nhầm, gom đúng 92% cặp ảnh (bản 0.2: 81%).
- Không bỏ sót cosplayer mặt nạ / kigurumi; người đứng phía sau không bị tính thành chủ thể.
- **Tự học từ các lần bạn sửa** (gộp / tách / bỏ ảnh), có kiểm tra an toàn, chỉ trên máy của bạn;
  xem hoặc xoá bằng nút **🎓 AI đã học**.
- Chấm điểm kỹ thuật (nét ở mắt đo trên ảnh gốc, **mắt nhắm/mở**, khuôn mặt, ánh sáng, bố cục) và một
  **gợi ý thẩm mỹ** nhỏ bằng AI; giải thích điểm mạnh / điểm yếu / chưa đánh giá.
- **⭐ Chọn ảnh**: N ảnh mỗi chủ thể, khác dáng nhau; **⤴ Xuất ảnh** chỉ sao chép, không bao giờ đụng ảnh gốc.

Đang dùng bản 0.x: cài đè lên là được, dữ liệu cũ giữ nguyên. Lần đầu mở lại một thư mục, bấm
**🧠 Nhận diện chủ thể** rồi **📊 Phân tích ảnh** để cập nhật.

### Tải file nào?
- **`KiraPick-…-BoCai.zip`** ← tải file này (bộ cài + hướng dẫn tiếng Việt).
- `KiraPick-…-portable.zip`: bản không cần cài, giải nén ra là chạy `KiraPick.exe`.
- `KiraPick-Setup-….exe`: chỉ riêng bộ cài.

### Cài trong 3 bước
1. Nhấp phải vào file `…-BoCai.zip` → **Extract All** (Giải nén tất cả).
2. Nhấp đúp `KiraPick-Setup-….exe`. Nếu Windows báo *“Windows protected your PC”*:
   bấm **More info** → **Run anyway** (bộ cài chưa có chữ ký số trả phí, không phải virus).
3. Next → Install → Finish. Mở ứng dụng bằng biểu tượng **KiraPick**.

Hướng dẫn chi tiết: file `HUONG_DAN_CAI_DAT.txt` trong file zip.

### Lưu ý miễn trừ trách nhiệm
Dự án cá nhân, **phi thương mại**, chia sẻ miễn phí (PolyForm Noncommercial 1.0.0). ArcFace (InsightFace) và
TOPIQ **chỉ được dùng phi thương mại / nghiên cứu**; YoutuReID được huấn luyện trên dữ liệu nghiên cứu. Chỉ dùng
cá nhân, không bán, không dùng để nhận diện người cho dịch vụ hay giám sát. Kết quả AI có thể sai — hãy xem lại
trước khi giao ảnh. Chi tiết: README (*Lưu ý miễn trừ trách nhiệm*) và file giấy phép trong bộ cài.
