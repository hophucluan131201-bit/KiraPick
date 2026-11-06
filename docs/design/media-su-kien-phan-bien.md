# Phản biện đặc tả "Media sự kiện" (bản 1)

Mình tự soi lại bản đặc tả vừa viết, như một người duyệt khó tính. Mỗi mục gồm: **vấn đề**, **vì sao quan trọng** và
**đề xuất sửa**. Mức độ được ghi trong ngoặc:
- **Chặn:** phải sửa trước khi làm.
- **Lớn:** ảnh hưởng nhiều tới chất lượng hoặc tiến độ.
- **Nhỏ:** nên sửa.

## A. Pháp lý và giấy phép

**A1. ArcFace chỉ được dùng phi thương mại, mà Media sự kiện thường là việc có thu tiền (Chặn).**
- **Vấn đề:** bản 1 định gom người bằng khuôn mặt "giống chế độ Chụp cá nhân", tức là dùng ArcFace. Giấy phép của mô
  hình này chỉ cho dùng phi thương mại / nghiên cứu. Chụp sự kiện để giao cho khách hàng là dùng thương mại. Mô hình
  chấm chất lượng TOPIQ cũng cùng loại giấy phép (PolyForm Noncommercial).
- **Đề xuất:**
  - Ở chế độ Media, gom người bằng **SFace** (giấy phép Apache-2.0, đã có sẵn trong app). SFace kém ArcFace một chút,
    nên phải đo lại trên bộ ảnh mẫu.
  - Không dùng TOPIQ để chọn ảnh trong Media; dùng các phép đo nét, sáng, mắt.
  - Nếu bạn vẫn muốn dùng ArcFace / TOPIQ cho việc có thu tiền, đó là quyết định của bạn và cần ghi rõ. Mình
    khuyên không.

**A2. Ghi nhớ khuôn mặt qua nhiều sự kiện là lưu dữ liệu sinh trắc học của người khác (Lớn).**
- **Vấn đề:** dữ liệu khuôn mặt của diễn giả, khách mời, khán giả là dữ liệu cá nhân **nhạy cảm**. Ở Việt Nam,
  Nghị định 13/2023 coi dữ liệu sinh trắc là dữ liệu nhạy cảm.
- **Đề xuất:**
  - **Mặc định tắt.** Chỉ nhớ những người **bạn tự đặt tên**, không nhớ khán giả.
  - Lưu trên máy; xem và xoá được từng người.
  - Có dòng giải thích ngay chỗ bật tuỳ chọn.

## B. Phân loại cỡ cảnh (Toàn / Trung / Cận)

**B1. Chưa định nghĩa "chủ thể chính" (Lớn).**
- **Vấn đề:** ảnh hội trường thường có đầu khán giả **to, mờ ở tiền cảnh**, như ảnh mẫu VNNIC của bạn. Nếu lấy
  "người lớn nhất" làm chủ thể, ảnh toàn cảnh sẽ bị xếp thành Cận.
- **Đề xuất:** chủ thể chính phải là người **nét**, **gần giữa khung**, **thấy mặt hoặc thân trước**, và **không bị mép
  khung cắt cụt**. Người mờ ở tiền cảnh và người quay lưng không được tính.

**B2. Không có mô hình dáng người để biết "từ hông trở lên" (Lớn).**
- **Vấn đề:** app có khung người và khuôn mặt, nhưng không có các điểm khớp (vai, hông, gối). Một người đứng xa thấy
  toàn thân, và một người đứng gần thấy nửa người, có thể cho khung cao như nhau.
- **Đề xuất:** dùng **tỉ lệ chiều cao khuôn mặt so với chiều cao khung hình**, kết hợp với việc khung người có chạm mép
  dưới ảnh hay không. Ví dụ:
  - **Cận:** mặt cao hơn khoảng 12 % khung;
  - **Trung:** 4–12 %;
  - **Toàn:** dưới 4 %, hoặc không có chủ thể.
  Các ngưỡng này chỉnh theo bộ ảnh mẫu. Nếu không đạt độ chính xác cần thiết, sẽ cần thêm một mô hình dáng người có
  giấy phép thương mại (đánh giá riêng).

