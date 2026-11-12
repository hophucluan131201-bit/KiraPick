# KiraPick Beta — Đặc tả màn hình chọn chế độ

> **ĐÃ BỎ (2026-11-12):** chủ dự án quyết định bỏ hẳn Media sự kiện; mã đã gỡ khỏi `beta` (commit `942b02e`). Tài liệu này chỉ còn là lịch sử.

**Trạng thái:** Dự thảo để chủ dự án duyệt.  
**Phạm vi GitHub:** Làm việc tại khu vực Beta của repository KiraPick. Claude Code xác minh nhánh hoặc đích PR thực tế tương ứng với “tab Beta” trước khi triển khai. Chủ dự án duyệt riêng việc hợp nhất vào nhánh chính, tạo tag và phát hành.

## 1. Mục tiêu

Khi khởi động KiraPick theo cách thông thường, người dùng thấy ngay màn hình chọn chế độ. **Chụp cá nhân** mở quy trình lọc ảnh theo từng chủ thể hiện có. **Media sự kiện** mở quy trình tác nghiệp riêng cho sự kiện cosplay, hội nghị và các chương trình khác.

Chụp dàn cosplay lớn là bài toán riêng. Nếu có ảnh dàn trong một sự kiện, Media có thể xử lý chúng như một khoảnh khắc. Đánh giá ai bị che, ai nhắm mắt và đội hình có ổn hay không thuộc phạm vi đặc tả khác. Logo mới áp dụng sau khi bản cập nhật này phát hành.

## 2. Giao diện và điều hướng

Dùng mockup **KiraPick chọn chế độ làm việc.png** làm tham chiếu bố cục. Màn hình có nền tối, tiêu đề “Chọn chế độ làm việc” và hai thẻ lớn ngang hàng. Dùng nhận diện đang có trong app. Ảnh và logo trên mockup là minh họa. Claude Code đề xuất ảnh dùng thực tế và cách bố trí ở cửa sổ nhỏ.

| Thẻ | Nội dung phụ | Khi kích hoạt |
|---|---|---|
| **Chụp cá nhân** | Gom ảnh theo chủ thể hoặc tạo hình. | Mở đúng điểm vào của quy trình hiện tại. |
| **Media sự kiện** | Duyệt ảnh theo diễn biến chương trình. | Mở màn hình bắt đầu của luồng Media. |

- Toàn bộ thẻ có thể bấm. Tab di chuyển focus theo thứ tự trái sang phải. Enter hoặc Space kích hoạt thẻ đang có focus. Viền focus dễ thấy.
- Hai lựa chọn hiển thị rõ ở 1080p và khi thu nhỏ tới kích thước cửa sổ tối thiểu do Claude Code xác định. Chữ và nút luôn đọc, bấm được.
- Khởi động thông thường luôn hiển thị bộ chọn, kể cả khi lần trước đã chọn một chế độ. Claude Code khảo sát các điểm vào đặc biệt, nếu có, và trình cách xử lý.
- **Đề xuất cần duyệt:** thêm lệnh “Đổi chế độ” để quay về bộ chọn. Claude Code trình cách lưu hoặc cảnh báo trước khi rời phiên đang làm, cùng hành vi khi người dùng hủy hoặc quay lại.

## 3. Ranh giới hai quy trình

### Chụp cá nhân

Giữ hành vi của bản chính thức hiện hành. Kiểm tra nhập và ghép RAW+JPEG, nhận diện chủ thể hoặc look, phân tích ảnh, so sánh 2–4 ảnh, đánh dấu, hoàn tác và xuất bản sao. Dự án cũ phải mở được bằng luồng Cá nhân và giữ dữ liệu đã lưu. Nếu cần đổi cấu trúc dữ liệu, Claude Code phải trình phương án tương thích và phục hồi trước khi triển khai.

### Media sự kiện

