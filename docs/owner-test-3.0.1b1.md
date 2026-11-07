# Hướng dẫn thử bản Beta KiraPick 3.0.1b1 (DirectML) và 3.0.1b1a (CUDA)

Đây là **bộ cài thử**, không phải bản phát hành: chưa tag, chưa release, chưa merge `main`.
Phạm vi: phần nền LIC-1 (chỉ dùng mô hình có căn cứ quyền) + chế độ **Media sự kiện** Mốc 1.

**Quy tắc chung**
- Làm lần lượt từng bước. Bước nào ra **khác** mô tả "Phải thấy": **dừng lại**, chụp màn hình, gửi lại. Đừng đoán.
- Chỉ dùng **bản sao** của ảnh. Không mở thư mục ảnh gốc của khách.
- Mỗi bảng có cột "Đạt?": ghi **Đạt** hoặc **Không** + ghi chú ngắn.
- Thời gian: phần A–C khoảng 45 phút; phần D–F khoảng 2–3 giờ (gồm thời gian máy phân tích).

| | |
|---|---|
| Commit của bộ cài | `d45548bb35b0dedd3e37fac5c55bf259ee9eb5a6` (nhánh `beta`) |
| Lần build | https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42377412145 |
| Tải được đến | 07/12/2026 (phải đăng nhập GitHub bằng tài khoản có quyền vào repo) |

---

## 0. Đọc trước (5 phút)

**Hai bản, cài được cùng lúc, đều nằm riêng:**

| Bản | Tên trong Start Menu | Thư mục cài | Dùng cho |
|---|---|---|---|
| DirectML 3.0.1b1 | **KiraPick Beta** | `%LOCALAPPDATA%\Programs\KiraPick-Beta` | mọi máy (bản sẽ gửi người quen) |
| CUDA 3.0.1b1a | **KiraPick Beta CUDA** | `%LOCALAPPDATA%\Programs\KiraPick-Beta-CUDA` | máy có card NVIDIA (máy anh) |

- Cả hai **không đè** KiraPick 3.0.0 / 3.0.0a đang có. Lối tắt "KiraPick" cũ vẫn còn.
- **Đề xuất:** thử bản **CUDA** trước trên máy anh (đủ các phần A–F), rồi cài thêm bản **DirectML** và làm lại phần A–C
  (vì đó là bản người quen sẽ dùng).
- **Bỏ qua file `HUONG_DAN_CAI_DAT.txt`** trong gói. Đó là hướng dẫn cũ của bản 3.0.0 (ghi "bản 3.0 thay bản 2.2.x"):
  **sai** với bản Beta. Trang này thay nó.

**Dữ liệu dùng chung — đọc kỹ:**
- Mọi bản KiraPick trên máy (3.0.0, 3.0.0a, Beta, Beta CUDA) dùng **chung** thư mục `%LOCALAPPDATA%\KiraPick`.
- Mở một buổi chụp **Chụp cá nhân** cũ bằng bản Beta sẽ **nâng cấp** dữ liệu của buổi đó (app tự giữ một bản sao
  `.v7.bak`). Sau đó KiraPick 3.0.0 **không mở lại được** buổi đó (báo "phiên bản mới hơn").
  → Vì vậy **phải sao lưu ở bước A4**, và nên dùng một **bản sao** thư mục ảnh mới cho đợt thử.
