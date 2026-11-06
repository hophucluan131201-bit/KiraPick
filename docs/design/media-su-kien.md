# Media sự kiện — Đặc tả bản 2 (đã chốt với chủ dự án, 2026-11-06)

Áp dụng cho chế độ **Media sự kiện**. Chế độ **Chụp cá nhân** không đổi gì.
Chế độ này chạy **offline**, **không đụng tới ảnh gốc**, và chỉ chạy khi bạn bấm.

Đây là công việc **có thu tiền**, nên chế độ này chỉ dùng mô hình có giấy phép thương mại (mục 6).

## 1. Quy trình

1. **📂 Nhập ảnh:** một thư mục sự kiện (RAW, JPEG, RAW+JPEG). Ảnh của **nhiều máy** nằm chung một thư mục, hoặc trong
   các thư mục con.
2. **🕒 Chỉnh giờ máy:**
   - App liệt kê các máy ảnh có trong thư mục (theo số serial / tên máy trong EXIF).
   - Nếu giờ giữa các máy lệch nhau, bạn chọn **hai ảnh chụp cùng lúc** từ hai máy. App tính độ lệch và áp cho toàn
     bộ ảnh của máy đó.
   - App chỉ lưu độ lệch trong dữ liệu của mình, **không sửa EXIF** của ảnh gốc.
   - Chụp bằng một máy thì bỏ qua bước này.
3. **🧠 Phân tích sự kiện:**
   - Bấm một nút; tạm dừng và chạy tiếp được.
   - **Ảnh nào xong trước thì hiện và lọc được ngay**, không phải chờ hết.
   - Mỗi ảnh được gắn 4 nhóm thẻ (mục 2) và được xếp vào khoảnh khắc (mục 3).
4. **Duyệt:**
   - Cột trái là dòng thời gian các khoảnh khắc, cùng danh sách NGƯỜI; ở giữa là lưới ảnh.
   - Lọc theo thẻ.
   - Đánh dấu P / X / sao / ❤, hoàn tác Ctrl+Z, xem lớn, so sánh 2–4 ảnh: giống chế độ Chụp cá nhân.
5. **⤴ Xuất ảnh:** chỉ sao chép, kiểm tra SHA-256, không ghi đè. Có thể chia thư mục theo khoảnh khắc, bối cảnh, người
   hoặc tên booth.

Mọi thẻ do AI gắn đều là **gợi ý**: bạn sửa được, và app học lại ngay **trong sự kiện đó**.

## 2. Bốn nhóm thẻ

### 2.1 Cỡ cảnh: Toàn / Trung / Cận

- **Chủ thể chính** là người **nét**, **gần giữa khung**, **thấy mặt**, và **không bị mép khung cắt cụt**. Người mờ ở
  tiền cảnh (đầu khán giả) và người quay lưng không được tính.
- **Cách xếp:**
  - Dựa vào tỉ lệ chiều cao khuôn mặt chủ thể so với chiều cao khung hình.
  - Ngưỡng chỉnh theo bộ ảnh mẫu (mục 5), ban đầu khoảng: **Cận > 12 %**, **Trung 4–12 %**, **Toàn < 4 %** hoặc không có
    chủ thể.
- **Ảnh không có người:** để **"—"**. App không đoán; bạn gán tay nếu cần.

### 2.2 Bối cảnh: Sân khấu / Booth / Decor / Gian hàng / Sản phẩm / Merch

- **Một nhóm 6 loại**, giữ đúng như bạn đặt (không tách thành hai nhóm).
- **AI gợi ý** một bối cảnh chính cho mỗi ảnh, bằng CLIP (dùng lại phần đã tính lúc phân tích, nên không tốn thêm thời
  gian). Mức tự tin thấp thì ghi **"Chưa rõ"**.
- **Bạn có thể tick thêm bối cảnh khác** cho cùng ảnh, ví dụ vừa Booth vừa Sản phẩm.
- **Học từ bạn:** khi một loại có **từ 5 ảnh** bạn đã sửa trở lên, app gợi ý lại cho cả sự kiện dựa trên các ảnh đó.
- **Đo trên bộ ảnh mẫu:** nếu app hay nhầm giữa hai loại (ví dụ Booth và Gian hàng), mình báo lại bằng số liệu để bạn
  quyết định có gộp hay không.

**Tên booth / nhà tài trợ:**
- Chủ yếu bạn tự phân loại: chọn ảnh rồi gán tên, ví dụ "Booth Samsung".
- App hỗ trợ thêm: ảnh **trông giống và chụp gần giờ** với các ảnh đã gán sẽ được **gợi ý** cùng tên, chờ bạn bấm xác
  nhận.
- App không đọc được chữ hay logo.

### 2.3 Người và vai trò: Diễn giả / Celeb / Talent / Đại biểu

- **Gom người bằng khuôn mặt** với mô hình **SFace** (giấy phép thương mại). Không dùng ArcFace trong chế độ Media.
- **Danh sách NGƯỜI** chỉ hiện người **xuất hiện từ 5 ảnh trở lên**, hoặc **có mặt trên sân khấu**. Những người khác gom
  vào **"Khách khác"**.
- **Gán vai trò và tên:** bạn bấm vào một người, chọn vai trò và đặt tên. Mọi ảnh có người đó tự nhận thẻ.
- **Gán theo nhóm ảnh** khi app không nhận được mặt, ví dụ diễn giả ở xa hoặc ngược đèn: chọn nhiều ảnh, rồi bấm "Gán:
  Diễn giả A".
