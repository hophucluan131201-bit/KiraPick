# Thử bản KiraPick Internal Test CUDA 3.0.0b1.dev5a — Gộp chủ thể mới và Hoàn tác (Ctrl+Z)

Đây là bản thử nội bộ, không phải bản phát hành. Bước nào ra khác mô tả dưới đây thì **dừng lại** và chụp màn hình gửi
mình. **Đừng làm theo file `HUONG_DAN_CAI_DAT.txt`** có trong gói tải về.

## 1. Sao lưu và cài

1. **Đóng mọi KiraPick.** Chạy lệnh sau trong PowerShell; nó không được in ra gì:
   ```powershell
   if (Get-Process KiraPick -ErrorAction SilentlyContinue) { "CÒN KiraPick ĐANG CHẠY - hãy đóng hết" }
   ```
2. **Kiểm tra script sao lưu.** Dòng đầu phải là `True`, dòng sau phải đúng
   `96306f5dd04844322306a73da5089e293ea3588d015e87fa5a6d5ad6ab179c26`:
   ```powershell
   Test-Path D:\KiraPick-SaoLuu\owner_backup.ps1
   (Get-FileHash D:\KiraPick-SaoLuu\owner_backup.ps1 -Algorithm SHA256).Hash.ToLower()
   ```
3. **Sao lưu.** Cuối cùng phải có dòng màu xanh "SHA-256: khớp", và thư mục sao lưu phải có file `DOC_TOI.txt`. Ghi
   lại đường dẫn script in ra. **Không xoá** bản sao lưu cũ làm trước lần cài bản thử đầu tiên.
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
4. **Tải bộ cài** (phải đăng nhập GitHub). Bấm thẳng link tải này:
   https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41394908188/artifacts/13120031488
   - Hoặc mở **lần chạy 1** của run 41394908188:
     https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41394908188/attempts/1
     rồi kéo xuống mục **Artifacts** và tải **kirapick-windows-cuda**, khoảng 2,9 GB.
   - Trang run bình thường mở **lần chạy 2** (lần chạy lại riêng phần test hiệu năng), nên ở đó chỉ thấy
     kirapick-perf-windows. Không tải gói đó.
   - Gói tải được đến ngày 02/12/2026. Giải nén vào `D:\KiraPick-CUDA-dev5a\`.
5. **Kiểm tra mã.** Lệnh phải in ra đúng 3 dòng, khớp từng ký tự với bảng dưới. Sai thì **không cài**.
   ```powershell
   cd D:\KiraPick-CUDA-dev5a
   Get-ChildItem -Recurse -File -Filter "KiraPick-InternalTest-CUDA-3.0.0b1.dev5a-Setup*" | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
   ```

   | File | SHA-256 |
   |---|---|
   | `…-3.0.0b1.dev5a-Setup.exe` | `c6a543bcc6493ab93917d92a9ee966a91a88a69e6a99b61882c4cd25b5dbac47` |
   | `…-3.0.0b1.dev5a-Setup-1.bin` | `52f18731e77a93c1f3d1106189f2fd778367671add1445ed75aec43811fae494` |
   | `…-3.0.0b1.dev5a-Setup-2.bin` | `16e7426572ccb7808fad5f385c65d88e614c69e8f3475e37843f816916b99996` |
6. **Cài.** Chạy file `…-Setup.exe`.
   - Bộ cài chưa có chữ ký số nên Windows có thể hiện SmartScreen. Chỉ bấm **More info → Run anyway** khi ba mã ở
     bước 5 đã khớp, màn hình ghi đúng tên file trên và "Unknown publisher".
   - **Dừng lại** nếu Windows Defender báo virus, hoặc tên nhà phát hành hay tên file khác đi.
   - Bản này thay bản thử CUDA cũ. Bản chính thức và bản thử DirectML vẫn giữ nguyên.

## 2. Bảng kiểm tra

Chỉ dùng **bản sao** của một buổi chụp thử. Mỗi dòng ghi Đạt hoặc Không, và ghi chú nếu có.

| # | Làm | Phải thấy | Đạt? |
|---|---|---|---|
| 1 | Nút **Chỉnh sửa** trên thanh trên cùng | Menu có mục **Hoàn tác** (mờ khi chưa có gì để hoàn tác) | |
| 2 | Tick 2 chủ thể → **🔗 Gộp** | Hộp thoại cho chọn chủ thể giữ lại, đặt tên, thấy ảnh của từng chủ thể | |
| 3 | Gộp xong → **Ctrl+Z** | Hai chủ thể trở lại như cũ: ảnh, tên, số | |
| 4 | Đánh dấu hai chủ thể "khác nhau", rồi thử gộp hai chủ thể đó | Nút Gộp bị khoá; chỉ gộp được khi tick "Bỏ dấu…"; Ctrl+Z trả lại dấu | |
| 5 | Bấm **P**, **X**, số sao, **F** trên một ảnh → **Ctrl+Z** nhiều lần | Lùi lại từng bước, đúng thứ tự ngược | |
| 6 | Xen kẽ: gộp, bấm P, đổi tên → **Ctrl+Z** 3 lần | Hoàn tác đổi tên, rồi P, rồi gộp | |
| 7 | Gõ chữ trong ô tìm kiếm → **Ctrl+Z** | Chỉ xoá chữ vừa gõ, không đụng tới ảnh | |
| 8 | Phím **Z** khi xem ảnh lớn | Vẫn phóng to như trước | |
| 9 | Gộp hoặc đổi tên → đóng app → mở lại cùng thư mục → **Ctrl+Z** | Vẫn hoàn tác được; dòng trạng thái báo còn bao nhiêu thao tác | |
| 10 | Bấm P → đóng app → mở lại → **Ctrl+Z** | Không hoàn tác P (đúng thiết kế); thao tác chủ thể vẫn hoàn tác được | |
| 11 | Sau khi gộp, nếu trước đó đã **⭐ Chọn ảnh** | Hộp thoại và dòng trạng thái báo "cần chọn lại" | |
| 12 | Chọn/Loại, sao, ❤ của ảnh sau khi gộp và hoàn tác | Không đổi | |
| 13 | Tốc độ bấm P/X | Nhanh như bản trước | |

Gửi lại bảng này, kèm file `%LOCALAPPDATA%\KiraPick\logs\kirapick.log`. Chép file log ra chỗ khác trước khi gỡ cài đặt
hoặc khôi phục.

## 3. Quay lại như cũ

1. Gỡ bản thử: Start Menu → **Gỡ cài đặt KiraPick Internal Test CUDA**.
2. Muốn dùng lại bản 2.2.x thì khôi phục bản sao lưu làm **trước lần cài bản thử đầu tiên**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
   ```
   - Khôi phục đưa dữ liệu KiraPick về đúng lúc sao lưu. Mọi thao tác làm sau lần sao lưu đó sẽ không còn hiện trong
     app.
   - Script không xoá gì: dữ liệu hiện tại được cất trong thư mục `KiraPick.truoc-khoi-phuc-<ngày-giờ>`.
