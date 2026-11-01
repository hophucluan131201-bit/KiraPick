# Đo gom nhóm chủ thể — bản chẩn đoán KiraPick Internal Test CUDA 3.0.0b1.dev3a

Bản này chỉ để **đo** xem app gom nhóm khách đúng tới đâu. Nó không phải bản phát hành.
Bước nào ra khác mô tả dưới đây thì **dừng lại**, chụp màn hình và gửi cho mình.

**Đừng làm theo file `HUONG_DAN_CAI_DAT.txt`** có trong gói tải về. Đó là hướng dẫn cũ của bản 2.2.1; trang này
thay cho nó.

## 1. Tải bộ cài và kiểm tra

1. Đăng nhập GitHub, mở https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41325328231. Đúng run
   **41325328231**.
2. Ở mục **Artifacts**, tải **kirapick-windows-cuda**. Gói này tải được đến ngày 01/12/2026.
3. Giải nén vào `D:\KiraPick-CUDA-dev3a\`.
4. Mở PowerShell và chạy hai dòng sau:
   ```powershell
   cd D:\KiraPick-CUDA-dev3a
   Get-ChildItem -Recurse KiraPick-InternalTest-CUDA-* | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
   ```
5. So kết quả với bảng dưới. Phải khớp **đủ ba dòng**; sai dù chỉ một ký tự thì **không cài**.

   | File | SHA-256 |
   |---|---|
   | `KiraPick-InternalTest-CUDA-3.0.0b1.dev3a-Setup.exe` | `01021fdc6d4852ca7a3c42eb865350d94f2a2cdf5b36d13a19f2c112378a8174` |
   | `...-Setup-1.bin` | `cf64fd2013a08c69fe8cea75370d41026d8d595abb71e0476d7cd73af4774b00` |
   | `...-Setup-2.bin` | `9d64510d25f24f7d108c55cdaec8e3cfcec690a0ecb9716814eb18a95ef09f86` |

   File `.exe` và hai file `.bin` phải nằm **chung một thư mục**.

## 2. Sao lưu (bắt buộc)

1. Đóng mọi KiraPick. Mở Task Manager và kiểm tra: không còn `KiraPick.exe` nào.
2. Chạy lệnh sao lưu, dùng đúng script bạn đã có:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
3. Cuối cùng phải có dòng màu xanh ghi "SHA-256: khớp". **Ghi lại đường dẫn bản sao lưu** mà script in ra.

## 3. Cài

Chạy file `...-Setup.exe`. Nếu SmartScreen hiện cảnh báo, bấm **More info → Run anyway**.

Bản này **thay bản thử CUDA cũ (dev1a)** trên máy bạn. Bản KiraPick chính thức và bản thử DirectML vẫn giữ nguyên.

## 4. Đánh dấu khách (chỉ trên buổi chụp mới dùng để thử)

1. Chép buổi chụp mới sang một thư mục thử, ví dụ `D:\Test\BuoiThu`. **Chỉ mở bản chép này.**
2. Mở **KiraPick Internal Test CUDA**, mở thư mục `D:\Test\BuoiThu`, rồi chạy nhận diện chủ thể như mọi khi.
3. Trong danh sách CHỦ THỂ, **đổi tên** từng nhóm (chuột phải → **Đặt tên…**) theo dạng **K + số khách + gạch
   ngang + chữ bộ đồ**:
   - `K1-A` = khách 1, bộ đồ đầu tiên; `K1-B` = khách 1, bộ đồ thứ hai; `K2-A` = khách 2, bộ đồ đầu tiên.
   - Hai nhóm là cùng một khách và cùng một bộ đồ: đặt **trùng tên** (ví dụ cả hai đều là `K1-A`).
   - Nhóm có lẫn hai người, hoặc bạn không chắc: đặt tên `?`.
   - **Không gộp nhóm nào**, chỉ đổi tên.

## 5. Chạy lệnh đo

1. **Đóng hẳn KiraPick.** Kiểm tra Task Manager không còn `KiraPick.exe`.
2. Chạy lệnh sau (thay `D:\Test\BuoiThu` bằng đúng thư mục bạn đã mở ở bước 4):
   ```powershell
   & "$env:LOCALAPPDATA\Programs\KiraPick-InternalTest-CUDA\KiraPick.exe" --diagnose-grouping "D:\Test\BuoiThu" "D:\Test\grouping-report.json" | Out-Null
   ```
   Lệnh không mở cửa sổ nào và chạy xong trong khoảng một phút.
3. Nếu báo cáo ghi `seems to be open`: mở KiraPick lên, đóng lại, rồi chạy lại lệnh.

## 6. Kiểm tra và gửi kết quả

1. Mở `D:\Test\grouping-report.json` bằng Notepad.
2. Kiểm tra trong file:
   - có dòng `"ok": true`;
   - chỉ có số và các từ tiếng Anh cố định, không có tên file hay tên khách.
3. Gửi file `grouping-report.json` cho mình. Đừng gửi file `.traceback.txt` nếu có, trừ khi mình hỏi.

## 7. Quay lại như cũ

1. Start Menu → **Gỡ cài đặt KiraPick Internal Test CUDA**.
2. Trước khi dùng lại bản 2.2.x, khôi phục bản sao lưu. Dùng bản sao lưu làm **trước lần cài bản thử đầu tiên**.
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
   ```

## Lưu ý

- Kết quả "gom tự động ban đầu" trong báo cáo là kết quả **dựng lại** từ dữ liệu hiện có, không phải bản ghi lại
  của lần chạy đầu tiên.
- Lệnh đo không bao giờ sửa ảnh hay dữ liệu buổi chụp, và không dùng mạng. Nếu KiraPick đang mở, lệnh từ chối chạy.
