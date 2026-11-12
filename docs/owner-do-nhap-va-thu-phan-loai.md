# Đo nhập ảnh trên máy của bạn (Chụp cá nhân)

> **Media sự kiện đã bỏ (quyết định của chủ dự án, 2026-11-12).** KiraPick chỉ còn Chụp cá nhân, như 3.0.0. Phần thử
> Media và gợi ý ảnh gần trùng (A/B) trong bản trước của tài liệu này không còn dùng. Kết quả đã có:
> `docs/owner-ket-qua-reg3.md`.

Phần đo này **không bắt buộc**. Lượt đo ngày 2026-11-09 (236 JPEG) đã cho thấy Beta không chậm hơn 3.0.0. Chỉ làm lại
khi muốn đo thêm **thư mục có RAW+JPEG** hoặc **cache lạnh** (ngay sau khi khởi động lại máy).

## Bản test lấy ở đâu

**Bạn không tải bộ cài nào.** KiraPick 3.0.0a đang cài giữ nguyên. Script tự tải ba bản mã nguồn về
`C:\Users\<tên bạn>\KiraPick-Do` và chạy bằng Python (tự cài nếu máy chưa có). Cần khoảng 3 GB trống ở ổ C và mạng ở
bước 1. Thư mục ảnh chỉ được đọc; mỗi lần đo dùng một profile tạm riêng, dữ liệu KiraPick thật không bị đụng tới.

| Tên trong script | Bản | Commit |
|---|---|---|
| `3.0.0` | mã nguồn 3.0.0 | `e2fec9d` |
| `da-thu` | Beta 3.0.1b1 bạn đã thử | `d45548b` |
| `beta` | Beta hiện tại (đã bỏ Media) | `942b02e` |

Script tự dừng (chữ đỏ) nếu mã nguồn tải về không khớp SHA-256, hoặc nếu thư mục ảnh bị đổi (`unchanged=False`).

**Mở PowerShell:**
1. Bấm Start, gõ `powershell`, chọn **Windows PowerShell**.
2. Sao chép từng khối lệnh bên dưới (Ctrl+C), bấm chuột phải vào cửa sổ PowerShell để dán.
3. Chờ khối đó chạy xong rồi mới dán khối tiếp. Gặp chữ đỏ thì dừng lại, chụp màn hình gửi tôi.

## 1. Tải script và chuẩn bị (khoảng 20 phút, một lần)

Đóng KiraPick. Sửa đường dẫn trong ngoặc kép thành thư mục ảnh cần đo (tốt nhất có cả **RAW và JPEG cùng tên**).

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"; New-Item -ItemType Directory -Force -Path $W | Out-Null
$URL = "https://raw.githubusercontent.com/hophucluan131201-bit/KiraPick/24cf38db8679becdc7b93bfdf7bfe6a38a263b69/scripts/owner_measure.ps1"
Invoke-WebRequest -Uri $URL -OutFile "$W\owner_measure.ps1" -UseBasicParsing
$h = (Get-FileHash "$W\owner_measure.ps1" -Algorithm SHA256).Hash
if ($h -ne "8D672C6AC13974D8630F8E99348E4AD9BE4C6CFD187FE3B50C2F43CC99CDC1DF") {
    Write-Host "SAI MÃ SCRIPT: $h — DỪNG, không chạy gì thêm, báo tôi" -ForegroundColor Red
} else {
    Write-Host "OK: script đúng" -ForegroundColor Green
    powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc chuan-bi -Anh "D:\Ảnh\Thư mục có RAW+JPEG"
}
```

Đã chạy bước 1 lần trước rồi thì vẫn dán khối này. Script mới thay script cũ, tải bản Beta mới và đổi tên bản cũ (không
xoá).

## 2. Đo (khoảng 10 phút, tự chạy)

Muốn đo cache lạnh: **khởi động lại máy** trước, rồi dán ngay:

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc do-nhanh
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc tong-hop
```

Cửa sổ KiraPick tự mở, tự nhập rồi tự đóng; **đừng bấm vào nó**. Cuối cùng phải thấy `unchanged=True`. Gửi tôi file
**`KiraPick-do-nhap.zip`** trên Desktop (chỉ có con số).

Mỗi bản đo hai lần (lần mở đầu và lần chạy lại), mỗi lần ghi:
- thời gian tới **ảnh đầu tiên**, **mở / đánh dấu được ảnh**, **nhập xong**;
- số thẻ ảnh sau khi ghép RAW+JPEG và **số cặp**.

## Dọn sau khi xong

Đóng KiraPick rồi xoá thư mục `C:\Users\<tên bạn>\KiraPick-Do`. KiraPick 3.0.0a không bị ảnh hưởng.
