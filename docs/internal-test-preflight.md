# Trước khi cài bản thử nội bộ KiraPick Internal Test 3.0.0b1.dev1

Đọc hết trang này trước khi cài. Bản thử chỉ để **kiểm tra chấp nhận** (`docs/owner-acceptance-checklist.md`); nó
**không phải** bản phát hành.

## Những điều cần hiểu

- **Cài riêng nhưng dữ liệu dùng chung.** Bản thử cài vào `%LOCALAPPDATA%\Programs\KiraPick-InternalTest`, có lối tắt
  "KiraPick Internal Test" và mục gỡ cài đặt riêng: **không ghi đè KiraPick 2.2.1** bạn đang có. Nhưng cả hai bản
  dùng **chung** thư mục dữ liệu `%LOCALAPPDATA%\KiraPick` (phiên làm việc của từng thư mục ảnh, bộ nhớ học, nhật
  ký) và **chung** các cài đặt (`HKCU\Software\KiraPick`).
- **Mở một thư mục ảnh bằng bản thử sẽ nâng cấp phiên của thư mục đó lên v7.** Cài đặt thì không nâng cấp gì: trình
  cài không mở app. Chỉ khi bạn mở/nhập một thư mục trong bản thử thì phiên của thư mục đó mới được nâng cấp.
- **Sau khi nâng cấp, KiraPick 2.2.1 không mở được phiên đó nữa** (báo lỗi "SchemaTooNewError"). Gỡ bản thử hay
  cài lại 2.2.1 **không** đưa phiên về như cũ.
- **Quay lại = khôi phục bản sao lưu.** KiraPick tự để lại một bản `project.snorlu.db.v5.bak` trước khi nâng cấp,
  nhưng hãy dựa vào bản sao lưu đầy đủ của bạn (bên dưới). Bản thử không bao giờ ghi vào thư mục sao lưu nằm ngoài
  `%LOCALAPPDATA%`.
- **Ảnh gốc không bị đụng tới** (chỉ đọc, như mọi phiên bản). Riêng các bước rút thẻ: chỉ dùng thẻ thử đã sao lưu.

## Các bước bắt buộc trước khi chạy bản thử

1. **Đóng mọi KiraPick đang chạy** (cả 2.2.1). Kiểm tra trong Task Manager không còn `KiraPick.exe`.
2. **Sao lưu đầy đủ bằng script** — tải đúng bản đã kiểm thử (v2, commit `7265d2b`, SHA-256
   `96306f5dd04844322306a73da5089e293ea3588d015e87fa5a6d5ad6ab179c26`) theo bước 2 của
   `docs/owner-install-instructions.md`:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
   Script từ chối chạy khi KiraPick đang mở, không ghi đè bản sao lưu cũ, chép `%LOCALAPPDATA%\KiraPick` và các cài
   đặt, **so SHA-256 từng file**, rồi in ra đường dẫn bản sao lưu (ví dụ `D:\KiraPick-SaoLuu\20261031-153000`).
3. **Kiểm tra bản sao lưu đọc được**: mở thư mục đó, có file `DOC_TOI.txt` ghi "SHA-256 đã so khớp", thư mục
   `KiraPick\sessions` và `kirapick-settings.reg`. Bản sao lưu phải ở **ngoài** `%LOCALAPPDATA%` (script bắt buộc
   điều này).
4. **Dùng bản sao của thư mục ảnh để thử**: chép một buổi chụp (chỉ JPEG, như bảng kiểm tra) sang `D:\Test\...` và
   chỉ mở bản sao đó trong bản thử. Không mở các buổi chụp đang làm cho khách bằng bản thử.
5. Thẻ nhớ dùng để thử: đã sao lưu toàn bộ `DCIM`.

## Cài, thử, gỡ

1. Giải nén `KiraPick-InternalTest-3.0.0b1.dev1-BoCai.zip` vào một thư mục; chạy
   `KiraPick-InternalTest-3.0.0b1.dev1-Setup.exe` (file `.bin` phải nằm cùng thư mục). Trình cài **không** mở app ở
   cuối.
2. Mở **"KiraPick Internal Test"** từ Start Menu. Tiêu đề cửa sổ phải ghi **KiraPick 3.0.0b1.dev1**. Lối tắt
   "KiraPick" cũ vẫn mở bản 2.2.1.
3. Làm theo `docs/owner-acceptance-checklist.md` với bản sao thư mục ảnh và thẻ thử.
4. Lấy nhật ký: `%LOCALAPPDATA%\KiraPick\logs\kirapick.log` (chép ra ngoài trước khi gỡ hay khôi phục).
5. Gỡ bản thử: Start Menu → "Gỡ cài đặt KiraPick Internal Test" (hoặc Settings → Apps → "KiraPick Internal Test
   3.0.0b1.dev1"). KiraPick 2.2.1 vẫn còn; dữ liệu `%LOCALAPPDATA%\KiraPick` vẫn còn (trình gỡ không xoá dữ liệu).
6. Muốn dùng lại 2.2.1 với các thư mục đã mở bằng bản thử: **khôi phục**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\20261031-153000
   ```
   Script không xoá gì: thư mục dữ liệu hiện tại được đổi tên thành `KiraPick.truoc-khoi-phuc-<ngày-giờ>`, bản sao
   lưu được chép trở lại và kiểm tra SHA-256, cài đặt được nhập lại.

## Bốn cổng tách biệt

1. **Build xong** — CI tạo bộ cài (đã/ chưa).
2. **Tự kiểm tra bản đóng gói offline đạt** — CI chạy, mạng bị chặn (đã/ chưa).
3. **Bạn kiểm tra chấp nhận xong** — bảng kiểm tra (chưa).
4. **Duyệt phát hành beta công khai** — cần báo cáo quyết định và lệnh riêng của bạn (chưa; không được phép lúc này).