**B3. Ảnh không có người (Nhỏ).**
- **Vấn đề:** bản 1 suy ra "Cận sản phẩm" từ thẻ bối cảnh. Nhưng bối cảnh không cho biết vật to hay nhỏ trong khung.
- **Đề xuất:** ảnh không có người mặc định để **"—"** (không xếp cỡ cảnh), trừ khi bạn gán tay. Không đoán.

## C. Bối cảnh (6 loại)

**C1. Sáu loại đang trộn hai trục khác nhau (Lớn).**
- **Vấn đề:** Sân khấu / Booth / Gian hàng là **nơi chốn**. Sản phẩm / Merch / Decor là **thứ được chụp**. Một ảnh
  hoàn toàn có thể là "ở Booth, chụp Sản phẩm". Ép mỗi ảnh vào đúng một nhãn sẽ sai nhiều.
- **Đề xuất:** tách thành hai nhóm thẻ:
  - **Khu vực** (chọn một): Sân khấu / Booth / Gian hàng / Khu check-in, photowall / Khán phòng / Khác.
  - **Nội dung** (chọn được nhiều): Người / Sản phẩm / Merch / Decor.

**C2. CLIP phân biệt kém các loại gần nhau (Lớn).**
- **Vấn đề:** CLIP khá tốt với "sân khấu" so với "sản phẩm", nhưng **Booth** và **Gian hàng**, hay **Merch** và
  **Sản phẩm**, gần như cùng một thứ đối với nó.
- **Đề xuất:**
  - Gộp các cặp đó nếu định nghĩa của bạn không phân biệt bằng mắt được.
  - Hoặc chấp nhận app chỉ gợi ý nhóm lớn, phần còn lại để app học từ vài ảnh bạn sửa.
  - Đặt **ngưỡng tối thiểu** cho phần "học từ bạn": cần ít nhất khoảng 5 ảnh mẫu cho mỗi loại, tránh học lệch từ 1–2 ảnh.

**C3. Gắn tên thương hiệu cho booth / gian hàng (câu hỏi mới, Lớn).**
- **Vấn đề:** khách hàng thường muốn ảnh **theo từng nhà tài trợ** ("Booth của hãng X"). App không đọc được chữ và logo
  (không có OCR).
- **Đề xuất:** bạn gán tên cho **một khoảnh khắc** (ví dụ "Booth X"). Ảnh giống nó về hình ảnh và giờ chụp sẽ được gợi ý
  cùng tên. Cần bạn xác nhận có cần tính năng này không.

**C4. Chi phí tính toán (Nhỏ).**
- **Vấn đề:** chạy CLIP lại cho bối cảnh là thừa.
- **Đề xuất:** **dùng lại** phần nhúng CLIP mà app đã lưu cho mỗi ảnh khi phân tích. Bối cảnh khi đó gần như không tốn
  thêm thời gian.

## D. Vai trò người

**D1. Danh sách NGƯỜI sẽ dài hàng trăm (Lớn).**
- **Vấn đề:** một sự kiện có hàng trăm khách. Liệt kê ai cũng thành một mục thì không dùng được.
- **Đề xuất:** chỉ hiện người **xuất hiện từ khoảng 5 ảnh trở lên**, hoặc **xuất hiện trên sân khấu**. Những người khác
  gom vào **"Khách khác"**.

**D2. Diễn giả trên sân khấu thường khó nhận mặt (Lớn).**
- **Vấn đề:** diễn giả hay ở **xa**, **nghiêng mặt**, **ngược đèn**, nên mặt quá nhỏ và gom sai hoặc sót.
- **Đề xuất:**
  - Báo thật số ảnh **"chưa nhận được người"**.
  - Bạn gán tay theo khoảnh khắc được: chọn nhiều ảnh, rồi "Gán: Diễn giả A".
  - Không hứa tự nhận đủ.

**D3. Gợi ý "người trên sân khấu = diễn giả" dựa vào thẻ bối cảnh (Nhỏ).**
- **Vấn đề:** nếu thẻ Sân khấu sai thì gợi ý vai trò cũng sai theo, tức là sai dây chuyền.
- **Đề xuất:** chỉ hiện gợi ý vai trò khi thẻ Sân khấu có độ tự tin cao.

