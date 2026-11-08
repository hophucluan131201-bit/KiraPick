# Đo nhập ảnh và thử phân loại Media trên máy của bạn (REG-2)

Không cần bộ cài mới. Mọi thứ chạy từ mã nguồn, ở đúng các commit ghi trong script, trong thư mục
`%USERPROFILE%\KiraPick-Do`. Bạn chỉ gửi lại **con số**. Ảnh, tên ảnh và đường dẫn không rời máy.

- **Phần A** đo nhập ảnh: 3.0.0, Beta bạn đã thử và Beta đã sửa, trên cùng thư mục RAW+JPEG từng bị chậm, cùng máy, cùng
  ổ. Mất khoảng 1 giờ, có 2 lần khởi động lại máy.
- **Phần B** thử phân loại: luồng hiện tại so với 🧪 gom ảnh gần trùng, trên một sự kiện thật 300–500 ảnh. Mất khoảng 2 buổi.

Mở **Windows PowerShell** (không cần quyền quản trị). Dán **từng khối** một, chờ khối đó chạy xong rồi mới dán khối tiếp.
Thấy dòng chữ đỏ thì dừng lại, chụp màn hình gửi tôi.

---

## Phần A — Đo nhập ảnh

### A0. Tải script và kiểm mã SHA-256 (cần mạng)

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"; New-Item -ItemType Directory -Force -Path $W | Out-Null
$URL = "https://raw.githubusercontent.com/hophucluan131201-bit/KiraPick/7ffb37fd184702e0178f79bb01d0bd7a7cd8bf52/scripts/owner_measure.ps1"
Invoke-WebRequest -Uri $URL -OutFile "$W\owner_measure.ps1" -UseBasicParsing
$h = (Get-FileHash "$W\owner_measure.ps1" -Algorithm SHA256).Hash
if ($h -eq "48F234FDDD53B581600A3D84709E834BD086D586839ACF2E912F763333C9D22E") { Write-Host "OK: script đúng" -ForegroundColor Green } else { Write-Host "SAI MÃ: $h — dừng lại, báo tôi" -ForegroundColor Red }
```

### A1. Chuẩn bị (mạng, khoảng 10–20 phút)

Đóng mọi cửa sổ KiraPick. Sửa đường dẫn trong dấu ngoặc kép thành **thư mục ảnh từng bị chậm** (thư mục có cả RAW và JPEG):

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc chuan-bi -Anh "D:\Ảnh\Sự kiện bị chậm"
```

Bước này tải mã nguồn ba bản, cài Python 3.12 (nếu máy chưa có), cài thư viện, và tải các mô hình **được phép** cho bản
Beta. Nó cũng ghi lại máy, loại ổ chứa ảnh và số file trong thư mục ảnh. Cuối bước sẽ hiện "Xong bước chuẩn bị".

### A2. Đo 3.0.0 khi cache còn lạnh

**Khởi động lại máy.** Đăng nhập xong, đừng mở thư mục ảnh hay KiraPick. Mở PowerShell và dán ngay:

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc do-lanh -Ban 3.0.0
```

Một cửa sổ KiraPick tự mở, tự nhập ảnh rồi tự đóng. **Đừng bấm vào cửa sổ đó.** Máy đã bật quá 20 phút thì kết quả được
ghi là "ấm", không phải "lạnh".

### A3. Đo Beta đã sửa khi cache còn lạnh

**Khởi động lại máy lần nữa**, rồi dán:

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc do-lanh -Ban beta
```

### A4. Đo khi cache đã ấm (năm cách × hai vòng, đảo thứ tự ở vòng hai)

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc do-am
```

### A5. Đo phân tích AI, tách khỏi thời gian nhập (chỉ bản Beta đã sửa, có card đồ hoạ)

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc do-phan-tich
```

Bản 3.0.0 không được đo phân tích, vì nó mở những mô hình không được dùng, kể cả để đo nội bộ.

### A6. Tổng hợp

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc tong-hop
```

Gửi tôi file **`KiraPick-do-nhap.zip`** trên Desktop. Mỗi dòng trong file ghi:
- bản, chế độ, cache lạnh hay ấm;
- số file, **số cặp RAW+JPEG ghép được**;
- thời gian tới khi **lưới thao tác được**, lưới có đủ ảnh, **nhập xong**, mở lại;
- thời gian phân tích, ghi riêng.

File cũng ghi thư mục ảnh có đổi sau khi đo hay không (phải là `True`).

---

## Phần B — Thử phân loại Media: luồng hiện tại và 🧪 gom ảnh gần trùng

### B0. Chọn sự kiện và sao lưu

- **Một** sự kiện thật 300–500 ảnh. Tốt nhất là chụp bằng 2 máy, có sân khấu (cả ảnh toàn lẫn cận người phát biểu), booth,
  khán phòng, **hai hoạt động sát nhau** không nghỉ, và **một hoạt động chỉ có một ảnh** (dù ảnh đó hơi mờ).
- Ghi ra giấy **danh sách hoạt động** theo chương trình (khai mạc, phát biểu A, trao giải…). Danh sách này dùng để đếm hoạt
  động bị bỏ sót.
- Bản Beta chạy từ mã nguồn dùng chung dữ liệu với KiraPick đã cài. Hãy sao lưu trước:

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\src\beta\scripts\owner_backup.ps1" -Destination "$W\sao-luu"
```

