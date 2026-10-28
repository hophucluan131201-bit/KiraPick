## KiraPick 2.2.1

**Hai bản cài** (chọn một; xem HUONG_DAN_CAI_DAT.txt):
- **2.2.1 – bản chính thức (DirectML):** cho mọi máy Windows 10/11.
- **2.2.0a – NVIDIA CUDA (thử nghiệm):** cho máy có card NVIDIA. Bộ cài lớn nên gồm `Setup.exe` và nhiều file `.bin`;
  tải tất cả vào cùng một thư mục rồi chạy `Setup.exe`.
- Bản **OpenVINO** (cho máy chip Intel) tạm hoãn: bản đóng gói chưa qua được bài tự kiểm tra, sẽ phát hành khi sửa xong.

**Chấm điểm mới: hai điểm riêng**
- **K – Kỹ thuật:** nét, mắt, mặt, sáng, bố cục, thẩm mỹ. Thêm AI mới:
  - **CLIP ViT-L/14 + bộ chấm thẩm mỹ LAION** (điểm thẩm mỹ là trung bình TOPIQ và LAION);
  - **TOPIQ chấm chất lượng ảnh** (nhiễu, mờ, nén; 20 % phần nét);
  - **TOPIQ chấm khuôn mặt** (một nửa phần mặt).
- **G – Hợp gu bạn:** app tự học từ các lần bạn Giữ/Loại/cho sao/❤.
  - Danh sách khách chọn chỉ được tính nhẹ.
  - Chỉ hiện khi đã có ≥ 60 lựa chọn (≥ 20 thích, ≥ 20 không thích) **và** app đoán đúng rõ hơn đoán mò
    (tự kiểm tra, tách theo ngày chụp). Chưa đủ thì ghi rõ "Chưa đủ dữ liệu: 34/60".
  - 🎓 **AI đã học** cho biết bạn hay giữ / hay loại kiểu ảnh nào. Nút **So sánh ảnh…** hỏi "thích tấm nào hơn"
    trên các cặp ảnh giống nhau để học nhanh hơn.
- **⭐ Chọn ảnh** xếp theo K + G (mặc định 50/50, đổi trong ⚙ Tuỳ chọn).
  - Ảnh lỗi nặng (nhắm mắt, mất nét) không vượt điểm kỹ thuật.
  - Riêng ảnh cố ý mờ/tối kiểu nghệ thuật mà rất hợp gu bạn thì được giữ điểm ("ngoại lệ nghệ thuật").

**Giao diện**
- Bảng bên phải: thanh điểm + lý do cho từng tiêu chí, điểm yếu chính, những gì chưa chấm được và vì sao.
- Lưới ảnh hiện "K 78 · G 85" (⚠ khi có lỗi nặng); xếp được theo K, G hoặc K + G.
- Khung bên trái:
  - các mục Thư mục / Lọc / Chủ thể thu gọn được;
  - mục Thư mục tự ẩn khi chỉ có một thư mục;
  - bộ lọc thành các nút nhỏ 2 cột;
  - danh sách chủ thể không còn thanh cuộn ngang, ảnh đại diện to hơn, số ảnh hiện thành nhãn.

**Cập nhật mô hình AI (cần mạng, chỉ khi bạn muốn)**
- ⚙ Tuỳ chọn → 🔄 Cập nhật mô hình AI: tải bản vá mô hình đã được KiraPick kiểm tra và ký số.
  - Tải xong kiểm tra mã SHA-256; giữ bản cũ để quay lại.
  - Không gửi ảnh hay dữ liệu nào của bạn.
  - Tự kiểm tra khi mở app: tắt sẵn, bật được trong ⚙.
- Ngoài phần này, app vẫn chạy hoàn toàn offline.

**Lưu ý**
- Bấm 📊 Phân tích ảnh lại cho các buổi chụp cũ để có điểm mới.
- Lần đầu chạy chậm hơn (thêm CLIP: khoảng 0,7 giây/ảnh trên CPU).
- Giấy phép: CLIP của OpenAI (tài liệu ghi việc đưa vào sử dụng thực tế "nằm ngoài phạm vi") và các mô hình
  TOPIQ (phi thương mại) được dùng với sự đồng ý của chủ dự án cho ứng dụng phi thương mại này. Xem phần miễn trừ.

---

Ứng dụng lọc ảnh cosplay / đường phố, chạy **hoàn toàn offline** trên Windows 10/11.
Không cần cài Git hay Python — mọi thứ đã nằm trong bộ cài. Có card đồ hoạ (NVIDIA, AMD, Intel) thì AI tự dùng card qua DirectML; không có thì chạy bằng CPU.

### KiraPick làm được gì
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