## E. Lỗi nét

**E1. "Trật nét" dễ báo nhầm ở sân khấu (Lớn).**
- **Vấn đề:** màn LED, chữ trên backdrop và đèn sân khấu là những vùng **rất nét, độ tương phản cao**. Diễn giả
  hơi mềm một chút (do ánh sáng yếu, ISO cao) sẽ bị báo nhầm là "trật nét".
- **Đề xuất:**
  - Chỉ báo Trật nét khi có **chủ thể chính** theo B1.
  - Vùng nét so sánh phải nằm **cùng hướng sâu** với chủ thể: ngay sau hoặc trước người.
  - Loại vùng màn hình / đèn ra khỏi phép so.
  - Ngưỡng chỉnh theo bộ ảnh mẫu.

**E2. Ảnh nhiễu (ISO cao) làm sai phép đo nét (Nhỏ).**
- **Vấn đề:** hạt nhiễu làm phép đo nét tưởng ảnh "nét", nên ảnh out nét bị bỏ sót.
- **Đề xuất:** đo trên vùng đã lọc nhiễu nhẹ, và tính theo ISO của ảnh (đọc từ EXIF).

**E3. Mờ chuyển động khi chụp tiết mục (Nhỏ).**
- **Vấn đề:** talent nhảy, múa; ảnh lia máy có chủ ý. Ngoại lệ "nghệ thuật" ở chế độ cá nhân dựa vào việc học gu, không
  áp dụng được ở đây.
- **Đề xuất:** chỉ gắn thẻ để bạn lọc; **không tự loại** ảnh nào.

## F. Khoảnh khắc

**F1. Nhiều máy ảnh lệch giờ (Chặn).**
- **Vấn đề:** chụp sự kiện thường dùng **2 máy** hoặc **nhiều người chụp**, và giờ trên các máy lệch nhau vài phút.
  Chia khoảnh khắc theo giờ sẽ trộn sai thứ tự.
- **Đề xuất:**
  - Nhận biết từng máy qua số serial / tên máy trong EXIF.
  - Có màn **"Chỉnh giờ máy"**: chọn hai ảnh của hai máy cùng chụp một lúc, app tính độ lệch và áp cho cả máy.
  - Không sửa EXIF của ảnh gốc; chỉ lưu độ lệch trong dữ liệu của app.

**F2. Chụp liên tục thì không có khoảng nghỉ (Lớn).**
- **Vấn đề:** người chụp đi thẳng từ check-in sang sân khấu, không nghỉ lâu. Chia theo "nghỉ hơn N phút" sẽ không tách
  được hai hoạt động.
- **Đề xuất:**
  - Thêm tiêu chí **đổi cảnh về hình ảnh**: so nhúng CLIP giữa các nhóm ảnh liên tiếp. Tiêu chí này không phụ thuộc
    vào nhãn bối cảnh, nên tránh sai dây chuyền.
  - Thêm thao tác **"Tách tại đây"** nhanh trên dòng thời gian.

**F3. Ảnh mất giờ chụp (Nhỏ).**
- **Vấn đề:** JPEG đã qua chỉnh sửa có thể mất EXIF.
- **Đề xuất:** gom vào khoảnh khắc **"Không rõ giờ"**. Không dùng giờ của file, vì giờ file không đáng tin.

## G. Chọn ảnh tự động

**G1. "Khác dáng nhau" cần mô hình dáng người, mà app không có (Nhỏ).**
- **Đề xuất:** dùng **độ giống nhau của nhúng CLIP** và **ảnh chụp liên tiếp (burst)** để tránh chọn ảnh gần trùng.
  Cả hai đều đã có trong app.

**G2. Phụ thuộc thứ tự (Nhỏ).**
- **Vấn đề:** điều kiện "đủ người quan trọng" chỉ dùng được sau khi bạn đã gán vai trò.
- **Đề xuất:** khi chưa gán vai trò, bỏ qua điều kiện này và ghi rõ trên màn hình.

