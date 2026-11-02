# Đo gom nhóm lần 2 — bản chẩn đoán KiraPick Internal Test CUDA 3.0.0b1.dev4a

Bản này giống bản dev3a bạn đã dùng, thêm hai phần đo:
- tìm những tấm ảnh **có thể** là cùng một khách xuất hiện hai lần;
- kiểm tra phần app đã học từ các lần sửa của bạn.

Đây không phải bản phát hành. Bước nào ra khác mô tả dưới đây thì **dừng lại**, chụp màn hình và gửi cho mình.
**Đừng làm theo file `HUONG_DAN_CAI_DAT.txt`** có trong gói tải về.

## 1. Sao lưu (bắt buộc)

1. Đóng mọi KiraPick. Chạy lệnh sau trong PowerShell; nếu nó in ra dòng chữ, đóng nốt KiraPick rồi chạy lại cho
   tới khi không in ra gì:
   ```powershell
   if (Get-Process KiraPick -ErrorAction SilentlyContinue) { "CÒN KiraPick ĐANG CHẠY - hãy đóng hết" }
   ```
2. Kiểm tra script sao lưu đúng chỗ và đúng file:
   ```powershell
   Test-Path D:\KiraPick-SaoLuu\owner_backup.ps1
   (Get-FileHash D:\KiraPick-SaoLuu\owner_backup.ps1 -Algorithm SHA256).Hash.ToLower()
   ```
   - Dòng đầu phải là `True`.
   - Dòng sau phải đúng: `96306f5dd04844322306a73da5089e293ea3588d015e87fa5a6d5ad6ab179c26`.
   - Nếu dòng đầu là `False`, hoặc mã không khớp: **dừng lại** và báo mình (mình sẽ gửi cách tải lại).
3. Sao lưu:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
4. Kiểm tra sao lưu thành công:
   - Cuối cùng phải có dòng màu xanh ghi "SHA-256: khớp", và script in ra đường dẫn bản sao lưu.
   - Mở thư mục đó, phải có file `DOC_TOI.txt`.
   - **Ghi lại đường dẫn này.** Nếu thiếu bất kỳ điều nào ở trên: **dừng lại**.
5. **Không xoá bản sao lưu cũ** làm trước lần cài bản thử đầu tiên. Đó là bản để quay về 2.2.x.

## 2. Tải bộ cài và kiểm tra mã

1. Mở **đúng** trang https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41362621002. Chỉ tải từ trang
   này (run **41362621002**), và chỉ tải gói **kirapick-windows-cuda**. Gói tải được đến ngày 02/12/2026.
