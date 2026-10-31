# Cài bản thử nội bộ KiraPick Internal Test 3.0.0b1.dev1 — hướng dẫn từng bước

Bản đã được duyệt để **bạn tự cài và kiểm tra chấp nhận**. Không phải bản phát hành. Mất khoảng 2 giờ cả kiểm tra.
Nếu một bước không ra đúng như ghi ở đây: **dừng lại**, chụp màn hình, gửi lại — đừng đoán.

## Bước 1 — Tải đúng bộ cài và kiểm tra mã SHA-256

1. Đăng nhập GitHub, mở: https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41224104483
   (đúng run **41224104483**, commit `23f8746` — không dùng file của run khác).
2. Kéo xuống mục **Artifacts** → tải **kirapick-windows-directml** (khoảng 2,3 GB). Giải nén file tải về.
3. Bên trong có `KiraPick-InternalTest-3.0.0b1.dev1-BoCai.zip`. Kiểm tra mã của nó — mở PowerShell trong thư mục đó:
   ```powershell
   (Get-FileHash .\KiraPick-InternalTest-3.0.0b1.dev1-BoCai.zip -Algorithm SHA256).Hash.ToLower()
   ```
   Phải ra **đúng**:
   `26001562b8e9e7b958208846679989fdf11209fd713cba7c783f4ce1a5663762`
   Khác dù một ký tự → **không cài**, báo lại.
4. Giải nén `KiraPick-InternalTest-3.0.0b1.dev1-BoCai.zip` vào `D:\KiraPick-InternalTest-CaiDat\`. Có
   `KiraPick-InternalTest-3.0.0b1.dev1-Setup.exe` và `...-Setup-1.bin` (để chung một thư mục).

## Bước 2 — Tải script sao lưu và kiểm tra mã

1. Mở link (phiên bản 2 của script, đã kiểm thử riêng trên Windows PowerShell 5):
   https://raw.githubusercontent.com/hophucluan131201-bit/KiraPick/7265d2bd709d42d7678e8ad38aa1835635bea176/scripts/owner_backup.ps1
   Bấm chuột phải → **Save as…** → lưu thành `D:\KiraPick-SaoLuu\owner_backup.ps1`.
2. Kiểm tra mã:
   ```powershell
   (Get-FileHash D:\KiraPick-SaoLuu\owner_backup.ps1 -Algorithm SHA256).Hash.ToLower()
   ```
   Phải ra: `96306f5dd04844322306a73da5089e293ea3588d015e87fa5a6d5ad6ab179c26`

## Bước 3 — Sao lưu (bắt buộc, trước khi cài)

1. **Đóng mọi KiraPick** (cả 2.2.1). Mở Task Manager: không còn `KiraPick.exe`.
2. Chạy:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
   Cuối cùng phải có dòng xanh "Đã sao lưu … SHA-256: khớp" và "Bản sao lưu nằm ở: D:\KiraPick-SaoLuu\<ngày-giờ>".
   **Ghi lại đường dẫn này.**
3. Mở thư mục đó: có `DOC_TOI.txt` ("SHA-256 đã so khớp"), thư mục `KiraPick\sessions`, file `kirapick-settings.reg`.
4. Chép thêm (bằng tay) **các thư mục ảnh của buổi chụp sẽ thử** sang `D:\Test\` — chỉ mở bản sao này trong bản thử.
   Không mở buổi chụp đang làm cho khách bằng bản thử.
5. Thẻ nhớ thử: chép toàn bộ `DCIM` ra ổ cứng trước.

## Bước 4 — Cài

1. Chạy `KiraPick-InternalTest-3.0.0b1.dev1-Setup.exe`. Nếu Windows SmartScreen cảnh báo (bộ cài chưa ký số, giống
   2.2.1): **More info → Run anyway**.
2. Trình cài ghi "KiraPick Internal Test 3.0.0b1.dev1". Cài vào thư mục mặc định
   `%LOCALAPPDATA%\Programs\KiraPick-InternalTest`. Cuối cùng trình cài **không** mở app — đúng như thiết kế.
3. Kiểm tra: Start Menu có **KiraPick Internal Test** *và* vẫn có **KiraPick** (2.2.1). Settings → Apps có cả
   "KiraPick" và "KiraPick Internal Test 3.0.0b1.dev1".

## Bước 5 — Kiểm tra card đồ hoạ (DirectML) trước khi thử

Chạy bài tự kiểm tra của bản đã cài (không mở thư mục ảnh nào, không đụng dữ liệu của bạn):
```powershell
Start-Process "$env:LOCALAPPDATA\Programs\KiraPick-InternalTest\KiraPick.exe" -ArgumentList '--self-test', 'D:\Test\selftest.json' -Wait
Get-Content D:\Test\selftest.json
```
Gửi lại file `D:\Test\selftest.json`. Trong đó `"ok": true`, `"version": "3.0.0b1.dev1"`, và phần `"gpu"` cho biết app
chạy AI bằng card đồ hoạ (`"device"` có tên card / DirectML) hay phải dùng CPU (khi đó `"note"` ghi lý do). Mình chỉ
ghi "GPU đạt" khi file này cho thấy card đồ hoạ được dùng.

## Bước 6 — Thử theo bảng kiểm tra

Mở **KiraPick Internal Test** từ Start Menu (tiêu đề cửa sổ: **KiraPick 3.0.0b1.dev1**) và làm theo
`docs/owner-acceptance-checklist.md` với bản sao thư mục ảnh và thẻ thử. Trong lúc phân tích AI, mở Task Manager →
Performance → GPU: ghi lại GPU có chạy không (mục 10.3).

## Bước 7 — Lấy nhật ký

Đóng app, chép `%LOCALAPPDATA%\KiraPick\logs\kirapick.log` ra `D:\Test\`. Gửi cùng bảng kiểm tra và `selftest.json`.

## Bước 8 — Gỡ bản thử

Start Menu → **Gỡ cài đặt KiraPick Internal Test**. KiraPick 2.2.1 vẫn còn, dữ liệu vẫn còn.

## Bước 9 — Khôi phục (nếu muốn 2.2.1 mở lại các thư mục đã mở bằng bản thử)

```powershell
powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
```
Script không xoá gì: dữ liệu hiện tại được đổi tên thành `KiraPick.truoc-khoi-phuc-<ngày-giờ>`; nếu khôi phục hỏng giữa
chừng, dữ liệu trước đó được đặt lại đúng chỗ và báo lỗi. Sau đó mở KiraPick 2.2.1 như thường.

## Bốn cổng tách biệt

1. Build xong — **đạt** (run 41224104483). 2. Tự kiểm tra bản đóng gói offline — **đạt**. 3. Bạn kiểm tra chấp nhận —
**chưa**. 4. Duyệt phát hành beta công khai — **chưa, cần lệnh riêng của bạn**.
