# Màn hình chọn chế độ — Thiết kế bước 1 (chờ duyệt)

Đặc tả gốc: `KiraPick_Beta_Dac_ta_hai_che_do.md`.
**Chưa viết code nào.** Phần mở rộng này sẽ được làm sau khi bạn duyệt thiết kế này.

## 1. Kết quả khảo sát

| Mục | Hiện trạng |
|---|---|
| Nhánh làm việc ("tab Beta") | Nhánh **`beta`** trên GitHub. Hiện `main` và `beta` cùng ở commit `c8fcf9e`, đúng bản 3.0.0 đã phát hành. |
| Commit cơ sở | `c8fcf9e`. Mọi việc làm trên `beta`. Bản thử nội bộ có số phiên bản `3.1.0b1.devN`. Gộp vào `main`, gắn tag và phát hành chỉ làm khi bạn ra lệnh. |
| Điểm vào app | `app/main.py` → `MainWindow` (cửa sổ lọc ảnh hiện tại). Mỗi lần mở, app bắt đầu với cửa sổ trống và chờ **📂 Nhập ảnh**; không tự mở lại thư mục cũ. |
| Điểm vào đặc biệt | `--self-test` (CI và bộ cài tự kiểm tra) và `--diagnose-grouping` (báo cáo chẩn đoán). Cả hai **chạy không có cửa sổ**, nên **không hiện bộ chọn**. Ngoài hai điểm này, app không có cách mở nào khác: không có tham số thư mục, không có "Open with". |
| Lưu dữ liệu | Mỗi lần P/X/sao, gộp hay đổi tên đều **ghi ngay** vào dữ liệu phiên (SQLite). Rời màn hình không cần bấm "Lưu". Lịch sử hoàn tác thao tác chủ thể được lưu lại; P/X/sao chỉ nằm trong bộ nhớ. |
| Đóng phiên an toàn | Đã có sẵn và đã được kiểm thử: `closeEvent` và `_close_session`. Nếu đang xuất ảnh thì hỏi trước. Phân tích AI dừng lại và lần sau chạy tiếp được. Nhập ảnh dừng lại và lần sau nhập tiếp. |
| Cửa sổ nhỏ nhất | 560 × 300 px, bằng nửa màn hình 1080p ở 150 %. Bộ chọn phải dùng được ở cỡ này. |
| Màu và kiểu chữ | `app/ui/theme.py`: nền `#1e1f22`, thẻ `#26282c`, nhấn `#4c8dff`. Bộ chọn dùng đúng các màu này. |

## 2. Thiết kế màn hình

- **Một cửa sổ "KiraPick"** gồm:
  - tiêu đề **"Chọn chế độ làm việc"**;
  - **hai thẻ lớn ngang hàng**, mỗi thẻ có hình minh hoạ, tên và một dòng mô tả:
    - **Chụp cá nhân**: "Gom ảnh theo chủ thể hoặc tạo hình."
    - **Media sự kiện**: "Duyệt ảnh theo diễn biến chương trình." Thẻ có nhãn nhỏ **Beta**.
  - Góc dưới ghi số phiên bản, như cửa sổ hiện tại.
- **Hình minh hoạ:** **hình vẽ đơn giản (vector) tự vẽ**, cùng màu với app:
  - Chụp cá nhân: khung ngắm quanh một người.
  - Media sự kiện: sân khấu kèm dòng thời gian.
  - Không dùng ảnh thật: ảnh của bạn là riêng tư, ảnh mạng thì vướng bản quyền.
  - **Logo giữ nguyên.** Logo mới chỉ áp dụng sau khi bản cập nhật này phát hành, theo đặc tả.
- **Cửa sổ nhỏ:**
  - **Rộng ≥ 760 px:** hai thẻ đặt ngang, có hình.
  - **Hẹp hơn:** hai thẻ xếp dọc.
  - **Thấp dưới 420 px:** ẩn hình, chỉ còn tên và mô tả.
  - Ở mọi cỡ, đến cả 560 × 300, chữ vẫn đọc được và thẻ vẫn bấm được.
- **Bàn phím:**
  - **Tab / Shift+Tab** chuyển giữa hai thẻ, từ trái sang phải.
  - **Enter / Space** mở thẻ đang chọn. Viền xanh dày 3 px cho biết thẻ đang chọn. Lúc mở app, thẻ "Chụp cá nhân" được chọn sẵn.
  - Phím **1 / 2** chọn nhanh: đề xuất thêm, bạn bỏ nếu không cần.
- **Chuột:** bấm vào chỗ nào trên thẻ cũng được. Mỗi lần bấm **chỉ mở một lần**: bấm đúp hay giữ Enter không mở hai cửa sổ.

## 3. Điều hướng

- **Mở app bình thường:** **luôn** hiện bộ chọn, kể cả khi lần trước đã chọn một chế độ (NAV-01). App không ghi nhớ lựa chọn.
- **Chụp cá nhân:** mở **đúng cửa sổ lọc ảnh hiện tại**, không sửa gì bên trong. Kích thước cửa sổ được nhớ như cũ.
- **Media sự kiện**, trong khi luồng Media còn đang làm:
  - mở màn hình **"Media sự kiện — Beta, đang phát triển"**;
  - màn hình này ghi rõ trạng thái, có nút **⟵ Quay lại chọn chế độ** (và phím Esc);
  - **không nhập và không phân tích gì** (MED-01).
- **Chọn chế độ chỉ để điều hướng.** Bộ chọn không tự nhập ảnh, không tự chạy phân tích, và không dùng mạng.

## 4. "Đổi chế độ" (đề xuất cần duyệt)

