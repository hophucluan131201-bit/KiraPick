## KiraPick – bản thử nghiệm (beta)

> **0.3.0b3 – sửa theo góp ý.** Người đứng phía sau (mờ, quay lưng) không còn thành chủ thể riêng;
> một chủ thể chỉ giữ một người trong mỗi ảnh (tự sửa cả dữ liệu cũ); "Chưa xác định" chỉ còn những ảnh
> chưa có chủ thể nào; chữ "Người" đổi thành "Chủ thể"; ngưỡng gom chỉnh theo số đo thật trên ảnh lớn
> (buổi chụp thử: gom đúng 92%, không gộp nhầm).
>
> **0.3.0b2 – nhận diện chủ thể tốt hơn và tự học.**
> - Khuôn mặt **ArcFace** (InsightFace) và dáng người **YoutuReID**: gom đúng người hơn, nhất là ảnh chụp
>   cách xa nhau về thời gian và ảnh không thấy mặt. Lần đầu mở lại một thư mục cũ, bấm
>   **🧠 Nhận diện chủ thể**: app tính thêm cho các ảnh đã có, không phải nhận diện lại từ đầu.
> - **Tự học từ các lần bạn sửa**: mỗi lần gộp / tách / bỏ ảnh khỏi một người, app ghi lại và
>   chỉnh nhẹ mức gộp ở lần **🧠 Nhận diện chủ thể** sau. Có kiểm tra an toàn, chỉ học trên máy của bạn;
>   xem hoặc xoá bằng nút **🎓 AI đã học**.
> - Bộ cài nặng hơn khoảng 280 MB.
>
> **Lưu ý:** ArcFace và TOPIQ **chỉ được dùng phi thương mại / nghiên cứu**; YoutuReID được huấn luyện trên
> dữ liệu nghiên cứu. Chỉ dùng cá nhân, không bán, không dùng để nhận diện người cho dịch vụ hay giám sát.
> Chi tiết: phần *Lưu ý miễn trừ trách nhiệm* trong README và file giấy phép trong bộ cài.
>
> 0.3.0b1: gợi ý thẩm mỹ bằng AI (TOPIQ). Bản ổn định trước đó (0.2.0b4) vẫn giữ nguyên ở dưới.

Ứng dụng lọc ảnh cosplay / đường phố, chạy **hoàn toàn offline** trên Windows 10/11.
Không cần cài Git hay Python — mọi thứ đã nằm trong bộ cài. Có card đồ hoạ (NVIDIA, AMD, Intel) thì AI tự dùng card qua DirectML; không có thì chạy bằng CPU.

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

Ảnh gốc không bao giờ bị sửa, xoá hay di chuyển; “Xuất ảnh” chỉ sao chép.
Dự án cá nhân, phi thương mại, chia sẻ miễn phí (PolyForm Noncommercial 1.0.0).
