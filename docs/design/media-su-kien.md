# Media sự kiện — Đặc tả (chờ duyệt)

Áp dụng cho chế độ **Media sự kiện** trên màn hình chọn chế độ. Chế độ **Chụp cá nhân** không đổi gì.
Mọi xử lý đều **chạy offline** trên máy, **không đụng tới ảnh gốc**, và chỉ chạy khi bạn bấm.

## 1. Quy trình

1. **📂 Nhập ảnh:** một thư mục sự kiện, RAW, JPEG hoặc cặp RAW+JPEG (dùng lại phần nhập ảnh hiện có).
2. **🧠 Phân tích sự kiện:** một nút, chạy một lần, có thể tạm dừng và chạy tiếp. Mỗi ảnh được gắn **4 nhóm thẻ** (mục 2)
   và được xếp vào **khoảnh khắc** (mục 3).
3. **Duyệt:**
   - Cột trái là **dòng thời gian các khoảnh khắc**; ở giữa là lưới ảnh.
   - Lọc nhanh theo thẻ, ví dụ: chỉ ảnh **Cận** + **Diễn giả** + **không lỗi nét**.
   - Đánh dấu bằng P / X / sao / ❤, hoàn tác bằng Ctrl+Z, xem lớn, so sánh 2–4 ảnh: giống chế độ Chụp cá nhân.
4. **⤴ Xuất bộ ảnh bàn giao:** chỉ sao chép, kiểm tra SHA-256, không ghi đè (dùng lại phần xuất ảnh hiện có).
   Có thể chia thư mục theo khoảnh khắc, theo bối cảnh hoặc theo người.

Mọi thẻ AI gắn đều là **gợi ý**, bạn sửa được. Sửa ở đâu thì app **ghi nhớ và học** ngay trong sự kiện đó.

## 2. Bốn nhóm thẻ (theo yêu cầu của bạn)

### 2.1 Cỡ cảnh: Toàn / Trung / Cận

- **Cách làm:** đo thật trên ảnh, không đoán. App dò người và khuôn mặt (mô hình đã có trong app), rồi so kích thước người
  chính với khung hình:
  - **Cận:** khuôn mặt hoặc nửa trên người chiếm phần lớn khung (chân dung, cận mặt, cận tay cầm sản phẩm).
  - **Trung:** thấy người từ khoảng ngang hông hoặc gối trở lên, hoặc một nhóm nhỏ chiếm phần lớn khung.
  - **Toàn:** người nhỏ trong khung, hoặc không có người chính (toàn cảnh hội trường, sân khấu, khu triển lãm).
- **Ngưỡng:** mình chỉnh theo **bộ ảnh mẫu của bạn** (mục 6), rồi mới báo độ chính xác thật.
- **Ảnh không có người** (sản phẩm, decor): dựa vào thẻ bối cảnh. Ví dụ cận sản phẩm sẽ là **Cận**.

### 2.2 Bối cảnh: Sân khấu / Booth / Decor / Gian hàng / Sản phẩm / Merch

- **Cách làm:** dùng mô hình **CLIP** đã có trong app (đang dùng để chấm thẩm mỹ). Mình so ảnh với mô tả bằng chữ của
  từng bối cảnh.
  - Các mô tả này được tính sẵn lúc build, nên app vẫn chạy offline.
  - Đây là suy luận thật của mô hình, không bịa điểm.
- **Mức tự tin:**
  - Mỗi ảnh nhận **một bối cảnh chính**, kèm mức tự tin.
  - Tự tin thấp thì ghi **"Chưa rõ"** để bạn chọn.
- **Học từ bạn:**
  - Bạn sửa bối cảnh của vài ảnh thì app học ngay từ các ảnh đó, rồi gợi ý lại cho cả sự kiện.
  - Học bằng cách so độ giống với các ảnh bạn đã gán, không cần mạng.
- **Cần bạn định nghĩa** (xem mục 7): Booth khác Gian hàng thế nào; Decor gồm những gì; Merch khác Sản phẩm thế nào.

### 2.3 Vai trò người: Diễn giả / Celeb / Talent / Đại biểu

- **Gom theo người:**
  - Bằng khuôn mặt, giống chế độ Chụp cá nhân, nhưng gom theo **người**, không theo trang phục.
  - Mỗi người hiện thành một mục trong danh sách **NGƯỜI**, kèm ảnh mặt.
- **Gán vai trò và tên:**
  - Bạn bấm vào người đó, chọn vai trò (Diễn giả / Celeb / Talent / Đại biểu), và nếu muốn thì đặt tên.
  - Mọi ảnh có người đó tự nhận thẻ đó.
  - Đây là cách **nhận biết từng người** như bạn muốn.
- **Gợi ý của app:**
  - Người xuất hiện nhiều trên **sân khấu** sẽ được gợi ý là "có thể là diễn giả / talent".
  - App **không tự biết tên** ai, và **không** tra cứu người nổi tiếng: không có mạng, cũng không có cơ sở dữ liệu
    khuôn mặt người nổi tiếng.