- Sự kiện Media là dữ liệu mới, nằm ở `%LOCALAPPDATA%\KiraPick\media\`; bản 3.0.0 không dùng tới.

**Cách dán lệnh PowerShell:** bấm **Start**, gõ `PowerShell`, Enter. Chép **cả khối** lệnh (Ctrl+C), bấm vào cửa sổ
PowerShell, **nhấp chuột phải** để dán, rồi **Enter**. Máy không có ổ `D:` thì thay `D:` bằng `C:` trong mọi lệnh.

**Chuẩn bị trước:**
- Một **bản sao** của một buổi chụp thật (RAW + JPEG), chép sang `D:\BetaTest\BuoiChup` (khoảng 200–500 ảnh là đủ).
- Một **bản sao** của một buổi sự kiện, tốt nhất **từ hai máy ảnh**, mỗi máy một thư mục con:
  `D:\BetaTest\SuKien\MayA`, `D:\BetaTest\SuKien\MayB`.
- Một thư mục trống để xuất ảnh: `D:\BetaTest\Xuat`.

---

## A. Tải, kiểm mã, sao lưu, cài

**Nếu một lệnh báo lỗi và PowerShell hiện thêm dòng "Windows PowerShell … Copyright (C) Microsoft Corporation":** đó
là một cửa sổ PowerShell **lồng** bên trong, không còn các biến của bước A0. Gõ `exit` rồi Enter để quay về, hoặc đóng
hẳn PowerShell, mở lại và chạy lại khối A0.

### A0. Chọn bản sẽ cài (chạy lại khối này mỗi khi mở PowerShell mới)

Dán **một** trong hai khối:

```powershell
# Bản CUDA (máy có card NVIDIA)
$GOI = "kirapick-windows-cuda"; $TEN = "KiraPick-Beta-CUDA-3.0.1b1a"; $THUMUC = "KiraPick-Beta-CUDA"
$MONG = @{ "$TEN-Setup.exe" = "9baaae76598dc722f122a500e44646d8043492750c846027f4f541ad8acfa7b7";
           "$TEN-Setup-1.bin" = "4e0e7a8c298146ec0fc49c101432bd22732bd719277a17e3b45129f29718802d";
           "owner_backup.ps1" = "67dc1097627ff515d0c03f2a957e851ecd388157eb8b34754057e21afd854f51" }
"Da chon ban CUDA"
```

```powershell
# Bản DirectML (mọi máy)
$GOI = "kirapick-windows-directml"; $TEN = "KiraPick-Beta-3.0.1b1"; $THUMUC = "KiraPick-Beta"
$MONG = @{ "$TEN-Setup.exe" = "b819a20fd06aa2bfcc1ef2167ce85456d136faddc6b26c083fee80dad7e2a5f4";
           "$TEN-Setup-1.bin" = "faf387f6f7695bd61619015f2b8e53808a6f5984b96d882455572d69871ddd2d";
           "owner_backup.ps1" = "67dc1097627ff515d0c03f2a957e851ecd388157eb8b34754057e21afd854f51" }