- **Gợi ý "có thể là diễn giả / talent"** chỉ hiện khi app chắc ảnh đó là Sân khấu.
- App báo thật số ảnh **"chưa nhận được người"**.
- **Không nhớ người qua các sự kiện:** mỗi sự kiện bắt đầu từ đầu, và không lưu dữ liệu khuôn mặt sau khi xoá sự kiện.

### 2.4 Lỗi nét: Out nét / Trật nét

- **Đo nét trên ảnh độ phân giải gốc**, ở vùng chủ thể.
- **Out nét:** cả ảnh mờ (rung tay, chuyển động, lấy nét trượt).
- **Trật nét:** chủ thể chính mờ, nhưng vùng ngay trước hoặc sau chủ thể lại nét. Màn LED và đèn sân khấu được loại
  khỏi phép so, để tránh báo nhầm.
- **Ảnh ISO cao** được tính tới, để hạt nhiễu không bị hiểu là "nét".
- **Không tự loại ảnh nào.** Thẻ chỉ để bạn lọc nhanh (ảnh lia máy, múa… có thể là cố ý).

## 3. Khoảnh khắc

- **Chia theo giờ chụp đã chỉnh lệch giữa các máy**, theo hai tiêu chí:
  - khoảng nghỉ dài;
  - **đổi cảnh về hình ảnh**: so độ giống giữa các nhóm ảnh liên tiếp. Tiêu chí này giúp tách được cả khi chụp liên tục.
- **Tên khoảnh khắc:** mặc định là giờ và bối cảnh chính, ví dụ "14:05 · Sân khấu". Bạn đổi tên được, ví dụ "Trao giải".
- **Gộp, tách, "Tách tại đây"** trên dòng thời gian; đều có Ctrl+Z.
- **Ảnh không có giờ chụp** nằm ở khoảnh khắc **"Không rõ giờ"**.
- **Cùng một người ở nhiều hoạt động** vẫn nằm ở các khoảnh khắc riêng. Danh sách NGƯỜI cho thấy người đó có mặt ở đâu.
- **Mỗi khoảnh khắc báo đủ cỡ cảnh hay chưa**, ví dụ "đã chọn: Toàn ✓ Trung ✓ Cận ✗".

## 4. Chọn ảnh tự động

- Nút **⭐ Chọn ảnh** chọn sẵn vài ảnh cho mỗi khoảnh khắc, theo thứ tự ưu tiên:
  1. không lỗi nét;
  2. đủ Toàn / Trung / Cận;
  3. có người quan trọng (nếu bạn đã gán vai trò);
  4. không chọn các ảnh gần trùng nhau.
- **Điểm chọn** dựa vào nét, sáng, mắt mở, bố cục. Không dùng TOPIQ.
- Thẻ nào chưa đạt mục tiêu ở mục 5 thì ghi **"(thử nghiệm)"** và **không dùng** để chọn ảnh.

## 5. Kiểm chứng: dán nhãn mẫu

- Làm **một lần, ngắn**. Bạn mở một sự kiện đã chụp (bản sao), bật **"Dán nhãn mẫu"**, rồi bấm phím cho khoảng
  **100–150 ảnh** do app chọn sẵn cho đa dạng:
  - **T / U / C:** cỡ cảnh;
  - **phím số:** bối cảnh;
  - **O:** out nét; **R:** trật nét.
- App so kết quả AI với nhãn của bạn, rồi ra bảng **phần trăm đúng**. Bảng chỉ có con số, không gửi ảnh đi đâu.
- **Mục tiêu:**
  - cỡ cảnh **≥ 85 %**;
  - bối cảnh **≥ 80 %**;
  - out nét: bắt được **≥ 90 %**, báo nhầm **≤ 10 %**;
  - gom người: **không gộp nhầm** hai người khác nhau.

## 6. Giấy phép và dữ liệu

- **Mô hình dùng trong Media:**
  - dò người YOLOX (Apache-2.0);
  - dò mặt YuNet (MIT);
  - nhận mặt **SFace** (Apache-2.0);
  - CLIP (bạn đã chấp nhận điều khoản từ 2026-10-28).
- **Không dùng trong Media:** ArcFace và TOPIQ (chỉ được dùng phi thương mại).
- **Dữ liệu Media** lưu riêng ở `%LOCALAPPDATA%\KiraPick\media\`. Dự án Chụp cá nhân không bị đổi.

## 7. Tốc độ

- **Mục tiêu:** càng nhanh càng tốt. Mỗi việc nặng chỉ chạy một lần, và kết quả hiện dần trong lúc phân tích.
- Mình báo thời gian thật cho 1.000 / 5.000 ảnh, đo trên máy RTX của bạn khi bạn thử bản cuối.

## 8. Thứ tự làm

Bạn không phải thử từng mốc.

1. **Mốc 1:** nhập ảnh nhiều máy + chỉnh giờ + khoảnh khắc + cỡ cảnh + lỗi nét + chế độ dán nhãn mẫu.
   → Gửi bạn **một bản để dán nhãn mẫu** (mục 5). Mình đo kết quả rồi chỉnh.
2. **Mốc 2:** bối cảnh + tên booth + người và vai trò.
3. **Mốc 3:** chọn ảnh tự động + xuất ảnh.
   → **Một bản thử cuối duy nhất**, kèm một bảng kiểm tra cho cả hai chế độ.