2. Giải nén vào `D:\KiraPick-CUDA-dev4a\`.
3. Tính mã của **ba file cài** (chỉ ba file này):
   ```powershell
   cd D:\KiraPick-CUDA-dev4a
   Get-ChildItem -Recurse -File -Filter "KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup*" | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
   ```
4. Lệnh phải in ra **đúng 3 dòng**, và mỗi mã phải **khớp từng ký tự**:

   | File | SHA-256 |
   |---|---|
   | `KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup.exe` | `4326168d4a5ab30998cbb246e7d7019ecbbe2aca1ecefbaeae0250d6ffb66b11` |
   | `KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup-1.bin` | `134c2d16e306ab3ce9d22f914bc218b008ff3aba36782275bf3c9f944ca5a5dd` |
   | `KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup-2.bin` | `914a52a768d2917a7bf44f643cb2617c7b1d128140445cef79400d366712547d` |

   Thiếu file, thừa dòng, hoặc sai dù một ký tự: **không cài**, báo mình.

## 3. Cài

1. Chạy `KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup.exe`.
2. Bộ cài **chưa có chữ ký số**. Vì vậy Windows có thể hiện màn hình xanh SmartScreen ghi
   "Unknown publisher" (Nhà phát hành không xác định). Bộ cài được xác minh bằng **mã SHA-256 ở bước 2**, không
   phải bằng chữ ký.
   - Chỉ bấm **More info → Run anyway** khi **cả hai** điều sau đúng:
     - ba mã SHA-256 ở bước 2 đã khớp hết;
     - màn hình ghi đúng tên file `KiraPick-InternalTest-CUDA-3.0.0b1.dev4a-Setup.exe` và "Unknown publisher".
   - **Dừng lại, không chạy**, nếu thấy bất kỳ điều nào sau:
     - Windows Defender báo phát hiện virus hoặc mối đe doạ;
     - màn hình ghi một tên nhà phát hành khác;
     - tên file khác với tên ở trên.

     Chụp màn hình gửi mình.
3. Bản này **thay bản thử CUDA dev3a**. Bản KiraPick chính thức và bản thử DirectML vẫn giữ nguyên.

## 4. Chạy lệnh đo trên buổi chụp thử

Chỉ dùng **bản sao buổi chụp thử** bạn đã dùng lần trước (đã đặt tên nhóm `K1-A`…). Không dùng buổi chụp nào khác.

1. **Đóng hết KiraPick**, rồi kiểm tra lại bằng lệnh ở bước 1.1. Lệnh không được in ra gì.
2. Chạy (thay `D:\Test\BuoiThu` bằng đúng thư mục buổi chụp thử):
   ```powershell
   & "$env:LOCALAPPDATA\Programs\KiraPick-InternalTest-CUDA\KiraPick.exe" --diagnose-grouping "D:\Test\BuoiThu" "D:\Test\grouping-report-2.json" --cooccurrence-list "D:\Test\anh-nghi-trung.csv" | Out-Null
   ```
3. Mở `D:\Test\grouping-report-2.json` bằng Notepad và kiểm tra:
   - có `"ok": true` và `"network_attempts": 0`;
   - không có tên ảnh, tên khách hay tên thư mục nào.

   Nếu thấy `seems to be open`: mở KiraPick, đóng lại, rồi chạy lại lệnh.

Lệnh tạo ra hai file:
- `grouping-report-2.json`: chỉ có số liệu. **Gửi file này cho mình.**
- `anh-nghi-trung.csv`: có tên ảnh và tên nhóm. **Chỉ để bạn xem trên máy, không gửi cho ai.**

## 5. Xem các ảnh nghi trùng (trên máy bạn)

File CSV liệt kê những tấm ảnh mà hai nhóm có **cùng một tên khách**. Đây chỉ là **trường hợp nghi ngờ**: cột
`hypothesis` là phỏng đoán của app, **không phải** kết luận đó là cùng một người. Bạn là người xác nhận.

1. Mở `anh-nghi-trung.csv` bằng Excel.
2. Kiểm tra dòng tiêu đề (dòng đầu) có cột **`owner_verdict`**. Nếu không có: **dừng lại** và báo mình.
3. Với mỗi dòng, mở tấm ảnh trong KiraPick, xem kỹ, rồi điền vào `owner_verdict` **đúng một** từ:
   - `trung`: app nhận một người thành hai (ví dụ khung mặt riêng, khung người riêng);
   - `phanchieu`: có gương, kính hay màn hình phản chiếu;
   - `hainguoi`: đúng là hai người khác nhau;
   - `dattensai`: bạn đặt tên nhóm nhầm;
   - `khongro`: không chắc.
4. Lưu lại, vẫn ở dạng CSV. Sau đó đếm:
   ```powershell
   Import-Csv "D:\Test\anh-nghi-trung.csv" | Group-Object hypothesis, owner_verdict | Select-Object Count, Name
   ```
5. Gửi mình **bảng số đếm** mà lệnh in ra, cùng file `grouping-report-2.json`. **Không gửi** file CSV, tên ảnh hay
   ảnh.

## 6. Quay lại như cũ

1. Gỡ bản thử: Start Menu → **Gỡ cài đặt KiraPick Internal Test CUDA**.
2. Trước khi dùng lại bản 2.2.x, khôi phục bản sao lưu làm **trước lần cài bản thử đầu tiên**.

   **Lưu ý:** khôi phục sẽ đưa dữ liệu KiraPick về đúng như lúc sao lưu. Mọi thứ bạn làm **sau** lần sao lưu đó sẽ
   không còn hiện trong app nữa: buổi chụp đã mở, chủ thể đã đặt tên, Keep/Reject, phần đã học. Script không xoá
   chúng: dữ liệu hiện tại được đổi tên thành `KiraPick.truoc-khoi-phuc-<ngày-giờ>` trong `%LOCALAPPDATA%`. Nếu
   cần lấy lại phần nào trong đó, hỏi mình trước khi xoá.
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
   ```