"Da chon ban DirectML"
```

Phải thấy dòng `Da chon ban CUDA` (hoặc `Da chon ban DirectML`).

### A1. Tải gói

| Bản | Link tải (bấm, đăng nhập GitHub nếu được hỏi) | Kích thước |
|---|---|---|
| CUDA | https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42377412145/artifacts/13575883962 | ~509 MB |
| DirectML | https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42377412145/artifacts/13576780299 | ~318 MB |

Trình duyệt lưu file `kirapick-windows-cuda.zip` (hoặc `kirapick-windows-directml.zip`) vào thư mục **Downloads**.

### A2. Giải nén

Dán (cần đã chạy khối A0):
```powershell
$zip = "$env:USERPROFILE\Downloads\$GOI.zip"
if (-not (Test-Path $zip)) { "KHONG THAY $zip - kiem tra thu muc Downloads" } else {
  Expand-Archive $zip "D:\BetaTest\Goi\$GOI" -Force
  # Bản DirectML: bộ cài và owner_backup.ps1 nằm trong file BoCai.zip bên trong gói
  Get-ChildItem "D:\BetaTest\Goi\$GOI" -Recurse -File -Filter "*-BoCai.zip" | ForEach-Object {
    Expand-Archive $_.FullName "D:\BetaTest\Goi\$GOI\BoCai" -Force }
  "Da giai nen vao D:\BetaTest\Goi\$GOI"
}
```
Phải thấy `Da giai nen vao …`. Nếu thấy `KHONG THAY …`: file tải về nằm chỗ khác hoặc có tên khác (ví dụ thêm ` (1)`);
đổi tên cho đúng `kirapick-windows-cuda.zip` / `kirapick-windows-directml.zip` rồi dán lại.

### A3. Kiểm mã SHA-256

Dán cả khối. **Phải thấy đúng 3 dòng, đều bắt đầu bằng `KHOP`.** Có dòng `SAI` hoặc `THIEU` thì **dừng**, gửi lại màn
hình.
```powershell
foreach ($ten in $MONG.Keys) {
  $f = Get-ChildItem "D:\BetaTest\Goi\$GOI" -Recurse -File -Filter $ten | Select-Object -First 1
  if (-not $f) { "THIEU  $ten" }
  elseif ((Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower() -eq $MONG[$ten]) { "KHOP   $ten" }
  else { "SAI    $ten" }
}
```

### A4. Sao lưu dữ liệu KiraPick (dùng `owner_backup.ps1` vừa kiểm mã)

1. **Đóng mọi cửa sổ KiraPick** (kể cả bản 3.0.0).
2. Dán cả khối:
   ```powershell
   $bk = Get-ChildItem "D:\BetaTest\Goi\$GOI" -Recurse -File -Filter owner_backup.ps1 | Select-Object -First 1
   if (-not $bk) { "THIEU owner_backup.ps1 - dung lai, gui man hinh" } else {
     New-Item -ItemType Directory -Force D:\KiraPick-SaoLuu | Out-Null
     Copy-Item $bk.FullName D:\KiraPick-SaoLuu\owner_backup.ps1 -Force
     powershell -NoProfile -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   }
   ```
3. **Phải thấy** ở cuối một dòng **xanh** có chữ `SHA-256: khớp`. **Ghi lại** tên thư mục sao lưu vừa tạo (dạng
   `D:\KiraPick-SaoLuu\20261107-...`): cần nó nếu muốn khôi phục (phần H).
4. Máy chưa từng dùng KiraPick: script ghi thêm dòng "Chưa có … (KiraPick chưa từng chạy trên máy này)". Vẫn bình
   thường, đi tiếp.
5. Thấy chữ **đỏ** "KiraPick đang chạy": đóng hết KiraPick (kể cả biểu tượng ở khay đồng hồ) rồi dán lại khối ở bước 2.

### A5. Cài

1. Dán:
   ```powershell
   $setup = Get-ChildItem "D:\BetaTest\Goi\$GOI" -Recurse -File -Filter "$TEN-Setup.exe" | Select-Object -First 1
   if (-not $setup) { "THIEU $TEN-Setup.exe" } else { Start-Process $setup.FullName; "Da mo trinh cai dat" }
   ```
2. Nếu **SmartScreen** hiện ("Windows protected your PC"): chỉ khi bước A3 ra 3 dòng `KHOP` **và** màn hình ghi
   "Unknown publisher" → bấm **More info** → **Run anyway**.
3. Trình cài đặt: bấm **Next / Install** như bình thường, giữ thư mục mặc định. Cuối cùng bấm **Finish**.

| # | Kiểm | Phải thấy | Đạt? |
|---|---|---|---|
| A5.1 | Start Menu | Có **KiraPick Beta CUDA** (hoặc **KiraPick Beta**); lối tắt **KiraPick** cũ vẫn còn | |
| A5.2 | Trình cài đặt có tự mở app không | **Không** tự mở | |
| A5.3 | Nhấp phải `%LOCALAPPDATA%\Programs\<thư mục cài>\KiraPick.exe` → Properties → Details | "Product version" = **3.0.1b1a** (CUDA) / **3.0.1b1** (DirectML) | |

---

## B. Tự kiểm tra bản đã cài (self-test)

### B1. Chạy self-test

Dán (cần đã chạy khối A0). Lệnh chạy khoảng 1–3 phút, **không mở cửa sổ**; chờ tới khi hiện dòng `Xong, ma thoat ...`.
```powershell
$exe = "$env:LOCALAPPDATA\Programs\$THUMUC\KiraPick.exe"
$p = Start-Process $exe -ArgumentList "--self-test", "D:\BetaTest\selftest-$THUMUC.json" -Wait -PassThru
"Xong, ma thoat $($p.ExitCode) (0 = dat)"
```

### B2. Đọc kết quả

Dán:
```powershell
$r = Get-Content "D:\BetaTest\selftest-$THUMUC.json" -Raw -Encoding UTF8 | ConvertFrom-Json
"ok: $($r.ok)"; "phien ban: $($r.version) / $($r.edition)"; "thu ket noi mang: $(@($r.network_attempts).Count) lan"
"Media: $($r.media.analysed) anh, loi $($r.media.failed), mo hinh: $(($r.media.models | ForEach-Object model_id | Sort-Object -Unique) -join ', ')"
"Phien ca nhan co bang Media: $($r.media.personal_has_media_tables)"
"Card do hoa: $($r.gpu.device) - $($r.gpu.note)"
"cuDNN da nap: $($r.cuda.cudnn_dll)"; "Ly do khong dung CUDA (neu co): $($r.cuda.setup_error)"
"ORT providers: $($r.onnxruntime.providers -join ', ')"
```

| # | Dòng | Phải thấy | Đạt? |
|---|---|---|---|
| B2.1 | `Xong, ma thoat` | `0` | |
| B2.2 | `ok:` | `True` | |
| B2.3 | `phien ban:` | `3.0.1b1a / cuda` (hoặc `3.0.1b1 / directml`) | |
| B2.4 | `thu ket noi mang:` | `0 lan` | |
| B2.5 | `Media:` | `2 anh, loi 0`; mô hình **chỉ** gồm `face_detector`, `person_detector_s` (và có thể `person_detector_m`) | |
| B2.6 | `Phien ca nhan co bang Media:` | `False` | |
| B2.7 | `Card do hoa:` | Ghi lại nguyên văn (máy CUDA chưa cài cuDNN: `cpu` kèm lý do "cần cuDNN 9…") | |
| B2.8 | `cuDNN da nap:` (chỉ bản CUDA) | Chưa cài cuDNN 9: **trống**. Đã cài: đường dẫn tới `cudnn64_9.dll`. Ghi lại nguyên văn | |

### B3. (Chỉ bản CUDA) Cài cuDNN 9 rồi kiểm lại

Bản CUDA **không kèm** cuDNN (giấy phép NVIDIA). Không có cuDNN, app vẫn chạy bằng CPU.
1. Làm theo file `docs\HUONG_DAN_CUDNN.txt` trong thư mục cài
   (`%LOCALAPPDATA%\Programs\KiraPick-Beta-CUDA\docs\HUONG_DAN_CUDNN.txt`).
2. Chạy lại B1 và B2.

| # | Phải thấy | Đạt? |
|---|---|---|
| B3.1 | `cuDNN da nap:` có đường dẫn thật (ví dụ `C:\Program Files\NVIDIA\CUDNN\v9.x\bin\12.x\cudnn64_9.dll`) | |
| B3.2 | `Card do hoa:` **không** còn là `cpu` (hoặc có lý do rõ ràng nếu vẫn CPU) | |
| B3.3 | `ORT providers:` có `CUDAExecutionProvider` | |

Gửi lại file `D:\BetaTest\selftest-KiraPick-Beta-CUDA.json` (không chứa ảnh hay tên file ảnh).

---

## C. Mở hai chế độ (bắt buộc trước khi mời người test)

Mở **KiraPick Beta CUDA** (hoặc **KiraPick Beta**) từ Start Menu.

| # | Làm | Phải thấy | Đạt? |
|---|---|---|---|
| C1 | Mở app | Màn hình **chọn chế độ** với hai thẻ có hình: "Chụp cá nhân" và "Media sự kiện" | |
| C2 | Bấm thẻ **Chụp cá nhân** (hoặc phím **1**) | Cửa sổ lọc ảnh như bản 3.0.0 | |
| C3 | 📂 Nhập ảnh → chọn `D:\BetaTest\BuoiChup` | Ảnh hiện dần trong lưới; cặp RAW+JPEG hiện thành **một** ảnh | |
| C4 | ⚙ Tuỳ chọn → **⇄ Đổi chế độ…** → **Đổi chế độ** | Về màn hình chọn chế độ | |
| C5 | Bấm thẻ **Media sự kiện** (hoặc phím **2**) | Trang **Media sự kiện**: danh sách sự kiện (trống), nút **＋ Sự kiện mới**, **Mở**, **Xoá sự kiện…**, **⟵ Quay lại chọn chế độ** | |
| C6 | Bấm **⟵ Quay lại chọn chế độ** | Về màn hình chọn chế độ | |

Đạt cả C1–C6 và phần A, B → bộ cài **dùng được**. Phần D–F để chấm chất lượng.

---

## D. Chụp cá nhân — kiểm lại (hồi quy)

Bản này **khác 3.0.0** ở chỗ: **không còn gom người tự động** (mô hình nhận mặt chưa có căn cứ quyền) và **không còn
điểm thẩm mỹ**. Gom người làm **bằng tay**. Đó là đúng phạm vi, không phải lỗi.

| # | Làm (trong `D:\BetaTest\BuoiChup`) | Phải thấy | Đạt? |
|---|---|---|---|
| D1 | 🧠 Nhận diện chủ thể, rồi 📊 Phân tích ảnh | Chạy xong, không báo lỗi; dòng trạng thái ghi GPU / CPU. **Ghi lại thời gian** | |
| D2 | Xem cột **Chủ thể** | Có câu "gom người tự động chưa có trong bản này: chọn ảnh, bấm chuột phải → ➕ Tạo chủ thể mới hoặc Gán cho chủ thể…"; **không** có nhóm tự động | |
| D3 | Gom tay theo `docs/owner-trial-grp1.md` (tạo người, đưa ảnh vào, gộp, tách, Ctrl+Z) | Làm được; Ctrl+Z trả lại đúng | |
| D4 | Lọc ảnh: **P** / **X** / số sao / **F**, rồi **Ctrl+Z** vài lần | Phản hồi nhanh; Ctrl+Z lùi từng bước | |
| D5 | Tick 2–4 ảnh → **So sánh**, bấm P/X trong đó | P/X áp đúng ảnh đang trỏ | |
| D6 | ⤴ Xuất ảnh → "Ảnh đã Giữ" → `D:\BetaTest\Xuat\CaNhan` | Chỉ có ảnh đã chọn; ảnh gốc không đổi | |
| D7 | Đóng app → mở lại → Chụp cá nhân → nhập lại cùng thư mục | P/X, sao, ❤, nhóm gom tay vẫn còn | |

Sau đó **đóng app** và dán lệnh dưới để lấy số liệu gom tay (GRP-1):
```powershell
$p = Start-Process "$env:LOCALAPPDATA\Programs\$THUMUC\KiraPick.exe" -ArgumentList "--grp1-counts", "D:\BetaTest\BuoiChup", "--out", "D:\BetaTest\grp1.txt" -Wait -PassThru
"Xong, ma thoat $($p.ExitCode)"; Get-Content D:\BetaTest\grp1.txt -Encoding UTF8
```
Gửi lại `D:\BetaTest\grp1.txt` (chỉ có số).

---

## E. Media sự kiện — đi hết luồng

Mở app → thẻ **Media sự kiện**. Phím tắt có ghi ở dòng cuối cửa sổ:
**P** chọn · **X** loại · **Backspace** bỏ P/X · **F** ❤ · **Alt+0…5** sao · **T / U / C** cỡ cảnh Toàn / Trung / Cận ·
**1–5** nội dung (Sân khấu, Booth / Gian hàng, Decor, Sản phẩm, Merch; bấm lại để bỏ) · **Space** ảnh lớn ·
**← →** ảnh trước / sau · **Ctrl+Z** hoàn tác.

| # | Làm | Phải thấy | Đạt? |
|---|---|---|---|
| E1 | **＋ Sự kiện mới** → gõ tên `Thu Beta` → OK | Cửa sổ sự kiện mở, lưới trống; tiêu đề "Thu Beta" | |
| E2 | **📂 Nhập ảnh** → chọn `D:\BetaTest\SuKien\MayA` | Ảnh hiện; dòng dưới ghi "Đã nhập ảnh…" | |
| E3 | **📂 Nhập ảnh** lần nữa → `D:\BetaTest\SuKien\MayB` | Thêm ảnh máy B; dòng dưới gợi ý "🕒 Máy ảnh & giờ"; nút **🕒 Máy ảnh & giờ** hiện ra | |
| E4 | Ô lọc **Nguồn máy** | Có 2 nguồn, mỗi nguồn ghi tên máy + thư mục + số ảnh | |
| E5 | Tìm 2 ảnh **chụp cùng lúc** ở hai máy (ví dụ cùng một khoảnh khắc trao giải). Bấm ảnh máy A, giữ **Ctrl**, bấm ảnh máy B → **🕒 Máy ảnh & giờ** → **Tính từ 2 ảnh đang chọn** → OK | Ô giây của máy B đổi; sau OK ảnh hai máy xếp xen nhau đúng thứ tự thời gian | |
| E6 | **Ctrl+Z** | Dòng dưới ghi "Đã hoàn tác: chỉnh giờ…"; thứ tự trở lại như trước. Làm lại E5 để tiếp tục | |
| E7 | **🧠 Phân tích sự kiện** | Nút đổi thành **⏸ Tạm dừng**; dòng dưới đếm "Đang phân tích: x/y ảnh"; vẫn duyệt ảnh được; thẻ ảnh hiện cỡ cảnh / cảnh báo nét dần dần, kèm "(thử nghiệm)" | |
| E8 | Giữa chừng bấm **⏸ Tạm dừng**, chờ dừng, rồi bấm **🧠** lại | Chạy tiếp từ chỗ dừng, không làm lại từ đầu. **Ghi lại tổng thời gian** và số ảnh | |
| E9 | Xem dải **khoảnh khắc** ở trên lưới | Các khoảnh khắc theo khoảng nghỉ; mỗi ô ghi số ảnh và "Toàn✓/✗ Trung✓/✗ Cận✓/✗" | |
| E10 | Lọc **Cỡ cảnh: Cận**, rồi **Lỗi nét: Out nét**, rồi **Nội dung**, rồi **Trạng thái: AI gợi ý (thử nghiệm)** | Lưới chỉ còn ảnh khớp; bỏ lọc (chọn "tất cả") thì về đủ ảnh | |
| E11 | Chọn một ảnh AI xếp sai cỡ cảnh → bấm **T**, **U** hoặc **C** | Khung bên phải ghi cỡ cảnh mới kèm **✓** (đã xác nhận), không còn "(thử nghiệm)" | |
| E12 | Chọn nhiều ảnh sân khấu (Ctrl/Shift + chuột) → bấm **1** | Cả nhóm có nhãn "Sân khấu"; bấm **1** lần nữa thì bỏ | |
| E13 | Bấm vào một ảnh giữa một khoảnh khắc → **✂ Tách tại đây** | Khoảnh khắc tách làm hai, cả hai có **📌** | |
| E14 | **🧠 Phân tích sự kiện** lần nữa, chờ xong → **Ctrl+Z** | Khoảnh khắc 📌 vẫn giữ sau phân tích lại. Sau Ctrl+Z: dòng dưới có câu "**…cũng khôi phục cách chia khoảnh khắc trước đó…**"; P/X và nhãn đã xác nhận **không** đổi | |
| E15 | Chọn vài ảnh → **P**; vài ảnh → **X**; **Alt+3** cho một ảnh | Thẻ ảnh có tick xanh / mờ đi / 3 sao | |
| E16 | Chọn một ảnh đã **P** → **✎ Đổi tên** (khoảnh khắc) → trong ô gõ tên gõ vài chữ, bấm **Backspace** vài lần → **Cancel** | Backspace chỉ xoá chữ trong ô; ảnh **vẫn P**. (Ngoài ô gõ chữ, Backspace là bỏ P/X — đúng thiết kế) | |
| E17 | Nếu có ảnh **⚠ lệch giờ**: chọn nó → **⚠ Chuyển** (hoặc **⚠ Giữ**) | Ảnh chuyển sang khoảnh khắc được gợi ý (hoặc ở lại), hết ⚠ | |
| E18 | **⤴ Xuất ảnh** → Chia thư mục **Theo khoảnh khắc** → Lưu vào **Chọn…** `D:\BetaTest\Xuat\SuKien` → **Xem trước** | Hiện "N ảnh P → M tệp, K thư mục: 01 …, 02 …". Nút **Sao chép** chỉ bật **sau** khi Xem trước | |
| E19 | **Sao chép** → chờ → **Đóng** | "Đã sao chép M tệp"; trong `D:\BetaTest\Xuat\SuKien` có thư mục `01 …`, `02 …`; ảnh trùng tên từ hai máy ra **hai** file khác tên | |
| E20 | Xuất lại vào **cùng** thư mục | Không ghi đè; báo tệp đã có sẵn / đặt tên khác | |
| E21 | **⟵ Sự kiện** → chọn "Thu Beta" → **Mở** | P/X, nhãn, khoảnh khắc 📌 vẫn còn | |
| E22 | ⟵ Sự kiện → ⟵ Quay lại chọn chế độ → **Chụp cá nhân** → nhập `D:\BetaTest\SuKien\MayA` | P/X ở đây **riêng**, không lẫn với P/X của sự kiện | |

---

## F. Dán nhãn mẫu và chấm (để biết AI đúng bao nhiêu)

Làm khi có ~100–150 ảnh sự kiện **thật** (ảnh gốc của anh; ảnh album chỉ dùng khi đã rõ quyền sử dụng).

1. Trong sự kiện, bấm **🏷 Dán nhãn mẫu** (nút sáng lên). Từ giờ các phím ghi **đáp án đúng**, không đổi nhãn làm việc:
   **T / U / C** cỡ cảnh · **1–5** nội dung · **N** nét · **O** out nét · **R** trật nét · **B** ảnh này **bắt đầu** một
   khoảnh khắc mới · **0** chưa đánh giá (bỏ qua ảnh). Bấm lại cùng phím để bỏ.
2. Đi lần lượt từng ảnh (→), gắn đáp án. Khung bên phải ghi "Mẫu: …" của ảnh đang chọn.
3. **Ghi riêng** (giấy hoặc Excel, chỉ số thứ tự ảnh, không cần tên file) các ảnh thuộc ca khó:
   - có **màn LED / màn chiếu** phía sau (sáng chói và không chói);
   - **ISO cao**, nhiều nhiễu;
   - chủ thể có chi tiết **chủ yếu theo một hướng** (áo sọc, rèm, vách kẻ);
   - **áo trắng sáng** còn chi tiết.
4. Bấm **🏷** lần nữa để tắt. Đóng app.
5. Chấm (thay `Thu Beta` bằng tên sự kiện):
   ```powershell
   $p = Start-Process "$env:LOCALAPPDATA\Programs\$THUMUC\KiraPick.exe" -ArgumentList "--media-score", "`"Thu Beta`"", "--out", "D:\BetaTest\cham.json" -Wait -PassThru
   "Xong, ma thoat $($p.ExitCode) (0 = dat)"
   ```
6. Gửi lại `D:\BetaTest\cham.json` (chỉ có số, không có tên ảnh) và danh sách ca khó ở bước 3.

Ghi chú: lệnh chấm tự chia ảnh thành **tập chỉnh ngưỡng** (~40 %) và **tập chấm** (~60 %) theo khoảnh khắc; nhóm dưới
15 mẫu ghi "chưa đủ mẫu". Ngưỡng nét **giữ nguyên** trong đợt thử này.

---

## G. Gửi lại

1. Các bảng ở phần A–F (cột Đạt?).
2. File: `D:\BetaTest\selftest-*.json`, `D:\BetaTest\grp1.txt`, `D:\BetaTest\cham.json`.
3. Nhật ký (không có ảnh): dán lệnh dưới, gửi file zip tạo ra.
   ```powershell
   Compress-Archive "$env:LOCALAPPDATA\KiraPick\logs\*" D:\BetaTest\logs-beta.zip -Force; "Da tao D:\BetaTest\logs-beta.zip"
   ```
4. Thời gian ghi được: D1 (phân tích Chụp cá nhân), E8 (phân tích sự kiện), kèm số ảnh và GPU/CPU.

## H. Gỡ và quay lại như cũ

- Gỡ: Start → **Gỡ cài đặt KiraPick Beta CUDA** (hoặc **KiraPick Beta**). KiraPick 3.0.0 / 3.0.0a vẫn còn nguyên.
- Gỡ **không** xoá ảnh, không xoá dữ liệu `%LOCALAPPDATA%\KiraPick`.
- Muốn trả dữ liệu về như trước khi thử (ví dụ để bản 3.0.0 mở lại buổi chụp đã mở bằng Beta): đóng mọi KiraPick, rồi
  dán (thay `TEN_BAN_SAO_LUU` bằng tên thư mục ghi ở bước A4):
  ```powershell
  powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\TEN_BAN_SAO_LUU
  ```
  Dữ liệu hiện tại được giữ sang một bên (thư mục `KiraPick.truoc-khoi-phuc-…`), không mất.

## I. Chưa kiểm được với bộ cài này

- **Nâng cấp đè lên 3.0.0 / 3.0.0a** và việc dọn 10 file cuDNN cũ (CLEAN-2): bản Beta cài riêng nên không thử được ca
  này; cần một bản build danh tính chính thức (ví dụ 3.0.1), anh quyết định khi nào build.
- Bản portable: bản Beta không có.
