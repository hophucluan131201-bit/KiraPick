# Đo gom nhóm lần 2 — bản chẩn đoán KiraPick Internal Test CUDA 3.0.0b1.dev4a

Bản này giống bản dev3a bạn đã dùng, thêm hai phần đo mới:
- tìm những tấm ảnh có cùng một khách xuất hiện hai lần;
- kiểm tra phần app đã học từ các lần sửa của bạn.

Nó không phải bản phát hành. Bước nào ra khác mô tả dưới đây thì **dừng lại** và gửi ảnh chụp màn hình cho mình.
**Đừng làm theo file `HUONG_DAN_CAI_DAT.txt`** có trong gói tải về.

## 1. Sao lưu

1. Đóng mọi KiraPick. Mở Task Manager kiểm tra: không còn `KiraPick.exe` nào.
2. Chạy:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
3. Cuối cùng phải có dòng màu xanh ghi "SHA-256: khớp". **Ghi lại đường dẫn bản sao lưu** mà script in ra.

## 2. Tải bộ cài và kiểm tra

1. Mở https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41362621002 (đúng run **41362621002**).
2. Chỉ tải **kirapick-windows-cuda**. Gói này tải được đến ngày 02/12/2026.
3. Giải nén vào `D:\KiraPick-CUDA-dev4a\`, rồi chạy trong PowerShell:
   ```powershell
   cd D:\KiraPick-CUDA-dev4a
   Get-ChildItem -Recurse KiraPick-InternalTest-CUDA-* | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
   ```
4. Kết quả phải khớp **đủ ba dòng** dưới đây. Sai dù chỉ một ký tự thì **không cài**.

   | File | SHA-256 |
   |---|---|
   | `KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup.exe` | `4326168d4a5ab30998cbb246e7d7019ecbbe2aca1ecefbaeae0250d6ffb66b11` |
   | `...-Setup-1.bin` | `134c2d16e306ab3ce9d22f914bc218b008ff3aba36782275bf3c9f944ca5a5dd` |
   | `...-Setup-2.bin` | `914a52a768d2917a7bf44f643cb2617c7b1d128140445cef79400d366712547d` |

## 3. Cài

Chạy file `...-Setup.exe`. Nếu SmartScreen hiện cảnh báo, bấm **More info → Run anyway**.

Bản này **thay bản thử CUDA dev3a**. Bản KiraPick chính thức và bản thử DirectML vẫn giữ nguyên.

## 4. Chạy lệnh đo trên buổi chụp thử

Dùng **đúng buổi chụp thử lần trước** (bản sao, các nhóm đã được đặt tên `K1-A`…). Không cần đặt tên lại.

1. **Đóng hẳn KiraPick.** Kiểm tra Task Manager không còn `KiraPick.exe`.
2. Chạy lệnh sau (thay `D:\Test\BuoiThu` bằng đúng thư mục buổi chụp thử của bạn):
   ```powershell
   & "$env:LOCALAPPDATA\Programs\KiraPick-InternalTest-CUDA\KiraPick.exe" --diagnose-grouping "D:\Test\BuoiThu" "D:\Test\grouping-report-2.json" --cooccurrence-list "D:\Test\anh-trung-nguoi.csv" | Out-Null
   ```
3. Lệnh tạo ra hai file:
   - `grouping-report-2.json`: chỉ có số liệu. **File này gửi cho mình.**
   - `anh-trung-nguoi.csv`: có tên ảnh và tên nhóm. **File này chỉ để bạn xem trên máy, đừng gửi.**

## 5. Xem các ảnh trùng người (trên máy bạn)

1. Mở `anh-trung-nguoi.csv` bằng Excel. Mỗi dòng là một tấm ảnh mà cùng một khách nằm ở hai nhóm.
2. Mở tấm ảnh đó trong KiraPick, xem kỹ, rồi điền vào cột `owner_verdict` **đúng một** từ sau:
   - `trung`: app nhận một người thành hai (ví dụ khung mặt riêng, khung người riêng);
   - `phanchieu`: có gương, kính hay màn hình phản chiếu;
   - `hainguoi`: đúng là hai người khác nhau trong ảnh;
   - `dattensai`: bạn đặt tên nhóm nhầm;
   - `khongro`: không chắc.
3. Lưu file (giữ định dạng CSV) rồi chạy lệnh này để đếm:
   ```powershell
   Import-Csv "D:\Test\anh-trung-nguoi.csv" | Group-Object hypothesis, owner_verdict | Select-Object Count, Name
   ```
4. Gửi mình **bảng số đếm** mà lệnh in ra. Không gửi tên ảnh, không gửi ảnh.

## 6. Quay lại như cũ

1. Gỡ bản thử: Start Menu → **Gỡ cài đặt KiraPick Internal Test CUDA**.
2. Trước khi dùng lại bản 2.2.x, khôi phục bản sao lưu. Dùng bản làm **trước lần cài bản thử đầu tiên**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
   ```
