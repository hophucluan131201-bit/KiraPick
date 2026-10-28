## KiraPick 2.2.0

**Ba bản cài** (chọn một; xem HUONG_DAN_CAI_DAT.txt):
- **2.2.0 – bản chính thức (DirectML):** cho mọi máy Windows 10/11.
- **2.2.0a – NVIDIA CUDA (thử nghiệm):** cho máy có card NVIDIA. Bộ cài lớn nên gồm `Setup.exe` và nhiều file `.bin`;
  tải tất cả vào cùng một thư mục rồi chạy `Setup.exe`.
- **2.2.0b – OpenVINO (thử nghiệm):** cho máy chip Intel; app tự đo, chỉ dùng OpenVINO khi nhanh hơn CPU thường.

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

## KiraPick 2.1.0b6 – bản thử nghiệm (beta)

> **Bản beta, chưa phải bản chính thức.** Bản chính thức mới nhất vẫn là 2.0.6.
> - **2.1.0b6 – gợi ý thẩm mỹ trên card đồ hoạ:** file tự kiểm tra 2.1.0b5 cho thấy DirectML báo lỗi (nút
>   Reshape) với mô hình thẩm mỹ vì mô hình nhận ảnh "mọi kích thước". Giờ card đồ hoạ dùng một bản cố định
>   kích thước cho từng hướng ảnh (ngang 576×384, dọc 384×576, …); vẫn so với CPU lúc khởi động, lỗi thì tự dùng CPU.
> - **2.1.0b5 – đo để tăng tốc:** file tự kiểm tra ghi thời gian từng khâu của 📊 (đọc ảnh gốc, gợi ý thẩm mỹ,
>   đo nét/mắt/mặt) và lý do mô hình thẩm mỹ không dùng được card đồ hoạ (nếu có).
> - **2.1.0b4 – 📊 Phân tích ảnh cũng dùng card đồ hoạ:** mô hình gợi ý thẩm mỹ được chạy trên GPU nếu khi
>   khởi động nó cho kết quả giống CPU (tự kiểm tra trên ảnh mẫu dọc và ngang); khác hoặc lỗi thì tự dùng CPU.
>   Thanh trạng thái ghi tên card đang dùng, ví dụ [GPU NVIDIA GeForce RTX 2080 …]; rê chuột lên để xem số đo.
> - **2.1.0b3 – chọn đúng card đồ hoạ:** laptop có 2 card (Intel + NVIDIA) thì DirectML từng chạy trên card
>   Intel nên chậm hơn CPU. Giờ app thử từng card, dùng card nhanh nhất và ghi tên card + thời gian đo lên thanh
>   trạng thái. Tự kiểm tra không còn lỗi khi thư mục Desktop nằm trong OneDrive (báo cáo vào thư mục logs).
> - **2.1.0b2 – bộ cài mở ngay:** file Setup.exe chỉ còn vài MB (dữ liệu nằm ở file `…-1.bin` đi kèm trong
>   `…-BoCai.zip`), vì Windows quét toàn bộ file .exe trước khi mở nên file 400 MB làm bấm vào rất lâu.
>   Giải nén cả file zip rồi chạy Setup.exe như cũ.
> - **Độ nét ảnh cận mặt:** ảnh chụp cận (mắt cách nhau hơn 500 điểm ảnh) được đo ở cỡ của chân dung thường,
>   nên ảnh cận nét không còn bị chê "thiếu nét"; ảnh chân dung bình thường vẫn đo ở 100% như cũ.
> - **Bố cục** được chấm cả khi app không thấy thân người (ảnh cận mặt); cắt trán trong ảnh cận được coi là
>   cách chụp, không phải lỗi.
> - **Thanh công cụ gọn lại:** "Tự chuyển ảnh" và "⚡ Dùng card đồ hoạ" nằm trong nút **⚙ Tuỳ chọn**, nên nút
>   **⌨ Phím tắt** không còn bị đẩy ra khỏi màn hình. Bấm 📊 Phân tích ảnh lại để chấm theo cách đo mới.


> **2.0.6 – hết "Not responding", không bị kẹt ở card đồ hoạ chậm.** AI chạy trong một tiến trình riêng nên
> cửa sổ luôn phản hồi (kể cả khi đang nạp mô hình). Lúc bắt đầu, app đo thử: nếu card đồ hoạ (DirectML) không
> nhanh hơn CPU trên máy này — ví dụ laptop có 2 card và DirectML lấy nhầm card Intel đang vẽ màn hình — thì tự
> dùng CPU và ghi rõ lý do trên thanh trạng thái.
>
> **2.0.5 – sửa lỗi "không chấm được" trên card đồ hoạ (DirectML).** Mô hình gợi ý thẩm mỹ không chạy trên
> DirectML nữa (chạy bằng CUDA hoặc CPU); nếu card đồ hoạ lỗi khi chạy một mô hình, mô hình đó tự chuyển sang CPU
> thay vì bỏ ảnh; lỗi của một mô hình phụ không làm mất điểm của cả ảnh; thanh trạng thái ghi rõ lỗi. Nút mới
> **⚡ Dùng card đồ hoạ**: tắt nếu máy bị giật / "Not responding". Tự kiểm tra có thể chạy trên vài ảnh thật:
> `KiraPick.exe --self-test bao-cao.json "D:\thư mục ảnh"`.
>
> **2.0.4 – danh sách chủ thể gọn gàng.** Ô chọn cách xếp ngay trên danh sách (theo số / thời gian chụp /
> nhiều ảnh nhất / tên), mặc định theo số. Chủ thể mới được đánh số theo thứ tự chụp. Nhấp phải vào danh sách →
> **🔢 Đánh số lại** để có 1, 2, 3… liền nhau (tên đã đặt và mọi lần sửa được giữ).
>
> **2.0.3 – ➕ Tạo chủ thể mới.** Chuột phải vào ảnh → **➕ Tạo chủ thể mới** cho người chưa có trong danh sách
> (đặt tên hoặc để trống); nếu đang xem một chủ thể, ảnh được chuyển sang chủ thể mới. Danh sách "Gán cho chủ thể…"
> xếp theo tên rồi theo số.
>
> **2.0.2 – "Cần xem lại" hỏi ít mà trúng hơn.** Chỉ hỏi khi hai chủ thể có trang phục khá giống nhau;
> mặt hơi giống (do makeup) mà trang phục khác hẳn thì không hỏi nữa. Buổi chụp thử: từ 64 câu hỏi (7 câu đúng là
> cùng một bộ) xuống 14 câu (6 câu đúng).
>
> **2.0.1 – bộ cài nhẹ hơn khoảng 370 MB.** Các mô hình AI lớn được lưu ở dạng nửa độ chính xác
> (FP16); kết quả gom chủ thể trên buổi chụp thử giống hệt bản 2.0.0. Bỏ thêm vài thành phần Qt không dùng.

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
