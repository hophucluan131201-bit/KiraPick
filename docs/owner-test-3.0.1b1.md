# Thử bản Beta KiraPick 3.0.1b1 (DirectML) / 3.0.1b1a (CUDA) — BUILD-1

Bộ cài thử, **không phải bản phát hành**: không tag, không release, chưa merge `main`. Phạm vi: phần nền LIC-1 + Media
Mốc 1. Bước nào ra khác mô tả thì **dừng lại**, chụp màn hình và gửi lại.

| | |
|---|---|
| Commit | `d45548bb35b0dedd3e37fac5c55bf259ee9eb5a6` (nhánh `beta`) |
| Lần build | https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42377412145 |
| Gói DirectML | `kirapick-windows-directml` (~318 MB): https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42377412145/artifacts/13576780299 |
| Gói CUDA | `kirapick-windows-cuda` (~509 MB): https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42377412145/artifacts/13575883962 |
| Tải được đến | 07/12/2026 (phải đăng nhập GitHub) |

## Đọc trước

- **Bỏ qua file `HUONG_DAN_CAI_DAT.txt`** có trong gói và trong thư mục cài. Đó là hướng dẫn của bản 3.0.0 ("bản 3.0 thay
  bản 2.2.x", tên file 3.0.0): **sai** với bản Beta này. Trang này thay nó. Bản build sau sẽ kèm hướng dẫn đúng.
- Bản Beta cài **riêng**: "KiraPick Beta" / "KiraPick Beta CUDA", thư mục `%LOCALAPPDATA%\Programs\KiraPick-Beta…`, mục
  gỡ riêng. **Không đè** KiraPick 3.0.0 / 3.0.0a đang có.
- **Dữ liệu dùng chung** `%LOCALAPPDATA%\KiraPick` với bản 3.0.0. Mở một buổi chụp cũ bằng bản Beta sẽ nâng cấp dữ liệu
  buổi đó (có bản sao `.v7.bak`); sau đó bản 3.0.0 báo "phiên bản mới hơn" với buổi đó. **Sao lưu trước** (bước 1).
- Không có bản portable trong đợt này (bản Beta chỉ có bộ cài).

## 1. Sao lưu, tải, kiểm SHA-256, cài

1. Đóng mọi KiraPick, rồi sao lưu (dùng `owner_backup.ps1` trong gói, hoặc bản cũ ở `D:\KiraPick-SaoLuu`). Cuối cùng
   phải có dòng xanh "SHA-256: khớp".
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
2. Tải gói ở bảng trên, giải nén vào `D:\KiraPick-Beta`.
3. Kiểm mã SHA-256 (phải **khớp đúng** bảng dưới):
   ```powershell
   Get-ChildItem D:\KiraPick-Beta -Recurse -File | Get-FileHash -Algorithm SHA256 | Format-Table Hash, Path -AutoSize
   ```

   | File | Byte | SHA-256 |
   |---|---|---|
   | `KiraPick-Beta-3.0.1b1-Setup.exe` | 2 122 534 | `b819a20fd06aa2bfcc1ef2167ce85456d136faddc6b26c083fee80dad7e2a5f4` |
   | `KiraPick-Beta-3.0.1b1-Setup-1.bin` | 157 352 491 | `faf387f6f7695bd61619015f2b8e53808a6f5984b96d882455572d69871ddd2d` |
   | `KiraPick-Beta-3.0.1b1-BoCai.zip` | 158 992 986 | `854405da1d1fde7737bd2ae5d380b141526e145ccf2c21d87f08035023c94d13` |
   | `KiraPick-Beta-CUDA-3.0.1b1a-Setup.exe` | 2 124 077 | `9baaae76598dc722f122a500e44646d8043492750c846027f4f541ad8acfa7b7` |
   | `KiraPick-Beta-CUDA-3.0.1b1a-Setup-1.bin` | 507 886 614 | `4e0e7a8c298146ec0fc49c101432bd22732bd719277a17e3b45129f29718802d` |
   | `owner_backup.ps1` (gói CUDA) | 6 265 | `67dc1097627ff515d0c03f2a957e851ecd388157eb8b34754057e21afd854f51` |

4. Cài: chạy `KiraPick-Beta-3.0.1b1-Setup.exe` (hoặc bản CUDA). SmartScreen hiện thì bấm **More info → Run anyway**,
   chỉ khi mã đã khớp và màn hình ghi "Unknown publisher". Start Menu phải có thêm **KiraPick Beta** (hoặc **KiraPick
   Beta CUDA**); các lối tắt KiraPick cũ vẫn còn.

## 2. Ba việc anh kiểm trước khi mời người test (checklist G5)

| # | Làm | Phải thấy | Đạt? |
|---|---|---|---|
| 1 | Tự kiểm tra bản đã cài (PowerShell, dòng dưới) | Mở `D:\kq-beta.json`: `"ok": true`, `"network_attempts": []`, `"version": "3.0.1b1"` (CUDA: `3.0.1b1a`), mục `media` có `"personal_has_media_tables": false` | |
| 2 | Mở **KiraPick Beta** → màn chọn chế độ → **Chụp cá nhân** → nhập một thư mục ảnh đã sao chép | Mở được, ảnh hiện; không có điểm thẩm mỹ, không gom người tự động (đúng phạm vi) | |
| 3 | ⇄ Đổi chế độ → **Media sự kiện** → ＋ Sự kiện mới → 📂 Nhập ảnh → 🧠 Phân tích sự kiện | Mở được; nhãn hiện dần, có "(thử nghiệm)" | |
| 4 | Bản CUDA: `cuda.cudnn_dll` trong `D:\kq-beta.json` | Chưa cài cuDNN 9: `null` và app chạy CPU kèm lý do; đã cài: đường dẫn thật của `cudnn64_9.dll` | |

```powershell
& "$env:LOCALAPPDATA\Programs\KiraPick-Beta\KiraPick.exe" --self-test D:\kq-beta.json
# bản CUDA:
& "$env:LOCALAPPDATA\Programs\KiraPick-Beta-CUDA\KiraPick.exe" --self-test D:\kq-beta.json
```

Đạt cả bốn thì làm tiếp checklist `docs/checklist-test-ban-day-du.md` (C, D, E, F) và mới mời người quen.

## 3. Ca nâng cấp (A2) chưa kiểm được với bản này

Bản Beta cài **bên cạnh** bản 3.0.0, nên ca "cài đè lên 3.0.0 / 3.0.0a" (A2, B5 nâng cấp, A4 CLEAN-2) **không** kiểm
được bằng bộ cài này: cần một bản build có danh tính chính thức (ví dụ 3.0.1), do anh quyết định khi nào build.

## 4. Gỡ

Start Menu → **Gỡ cài đặt KiraPick Beta** (hoặc Beta CUDA). KiraPick 3.0.0 và dữ liệu vẫn còn.