## H. Hiệu năng và quy mô

**H1. Một sự kiện có 3.000–10.000 ảnh (Lớn).**
- **Vấn đề:** đo nét trên ảnh gốc cho từng ảnh, trên máy DirectML (phần CLIP chạy CPU khoảng 0,7 giây/ảnh), có thể mất
  hàng giờ.
- **Đề xuất:**
  - Đặt mục tiêu: 5.000 ảnh trên máy RTX của bạn trong **dưới khoảng 45 phút**.
  - Đo nét gốc chỉ ở **vùng chủ thể** (đã là cách của app).
  - Kết quả hiện **dần dần**: xem và lọc được trong lúc vẫn đang phân tích.
- Bản 1 chưa có mục tiêu thời gian. Cần bạn xác nhận con số.

## I. Kiểm chứng và tiêu chí đạt

**I1. Chưa có ngưỡng đạt / không đạt (Chặn).**
- **Vấn đề:** bản 1 chỉ ghi "báo độ chính xác thật". Nếu độ chính xác thấp thì làm gì?
- **Đề xuất:**
  - Đặt mục tiêu cho từng thẻ, ví dụ:
    - Cỡ cảnh **≥ 85 %**;
    - Khu vực **≥ 80 %**;
    - Out nét: bắt được **≥ 90 %**, báo nhầm **≤ 10 %**;
    - Gom người: **không gộp nhầm** (độ chính xác 1.0) với các người đã đặt tên.
  - Thẻ nào chưa đạt thì vẫn có trong app, nhưng ghi **"(thử nghiệm)"** và **không dùng** để chọn ảnh tự động.

**I2. Gánh nặng dán nhãn (Nhỏ).**
- **Vấn đề:** dán nhãn trong Excel cực, mà 100–150 ảnh là **quá ít** cho 6 bối cảnh × 3 cỡ cảnh.
- **Đề xuất:**
  - Dán nhãn **ngay trong app**, bằng phím tắt khi duyệt (ví dụ T / U / C cho cỡ cảnh). App xuất file đánh giá chỉ
    gồm số liệu.
  - Cần khoảng **200 ảnh**, có đủ mỗi loại ít nhất 15–20 ảnh.

## J. Phạm vi

**J1. Quá nhiều cho một lần làm (Lớn).**
- **Vấn đề:** bạn muốn chỉ thử một lần. Nhưng làm hết rồi mới đo thì nếu một phần không đạt, phải làm lại nhiều.
- **Đề xuất:** làm theo 3 mốc **nội bộ** (bạn không phải thử từng mốc):
  1. Cỡ cảnh + lỗi nét + khoảnh khắc (có chỉnh giờ máy).
  2. Khu vực / nội dung + người / vai trò.
  3. Chọn ảnh + xuất ảnh.
- Sau mỗi mốc, mình tự đo trên bộ ảnh mẫu của bạn. Bạn chỉ thử **một bản cuối**.

## Câu hỏi cần bạn chốt (thay mục 7 của bản 1)

1. **Giấy phép (A1):** Media sự kiện là việc có thu tiền phải không? Nếu đúng, mình dùng **SFace** thay ArcFace và bỏ
   TOPIQ trong chế độ Media.
2. **Bối cảnh (C1, C2):** đồng ý tách thành **Khu vực** (chọn một) và **Nội dung** (chọn nhiều) không? Booth và Gian
   hàng có cần tách riêng không? Merch và Sản phẩm thì sao?
3. **Tên nhà tài trợ / booth (C3):** có cần gắn tên booth / nhà tài trợ không?
4. **Nhiều máy ảnh (F1):** bạn có hay chụp sự kiện bằng 2 máy, hoặc cùng người khác không?
5. **Nhớ người qua sự kiện (A2):** để tắt mặc định, chỉ nhớ người bạn đặt tên, được không?
6. **Thời gian (H1):** mục tiêu 5.000 ảnh dưới khoảng 45 phút trên máy RTX có hợp lý không?
7. **Bộ ảnh mẫu (I2):** khoảng 200 ảnh, dán nhãn ngay trong app, được không?