### B1. Mở bản Beta đã sửa (từ mã nguồn)

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
Set-Location "$W\src\beta"; & "$W\venv\Scripts\python.exe" -m app
```

Chọn **Media sự kiện**. Tạo **hai** sự kiện từ **cùng** thư mục ảnh, đặt tên **đúng như sau**:
`Thử B — gom nhóm` và `Thử A — hiện tại`. Với mỗi sự kiện: 📂 Nhập ảnh → 🧠 Phân tích sự kiện → chờ xong.

### B2. Buổi 1: `Thử B — gom nhóm` (làm trước)

Làm B trước. Lần sau (A) bạn đã quen ảnh nên sẽ nhanh hơn, vì vậy nếu B vẫn nhanh hơn thì kết quả đó đáng tin.

1. Bật ⚙ Tuỳ chọn → **🧪 Thử nghiệm: gom ảnh gần trùng (sự kiện này)**. LỌC SỰ KIỆN → **🧪 Nhóm: chỉ ảnh gợi ý**.
2. **Bấm đồng hồ.** Làm như khi giao khách thật: duyệt từng khoảnh khắc, P ảnh giao, X ảnh hỏng, sửa cỡ cảnh / nội dung
   khi cần, ✂ tách khi hai hoạt động bị chung một khoảnh khắc.
   - Thẻ **"▣ gợi ý · +N"**: nhóm còn N ảnh nữa. Chuột phải → **🧪 Mở nhóm** để xem cả nhóm.
   - Nhóm gộp nhầm hai cảnh khác nhau: chuột phải ảnh đầu cảnh sau → **🧪 Tách ảnh này khỏi nhóm**.
   - Hai nhóm đáng ra là một: chuột phải → **🧪 Gộp nhóm này với nhóm trước**.
   - KHOẢNH KHẮC ghi **"⚠ chưa có ảnh P"**: khoảnh khắc đó chưa có ảnh giao.
3. ⤴ Xuất ảnh → Ảnh: **Ảnh đã chọn (P)** → Theo khoảnh khắc → Sao chép. **Dừng đồng hồ.** Ghi lại số phút.
4. Đối chiếu danh sách hoạt động trên giấy: hoạt động nào **không có thư mục / không có ảnh** trong thư mục giao?

### B3. Buổi 2 (ngày khác nếu được): `Thử A — hiện tại`

Làm như B2 nhưng **không bật 🧪**: duyệt toàn bộ ảnh như hiện nay. Bấm đồng hồ từ lúc bắt đầu tới khi xuất xong.

### B4. Nhãn mẫu cho ranh giới khoảnh khắc

Làm trên `Thử A — hiện tại`: bấm 🏷 Dán nhãn mẫu. Với 100–150 ảnh, bấm **B** ở mỗi ảnh **bắt đầu một hoạt động mới**,
và Q / W / R cho nét. Bấm 🏷 lần nữa để thoát.

### B5. Lấy số (chỉ con số)

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"; Set-Location "$W\src\beta"; $P = "$W\venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path "$W\thu" | Out-Null
& $P -m app --media-counts "Thử B — gom nhóm" --out "$W\thu\dem-B.json"
& $P -m app --media-counts "Thử A — hiện tại" --out "$W\thu\dem-A.json"
& $P -m app --media-score "Thử A — hiện tại" --out "$W\thu\cham.json"
Compress-Archive -Path "$W\thu\*" -DestinationPath "$([Environment]::GetFolderPath('Desktop'))\KiraPick-thu-phan-loai.zip" -Force
```

Gửi tôi `KiraPick-thu-phan-loai.zip` kèm **bảng ghi tay** này:

| | Thử B (gom nhóm) | Thử A (hiện tại) |
|---|---|---|
| Phút từ lúc bắt đầu chọn tới khi xuất xong (đồng hồ) | | |
| Hoạt động bị bỏ sót (có trong chương trình, không có ảnh giao) | | |
| Có nhóm nào trộn ảnh toàn với ảnh cận không? (B) | | — |
| Ảnh hai máy cùng khoảnh khắc: có thấy đủ ảnh gợi ý của cả hai máy không? (B) | | — |
| Hai hoạt động sát nhau: app tách được không, hay bạn phải ✂? | | |
| Hoạt động chỉ có một ảnh bị cảnh báo nét: có thấy ảnh đó trong "chỉ ảnh gợi ý" không? (B) | | — |
| Bước mất thời gian nhất | | |

---

## Các số sẽ đọc từ file gửi về

| Số đo | Lấy từ |
|---|---|
| Thời gian chọn ảnh bàn giao | đồng hồ của bạn; kiểm chéo bằng `minutes_first_to_last` |
| Số thao tác | `actions_by_kind`: P / X / sao, cỡ cảnh, nội dung, ✂ / gộp / đổi tên khoảnh khắc, Ctrl+Z, mở nhóm |
| Số thao tác sửa nhóm | `group_break` (nhóm gộp sai) + `group_join` (nhóm tách sai) |
| Gộp / tách sai khoảnh khắc | `cham.json`, mục ranh giới (từ nhãn B) |
| Khoảnh khắc bị bỏ sót | `moments_without_P` + hoạt động bị sót trong bảng ghi tay |
| Phần app tự làm | số nhóm, số ảnh gợi ý, nhóm một ảnh có cảnh báo nét (`groups`) |

Đổi logic mặc định và build tiếp chỉ làm sau khi có các số này và bạn quyết định.