Đơn vị duyệt dự kiến là cụm khoảnh khắc theo thời gian. Một người xuất hiện ở check-in, sân khấu và trao giải vẫn thuộc các cụm diễn biến riêng. Khi xét ảnh bàn giao, có thể giữ cả ảnh toàn cảnh và ảnh cận của cùng một khoảnh khắc. Quy tắc tạo cụm, xếp hạng, đánh dấu và xuất bộ ảnh Media cần đặc tả riêng trước khi triển khai đầy đủ.

Có thể tái sử dụng phần nhập ảnh, đọc metadata, xem trước và các thao tác phù hợp sau khi khảo sát mã nguồn. Việc chọn một chế độ chỉ điều hướng vào luồng đó, chưa tự chạy phân tích. Các xử lý ảnh tiếp tục chạy offline.

## 4. Trình tự triển khai đề xuất

1. **Thiết kế trên Beta.** Claude Code xác định đích GitHub, commit cơ sở, điểm vào app, dữ liệu dự án và các thành phần dự kiến tái sử dụng. Trình thiết kế màn hình, điều hướng, xử lý phiên và kế hoạch kiểm thử.
2. **Nghiệm thu màn hình chọn chế độ.** Kiểm thử khởi động, điều hướng và hồi quy Cá nhân. Nếu luồng Media đang phát triển, màn hình đích phải ghi rõ trạng thái Beta và cho phép quay lại bộ chọn. Mốc này nghiệm thu điều hướng.
3. **Nghiệm thu Media.** Chốt đặc tả Media và bộ ảnh kiểm thử thực tế. Xác minh chất lượng gom ảnh và khả năng chọn đủ khoảnh khắc cần bàn giao trước khi trình duyệt phát hành.

## 5. Tiêu chí nghiệm thu

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| NAV-01 | Mở mới, đóng rồi mở lại sau khi đã dùng một chế độ | Cả hai lần đều hiện hai lựa chọn. |
| NAV-02 | Dùng chuột và bàn phím kích hoạt từng thẻ | Mỗi thẻ mở đúng luồng. Focus dễ thấy và kích hoạt một lần. |
| UI-01 | Chạy ở 1080p và kích thước cửa sổ tối thiểu | Đọc đủ nhãn và mô tả, thao tác được với cả hai thẻ. |
| PER-01 | Dùng bản sao dự án từ bản chính thức | Mở được. Các nhóm, tên và lựa chọn đã lưu được giữ đúng. |
| PER-02 | Chạy lại luồng Cá nhân trên Windows/CUDA | Các bước nhập, phân tích, so sánh, chọn/loại, hoàn tác và xuất bản sao hoạt động theo baseline. |
| NAV-03 | Rời chế độ khi có phiên làm việc, nếu có lệnh đổi chế độ | Hủy thì giữ nguyên phiên. Tiếp tục thì lưu hoặc xử lý thay đổi theo thiết kế đã duyệt. |
| MED-01 | Chọn Media khi quy trình đang phát triển | Vào đúng màn hình Media, đọc được trạng thái và quay lại bộ chọn. |
| MED-02 | Bộ ảnh có cùng người xuất hiện ở ba hoạt động | Khi nghiệm thu Media, duyệt được ba khoảnh khắc riêng và có thể chọn ảnh cho từng hoạt động. |

Dùng bản chính thức làm baseline hồi quy. Kết quả 11/11 của Private Beta 3.0.0b1a là tham chiếu cho danh sách kiểm thử. Bằng chứng cho đợt này gồm mã commit, bản build, ảnh hoặc video màn hình, bộ dữ liệu thử và kết quả từng ca. Các ca Windows/CUDA cần chạy trên môi trường phù hợp.

## 6. Phân vai

- **Chủ dự án:** duyệt phạm vi, giao diện, hành vi chuyển chế độ và nghiệm thu cuối.
- **Claude Code:** khảo sát repository, thiết kế kỹ thuật, lập trình và cung cấp bản build cùng bằng chứng kiểm thử.
- **ChatGPT:** phản biện thiết kế, kiểm tra ranh giới hai luồng, xây dựng và thực hiện các ca kiểm thử khả thi, đối chiếu bằng chứng và ghi các lỗi cản trở nghiệm thu.