**Vị trí:**
- Mục **"⇄ Đổi chế độ…"** trong menu **⚙ Tuỳ chọn**.
- Trên màn hình Media: nút **Quay lại**.

**Khi bấm "Đổi chế độ" lúc đang làm việc**, app hỏi một câu:

> **Rời chế độ Chụp cá nhân?**
> Các lựa chọn, sao, ❤, gộp và đổi tên đã được lưu.
> Sau khi rời, Ctrl+Z vẫn hoàn tác được thao tác với chủ thể, nhưng **không còn hoàn tác được P / X / sao / ❤**.
> [Ở lại] [Đổi chế độ]

- Nếu **đang phân tích AI**, câu hỏi thêm dòng: "Phân tích đang chạy sẽ dừng; lần sau mở lại thư mục này, bấm lại để chạy tiếp."
- Nếu **đang xuất ảnh**, app dùng câu hỏi có sẵn: "Đang xuất ảnh…, dừng sau file đang chép?"

**Kết quả của từng lựa chọn (NAV-03):**
- **Ở lại** hoặc Esc: không có gì thay đổi. Phiên, ảnh đang xem và các ảnh đang đánh dấu giữ nguyên.
- **Đổi chế độ:**
  - Cửa sổ lọc ảnh đóng theo đúng quy trình đóng app hiện tại: chờ các tác vụ dừng hẳn, đóng dữ liệu an toàn.
  - Sau đó bộ chọn hiện lại.
  - Mở lại thư mục đó bằng "Chụp cá nhân" thì mọi thứ còn nguyên, như khi tắt rồi mở lại app.
- **Không có thư mục nào đang mở:** đổi ngay, không hỏi.

## 5. Ranh giới hai quy trình

- **Chụp cá nhân:**
  - không đổi hành vi, không đổi cấu trúc dữ liệu;
  - **không cần chuyển đổi dữ liệu**: dự án cũ mở như trước (PER-01).
- **Media sự kiện:**
  - Ở đợt này **chưa có dữ liệu riêng**.
  - Khi làm thật, dữ liệu Media sẽ để **tách riêng**, ở `%LOCALAPPDATA%\KiraPick\media\`. Một thư mục ảnh mở bằng cả hai chế độ sẽ không bị lẫn dữ liệu. Phần này sẽ nằm trong đặc tả Media riêng, như đặc tả đã ghi.
- **Phần dự kiến dùng lại cho Media**, sau khi có đặc tả Media:
  - nhập ảnh và ghép RAW+JPEG;
  - đọc giờ chụp và máy ảnh;
  - ảnh xem trước HD và khung xem lớn;
  - xuất bản sao an toàn (SHA-256, không ghi đè).

## 6. Thay đổi kỹ thuật dự kiến (nhỏ, tách riêng)

- **Thêm mới:**
  - `app/ui/mode_picker.py`: màn hình chọn chế độ;
  - `app/ui/media_home.py`: màn hình Media đang phát triển;
  - `app/ui/app_shell.py`: chuyển qua lại giữa bộ chọn và hai luồng.
- **Sửa nhỏ:**
  - `app/main.py`: mở bộ chọn thay vì mở thẳng `MainWindow`;
  - `MainWindow`: thêm mục "Đổi chế độ" và gửi tín hiệu "đã đóng xong".
- Phần còn lại của `MainWindow` không đổi.

## 7. Kế hoạch kiểm thử

| Mã | Cách kiểm |
|---|---|
| NAV-01 | Test tự động: mở app hai lần, kể cả sau khi đã chọn Media, thì cả hai lần đều thấy bộ chọn. `--self-test` / `--diagnose-grouping` không hiện bộ chọn. |
| NAV-02 | Test tự động: Tab / Shift+Tab / Enter / Space / bấm chuột / bấm đúp đều mở đúng luồng, và chỉ mở một lần. Bạn kiểm bằng tay trên Windows. |
| UI-01 | Chụp màn hình tự động trên Windows ở 1920×1080 (100 % và 150 %) và 560×300: không chữ nào bị cắt, cả hai thẻ đều bấm được. |
| PER-01 / PER-02 | Bộ test hiện có (974 test trên Windows, test hiệu năng, test sức chịu) chạy lại nguyên vẹn. Sau đó bạn chạy lại bảng 11 bước của bản RC qua "Chụp cá nhân", trên bản sao một dự án thật. |
| NAV-03 | Test tự động: Ở lại thì phiên giữ nguyên; Đổi chế độ thì đóng an toàn, kể cả khi đang phân tích hoặc đang xuất ảnh, rồi bộ chọn hiện lại; mở lại thư mục thì dữ liệu còn nguyên. |
| MED-01 | Test tự động và kiểm bằng tay: vào màn hình Media, đọc được trạng thái, quay lại được bằng nút hoặc Esc. |
| MED-02 | Để tới bước 3 (nghiệm thu Media), sau khi có đặc tả Media và bộ ảnh thử. |

**Bằng chứng gửi bạn:** commit, run build, ảnh chụp màn hình bộ chọn ở 3 cỡ, kết quả từng ca. Bản build nội bộ là `3.1.0b1.dev1` (CUDA `…a`); bản này cài riêng, không đè lên bản 3.0.0.

## 8. Cần bạn quyết

1. **File mockup** `KiraPick chọn chế độ làm việc.png`: mình chưa nhận được. Gửi giúp để mình làm đúng bố cục.
2. Có làm **"Đổi chế độ"** như mục 4 không? Đây là đề xuất của mình, cần bạn duyệt.
3. Có giữ **phím tắt 1 / 2** không?
4. Hình minh hoạ: dùng **hình vẽ đơn giản** như mục 2 được không?