- **Nhớ qua các sự kiện** (tuỳ chọn, cần bạn quyết ở mục 7):
  - Có thể cho app nhớ những người bạn đã đặt tên, để sự kiện sau tự nhận ra (ví dụ một MC hay gặp).
  - Dữ liệu chỉ lưu trên máy bạn và xoá được.

### 2.4 Lỗi nét: Out nét / Trật nét

- **Cách làm:** dùng lại phần đo nét đã có trong app, đo trên **ảnh độ phân giải gốc**, không dùng ảnh thu nhỏ.
- **Out nét:** cả ảnh mờ, do rung tay, chủ thể chuyển động hoặc lấy nét không ăn.
- **Trật nét:** người hoặc vật chính bị mờ, nhưng chỗ khác trong ảnh lại nét, nghĩa là nét rơi ra trước hoặc ra sau.
  App so độ nét vùng chủ thể với vùng nét nhất trong ảnh.
- **Ảnh cố ý mờ** (lia máy, ánh đèn nghệ thuật) vẫn có thể giữ lại, giống chế độ cá nhân. Thẻ chỉ để bạn lọc nhanh.

## 3. Khoảnh khắc

- **Cách chia:**
  - Ảnh được chia thành khoảnh khắc theo **giờ chụp**: khoảng nghỉ dài hơn **N phút** thì sang khoảnh khắc mới.
  - N mặc định chọn theo bộ ảnh mẫu; bạn đổi được.
  - Bối cảnh thay đổi hẳn (ví dụ từ sân khấu sang khu gian hàng) cũng tách khoảnh khắc.
- **Tên khoảnh khắc:**
  - Mặc định là giờ chụp và bối cảnh chính, ví dụ "14:05 · Sân khấu".
  - Bạn đổi tên được, ví dụ "Check-in", "Phát biểu khai mạc", "Trao giải".
- **Gộp và tách tay được, có Ctrl+Z.**
- **Cùng một người** xuất hiện ở check-in, sân khấu và trao giải vẫn nằm ở **3 khoảnh khắc riêng** (MED-02).
  Danh sách NGƯỜI cho thấy người đó có mặt ở những khoảnh khắc nào.
- **Gợi ý đủ cỡ cảnh:**
  - Mỗi khoảnh khắc có dòng nhỏ ghi đã có ảnh Toàn / Trung / Cận nào được chọn.
  - Ví dụ "thiếu Cận" giúp bạn không bỏ sót.
  - Có thể giữ cả ảnh toàn cảnh và ảnh cận của cùng một khoảnh khắc.

## 4. Chọn ảnh tự động (tuỳ chọn)

- Nút **⭐ Chọn ảnh** cho mỗi khoảnh khắc chọn sẵn vài ảnh tốt nhất, ưu tiên:
  - không lỗi nét;
  - đủ Toàn / Trung / Cận;
  - đủ những người quan trọng (Diễn giả, Celeb…);
  - khác dáng nhau, không chọn 5 tấm gần giống nhau.
- Bạn duyệt lại như chế độ cá nhân.

## 5. Dữ liệu

- Dữ liệu của chế độ Media lưu **riêng**, ở `%LOCALAPPDATA%\KiraPick\media\`.
- Một thư mục mở bằng cả hai chế độ sẽ không bị lẫn dữ liệu, và dự án Chụp cá nhân cũ không bị đổi.
- Không cần chuyển đổi dữ liệu cũ.

## 6. Kiểm chứng trước khi giao bản thử

- Cần **một bộ ảnh sự kiện thật của bạn** (bản sao, vài trăm ảnh là đủ), kèm **nhãn mẫu**:
  - Cách dán nhãn đơn giản: một file Excel, mỗi dòng gồm tên file, cỡ cảnh, bối cảnh và lỗi nét.
  - Chỉ cần khoảng 100–150 ảnh có nhãn.
- Mình chạy app trên bộ ảnh đó và báo **độ chính xác thật** của từng nhóm thẻ. Mình không tự nhận là "chính xác" khi chưa đo.
- Sau đó mới build **một bản thử duy nhất**, gồm cả bộ chọn chế độ và Media, kèm **một bảng kiểm tra**.

## 7. Cần bạn chốt

1. **Booth** khác **Gian hàng** thế nào? **Decor** gồm những gì (backdrop, cổng chào, photowall…)? **Merch** khác
   **Sản phẩm** thế nào?
2. Một ảnh có thể mang **nhiều bối cảnh** (ví dụ vừa Booth vừa Sản phẩm), hay **chỉ một**?
3. Có cho app **nhớ người đã đặt tên qua các sự kiện** không? Dữ liệu chỉ lưu trên máy, xoá được.
4. Bạn gửi được **bộ ảnh mẫu kèm nhãn** như mục 6 không?
