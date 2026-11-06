# Thử bản nội bộ KiraPick 3.0.1b1.dev1a (CUDA) — Màn hình chọn chế độ

Bản thử nội bộ, không phải bản phát hành.

- Bản này cài **bên cạnh** KiraPick 3.0.0 (tên "KiraPick Internal Test CUDA") và thay bản thử nội bộ CUDA cũ, nếu máy
  có.
- Nó dùng **chung dữ liệu** với KiraPick 3.0.0.
- Bước nào ra khác mô tả thì **dừng lại**, chụp màn hình và gửi mình.

Cách dán lệnh: bấm Start, gõ `PowerShell`, Enter. Chép lệnh (Ctrl+C), nhấp chuột phải vào cửa sổ PowerShell để dán,
rồi Enter.

## 1. Sao lưu, tải, kiểm tra mã, cài

1. **Đóng mọi KiraPick**, rồi sao lưu. Cuối cùng phải có dòng xanh "SHA-256: khớp".
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
2. **Tải** (phải đăng nhập GitHub): https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42153256534/artifacts/13477167087
   (gói **kirapick-windows-cuda**, khoảng 3,1 GB, tải được đến 06/12/2026; build từ commit `efddabe` trên nhánh
   `internal-build/3.0.1b1.dev1`).
   **Không** làm theo file `HUONG_DAN_CAI_DAT.txt` trong gói (đó là hướng dẫn cho bản 3.0.0); làm theo file này.
3. **Giải nén** vào `D:\KiraPick-3.0.1-test`:
   ```powershell
   Expand-Archive "$env:USERPROFILE\Downloads\kirapick-windows-cuda.zip" D:\KiraPick-3.0.1-test -Force; "Da giai nen"
   ```
4. **Kiểm tra mã.** Dán cả khối. Phải thấy **3 dòng, đều bắt đầu bằng `KHOP`**; có dòng khác thì **không cài**.
   ```powershell
   $mong = @{
     "KiraPick-InternalTest-CUDA-3.0.1b1.dev1a-Setup.exe"   = "444cd126e14f6a33357b72b2941fa167a2fd856d7597788009da420bf0db4a08"
     "KiraPick-InternalTest-CUDA-3.0.1b1.dev1a-Setup-1.bin" = "1d3a0a762125e62fa5a5c84e7d303240d57de031c661e5fc86cea89dd80ff873"
     "KiraPick-InternalTest-CUDA-3.0.1b1.dev1a-Setup-2.bin" = "d98521992ebab48b56b82b15d1d8a0da05ee9b9ed30fe1f16884217035bea056"
   }
   foreach ($ten in $mong.Keys) {
     $f = Get-ChildItem D:\KiraPick-3.0.1-test -Recurse -File -Filter $ten | Select-Object -First 1
     if (-not $f) { "THIEU  $ten" }
     elseif ((Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower() -eq $mong[$ten]) { "KHOP   $ten" }
     else { "SAI    $ten" }
   }
   ```
5. **Cài:** dán lệnh dưới (hoặc nhấp đúp file `KiraPick-InternalTest-CUDA-3.0.1b1.dev1a-Setup.exe`).
   ```powershell
   Start-Process (Get-ChildItem D:\KiraPick-3.0.1-test -Recurse -File -Filter "KiraPick-InternalTest-CUDA-3.0.1b1.dev1a-Setup.exe" | Select-Object -First 1).FullName
   ```
   - Nếu SmartScreen hiện ra: bấm **More info → Run anyway**, chỉ khi mã đã khớp và màn hình ghi "Unknown publisher".
   - Mở app từ Start: **KiraPick Internal Test CUDA**.

## 2. Bảng kiểm tra

Chỉ mở **bản sao** của một buổi chụp. Mỗi dòng ghi Đạt hoặc Không, kèm ghi chú nếu có.

| # | Làm | Phải thấy | Đạt? |
|---|---|---|---|
| 1 | Mở app | Màn hình "Chọn chế độ làm việc" với hai thẻ có ảnh; thẻ "Chụp cá nhân" có viền xanh | |
| 2 | Bấm **Tab**, rồi **Shift+Tab** | Viền xanh chuyển sang "Media sự kiện" rồi quay về | |
| 3 | Bấm phím **2** (hoặc bấm chuột vào thẻ Media) | Trang "Media sự kiện — Beta · đang phát triển", có nút Quay lại | |
| 4 | Bấm **Esc** | Về lại màn hình chọn chế độ | |
| 5 | Bấm đúp thật nhanh vào thẻ "Chụp cá nhân" | Chỉ mở **một** cửa sổ lọc ảnh, giống bản 3.0.0 | |
| 6 | Kéo nhỏ cửa sổ chọn chế độ tới mức nhỏ nhất | Hai thẻ xếp dọc, chữ đọc được, bấm được | |
| 7 | Trong cửa sổ lọc ảnh: Nhập ảnh, Nhận diện, Phân tích, So sánh, P/X, Ctrl+Z, Xuất ảnh | Mọi thứ như bản 3.0.0 (làm nhanh các bước chính của bảng 11 bước) | |
| 8 | ⚙ Tuỳ chọn → **⇄ Đổi chế độ…** khi đang mở thư mục → **Ở lại** | Không có gì thay đổi, ảnh đang xem giữ nguyên | |
| 9 | ⚙ → **⇄ Đổi chế độ…** → **Đổi chế độ** | Về màn hình chọn chế độ; chọn lại "Chụp cá nhân", nhập lại cùng thư mục: Giữ/Loại, sao, nhóm vẫn còn | |
| 10 | Đóng app, mở lại | Lại thấy màn hình chọn chế độ (lần nào cũng hiện) | |

Gửi lại bảng này, kèm file `%LOCALAPPDATA%\KiraPick\logs\kirapick.log`.

## 3. Quay lại như cũ

- Gỡ bản thử: Start → **Gỡ cài đặt KiraPick Internal Test CUDA**. KiraPick 3.0.0 vẫn nằm riêng, không bị ảnh hưởng.
- Cần thì khôi phục bản sao lưu ở bước 1. Thay `TEN_BAN_SAO_LUU` bằng tên thư mục sao lưu:
  ```powershell
  powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\TEN_BAN_SAO_LUU
  ```
