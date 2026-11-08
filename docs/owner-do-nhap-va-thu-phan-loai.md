# Test ngắn trên máy của bạn (REG-3): nhập ảnh, luồng Media, thử gợi ý ảnh gần trùng

## ĐỌC TRƯỚC: bản để test lấy ở đâu?

**Bạn không tải bộ cài nào, và không gỡ hay cài lại gì cả.**

- **KiraPick 3.0.0a đang cài trên máy giữ nguyên.** Nó không có Media, và lần test này **không dùng** nó. Dữ liệu của nó
  (ảnh đã chọn, sao, nhóm người) không bị đụng tới.
- **Bản có Media là "KiraPick Beta (test)".** Chưa có bộ cài cho bản này; nó chạy thẳng từ mã nguồn. Ở bước 1, script tự
  tải về máy bạn, vào thư mục `C:\Users\<tên bạn>\KiraPick-Do`, đúng ba bản:

  | Tên trong script | Là bản nào | Dùng để |
  |---|---|---|
  | `3.0.0` | mã nguồn của 3.0.0 (cùng chức năng với bản 3.0.0a bạn đang dùng; chỉ khác là chạy bằng CPU / DirectML) | so tốc độ nhập |
  | `da-thu` | Beta 3.0.1b1 bạn đã thử trước đây | so tốc độ nhập |
  | `beta` | **Beta đã sửa, có Media** | so tốc độ nhập, kiểm Media, thử A/B |

- Script cũng tự cài **Python 3.12** (nếu máy chưa có) và các thư viện cần thiết. Mọi thứ nằm trong `KiraPick-Do`.
  **Cần khoảng 3 GB ổ C trống** và mạng Internet ở bước 1.
- Sau bước 1, bạn tạo **một biểu tượng "KiraPick Beta (test)" trên Desktop** (bước 1b). Bấm đúp vào đó là mở bản có Media,
  giống mở một app bình thường.
- Bản test dùng **profile riêng** (`KiraPick-Do\profile-thu`). Sự kiện, cài đặt và nhật ký của nó **không trộn** với
  KiraPick 3.0.0a. Thư mục ảnh của bạn chỉ được **đọc**, không bị sửa.
- Test xong muốn dọn: đóng KiraPick rồi xoá thư mục `KiraPick-Do`. KiraPick 3.0.0a vẫn như cũ.

**Thứ tự làm:**
1. **Bước 1:** tải và chuẩn bị (một lần, khoảng 20 phút).
2. **Bước 1b:** tạo biểu tượng trên Desktop.
3. **Bước 2:** đo tốc độ nhập (khoảng 10 phút, tự chạy).
4. **Bước 3:** kiểm Media (khoảng 15 phút, bạn tự bấm).
5. **Bước 4:** thử A/B (1–2 buổi).

Gửi lại tôi **2 file zip** và **các bảng ghi tay** ở cuối tài liệu. Chỉ có con số; ảnh, tên ảnh và đường dẫn không rời máy.

**Cách mở PowerShell:**
1. Bấm nút Start, gõ `powershell`.
2. Chọn **Windows PowerShell**. Không cần "Run as administrator".
3. Mỗi khối lệnh: bấm vào khung lệnh trong tài liệu, Ctrl+C để sao chép, rồi bấm chuột phải vào cửa sổ PowerShell để dán.
   Chờ chạy xong mới dán khối tiếp. Gặp chữ **đỏ** thì dừng lại, chụp màn hình gửi tôi.

## 0. Bản nào dùng cho phép thử nào

| Phép thử | Bản | Commit | Nội dung đã kiểm |
|---|---|---|---|
| Đo nhập (so sánh) | 3.0.0 | `e2fec9d` (tag v3.0.0) | SHA-256 của `app\main.py`, `app\ui\main_window.py` |
| Đo nhập (so sánh) | Beta bạn đã thử (3.0.1b1) | `d45548b` | SHA-256 của `app\main.py`, `app\ui\media_window.py` |
| Đo nhập, luồng Media, A/B | **Beta đã sửa** | **`743b76a`** | SHA-256 của 6 file: cửa sổ Media, 🧪 gom ảnh gần trùng, bộ đếm, profile test, công cụ đo |
| Script đo / mở / đếm | `owner_measure.ps1` | `cda80fe` | SHA-256 của cả file (bước 1) |

**Vì sao ghim `743b76a`, không ghim HEAD.**
- Ghim một commit cố định thì cả bạn và người duyệt đều biết chắc đang thử đúng mã nào. Commit mới hơn có thể đến sau mà
  không làm đổi phép thử.
- `743b76a` là commit **cuối cùng có thay đổi mã của app**. Các commit sau nó chỉ đổi test, script và tài liệu, không đổi
  `app\`, `configs\` hay `packaging\`.
- Vòng trước báo cáo ghi HEAD `ffb20fe` nhưng hướng dẫn ghim `6398412`: lý do giống hệt. `ffb20fe` chỉ thêm tài liệu và
  script vào sau `6398412`; mã app hai commit đó giống nhau.
- Bản `743b76a` có:
  - 🧪 gom ảnh gần trùng: ⚙ Tuỳ chọn → 🧪, mặc định tắt;
  - các bộ đếm: mỗi thao tác một dòng nhật ký, đọc lại bằng `--media-counts`;
  - đối chiếu với ranh giới hoạt động bạn đánh dấu: `--ranh-gioi`;
  - sửa nhóm nằm trong Ctrl+Z;
  - profile test riêng;
  - các lệnh đo / đếm in được tiếng Việt khi đầu ra bị chuyển hướng. Lỗi này do CI phát hiện; `22201ff` còn bị.

**Script tự dừng** (chữ đỏ, mã thoát 1) khi:
- mã nguồn tải về không khớp SHA-256. Bản sai được đổi tên, không bị xoá;
- thư mục ảnh thay đổi sau khi đo (`unchanged=False`).

Mở **Windows PowerShell** (không cần quyền quản trị). Dán **từng khối**, chờ xong rồi mới dán khối tiếp. Gặp chữ đỏ thì
dừng lại, chụp màn hình gửi tôi.

---

## 1. Tải script, kiểm SHA-256, chuẩn bị (cần mạng, 10–20 phút)

Đóng mọi cửa sổ KiraPick. Sửa đường dẫn trong ngoặc kép thành **thư mục ảnh của một sự kiện thật có cả RAW và JPEG cùng
tên** (nếu được, chính thư mục từng nhập chậm):

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"; New-Item -ItemType Directory -Force -Path $W | Out-Null
$URL = "https://raw.githubusercontent.com/hophucluan131201-bit/KiraPick/cda80fe6230ea8941d095ae54f271815d1817a7e/scripts/owner_measure.ps1"
Invoke-WebRequest -Uri $URL -OutFile "$W\owner_measure.ps1" -UseBasicParsing
$h = (Get-FileHash "$W\owner_measure.ps1" -Algorithm SHA256).Hash
if ($h -ne "74B4537E11F89DB95624AF8D48E5B3C9909ABF0BC810DF8EB77E6F18657D7958") {
    Write-Host "SAI MÃ SCRIPT: $h — DỪNG, không chạy gì thêm, báo tôi" -ForegroundColor Red
} else {
    Write-Host "OK: script đúng" -ForegroundColor Green
    powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc chuan-bi -Anh "D:\Ảnh\Sự kiện có RAW+JPEG"
}
```

Kết quả mong đợi: dòng xanh "OK: script đúng"; ba dòng "SHA-256 khớp" (hoặc "đúng"); cuối cùng là "Xong bước chuẩn bị … Ba
bản mã nguồn đều khớp SHA-256".

---

## 1b. Tạo biểu tượng "KiraPick Beta (test)" trên Desktop

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\KiraPick Beta (test).lnk")
$lnk.TargetPath = "powershell.exe"
$lnk.Arguments = "-ExecutionPolicy Bypass -WindowStyle Minimized -File `"$W\owner_measure.ps1`" -Buoc mo-beta"
$lnk.WorkingDirectory = $W
$ico = "$W\src\beta\packaging\kirapick.ico"; if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Save()
Write-Host "Đã tạo biểu tượng KiraPick Beta (test) trên Desktop" -ForegroundColor Green
```

Bấm đúp vào biểu tượng:
1. Một cửa sổ PowerShell nhỏ mở thu gọn dưới thanh tác vụ. **Đừng đóng nó**; nó tự đóng khi bạn đóng KiraPick.
2. Sau vài giây, KiraPick hiện **màn hình chọn chế độ**: Chụp cá nhân / **Media sự kiện**.

Nếu biểu tượng không mở được, dùng lệnh thay thế:
`powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\KiraPick-Do\owner_measure.ps1" -Buoc mo-beta`

---

## 2. Đo nhập nhanh (khoảng 10 phút)

Nếu được, **khởi động lại máy** trước. Khi đó lần đo đầu là "cache lạnh"; script tự ghi theo thời gian máy đã bật.

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc do-nhanh
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc tong-hop
```

Cửa sổ KiraPick tự mở, tự nhập rồi tự đóng; **đừng bấm vào nó**. Mỗi bản đo hai lần: **lần mở đầu** (phiên mới, chưa có
ảnh thu nhỏ) và **lần chạy lại** (cùng thư mục, phiên đã có). Mỗi lần ghi ba mốc tính từ lúc bấm nhập:
- **ảnh đầu tiên hiện ra**;
- **mở và đánh dấu được ảnh**: công cụ chọn một ảnh, bấm P và cuộn lưới;
- **nhập xong**.

Kèm theo đó là số **thẻ ảnh sau khi ghép RAW+JPEG** và số **cặp**.

Kết quả mong đợi ở cuối: `unchanged=True` (số file, tổng dung lượng và giờ sửa mới nhất trong thư mục ảnh y như trước khi
đo). Thấy `unchanged=False` thì script dừng; đừng dùng thư mục đó nữa và báo tôi ngay.

Gửi tôi **`KiraPick-do-nhap.zip`** trên Desktop.

**Đo đầy đủ** chỉ làm khi bản Beta chậm hơn 3.0.0 rõ rệt:
- `-Buoc do-lanh -Ban 3.0.0`, khởi động lại máy, `-Buoc do-lanh -Ban beta`;
- `-Buoc do-am`;
- `-Buoc do-phan-tich`, đo phân tích AI riêng, chỉ trên Beta;
- `-Buoc tong-hop`.

---

## 3. Kiểm nhanh luồng Media theo 3.0.0 (khoảng 15 phút)

Bấm đúp biểu tượng **KiraPick Beta (test)** trên Desktop (bước 1b).

1. Chọn **Media sự kiện**, tạo sự kiện **`KIEM MEDIA`**, nhập cùng thư mục ảnh, bấm 🧠 Phân tích sự kiện.
2. Làm lần lượt các thao tác trong bảng 3 và điền kết quả.
3. Ở bước xuất, chọn thư mục riêng `%USERPROFILE%\KiraPick-Do\xuat\kiem-media`.

---

## 4. Thử A/B: luồng hiện tại và 🧪 gợi ý ảnh gần trùng (1–2 buổi)

### 4.1 Cùng tập ảnh, cùng trạng thái ban đầu

Mở **KiraPick Beta (test)** từ biểu tượng trên Desktop, chọn **Media sự kiện**. Tạo **ba** sự kiện từ **cùng** thư mục ảnh, gõ tên **đúng** như sau:
`RANH GIOI`, `THU A`, `THU B`. Với từng sự kiện: 📂 Nhập ảnh → 🧠 Phân tích sự kiện → chờ xong. **Chưa sửa gì.**

### 4.2 Ranh giới hoạt động theo đánh giá của bạn (trước mọi tách / gộp tay)

1. Trong `RANH GIOI`, bấm 🏷 Dán nhãn mẫu.
2. Đi hết ảnh theo thời gian. Ở **ảnh đầu tiên của mỗi hoạt động** (theo bạn), bấm **B**.
3. Bấm 🏷 lần nữa để thoát. **Từ đây không sửa gì trong `RANH GIOI` nữa.**
4. Ghi ra giấy (chỉ giữ ở máy bạn), mỗi trường hợp một hoặc vài ảnh, để kiểm ở bảng 4:
   - một **chuỗi ảnh gần trùng** trong cùng một hoạt động;
   - **hai hoạt động khác nhau diễn ra sát nhau**;
   - một **hoạt động chỉ có một ảnh quan trọng**.

### 4.3 Lượt B rồi lượt A (cùng cách làm, mỗi lượt bấm đồng hồ)

Làm **B trước**. Lần sau (A) bạn đã quen ảnh nên sẽ nhanh hơn; vì vậy nếu B vẫn nhanh hơn thì kết quả đó đáng tin.

- **`THU B`**:
  1. Bật ⚙ Tuỳ chọn → **🧪 Thử nghiệm: gom ảnh gần trùng (sự kiện này)**.
  2. Chọn LỌC SỰ KIỆN → **🧪 Nhóm: chỉ ảnh gợi ý**.
  3. Chọn ảnh giao như thật: P / X, ✂ tách khoảnh khắc khi cần. Thẻ "▣ gợi ý · +N" có N ảnh nữa trong nhóm; chuột phải →
     🧪 Mở nhóm. Nhóm sai thì chuột phải → 🧪 Tách ảnh khỏi nhóm / 🧪 Gộp với nhóm trước (Ctrl+Z hoàn tác được).
  4. **Kiểm cả danh sách gợi ý lẫn lưới đầy đủ** (🧪 Nhóm: tất cả ảnh) cho ba trường hợp đã ghi ở 4.2.
  5. ⤴ Xuất ảnh → Ảnh đã chọn (P) → Theo khoảnh khắc → thư mục riêng `%USERPROFILE%\KiraPick-Do\xuat\B`.
- **`THU A`**: làm như trên nhưng **không bật 🧪**, duyệt cả lưới. Xuất vào `%USERPROFILE%\KiraPick-Do\xuat\A`.

### 4.4 Lấy số

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc dem-ab
```

Gửi tôi **`KiraPick-thu-phan-loai.zip`** trên Desktop, kèm các bảng ghi tay dưới đây. File zip có kết quả của **cả hai lượt**:
- so với ranh giới bạn đánh dấu: khoảnh khắc gộp sai / tách sai, hoạt động không có ảnh P, nhóm 🧪 trộn hai hoạt động;
- cách chia khoảnh khắc ban đầu của app;
- số thao tác;
- **số lần tách / gộp tay, ghi riêng**: khoảnh khắc ✂ / gộp / chuyển ảnh, và nhóm 🧪 tách / gộp.

---

## Bảng kết quả (bạn điền)

Cột **Bằng chứng**:
- **CI** = đã kiểm tự động trên máy Windows sạch (máy CI, ảnh tổng hợp và ảnh NASA công cộng), không phải máy bạn;
- **Chờ** = chỉ bạn kiểm được, trên máy và ảnh thật của bạn.

### Bảng 2 — Nhập ảnh (điền từ `ket-qua.txt`, hoặc chỉ gửi file zip)

| Bản | Chế độ | Lần | Cache | Thẻ ảnh sau ghép / cặp | Ảnh đầu (s) | Mở/đánh dấu được (s) | Nhập xong (s) | Bằng chứng |
|---|---|---|---|---|---|---|---|---|
| 3.0.0 | cá nhân | mở đầu | | | | | | Chờ |
| 3.0.0 | cá nhân | chạy lại | | | | | | Chờ |
| Đã thử | cá nhân | mở đầu | | | | | | Chờ |
| Đã thử | Media | mở đầu | | | | | | Chờ |
| Beta | cá nhân | mở đầu | | | | | | Chờ |
| Beta | Media | mở đầu | | | | | | Chờ |
| `unchanged` | — | — | — | — | — | — | (phải là True) | Chờ |

Đã có bằng chứng CI cho chính quy trình đo: script chạy trọn trên Windows PowerShell 5.1; 60 NEF + 20 JPEG ghép đúng 20 cặp
ở cả ba bản; dừng khi mã nguồn bị sửa; ra `unchanged=True`; không tạo `%LOCALAPPDATA%\KiraPick`
([run 42508189761](https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42508189761)).

### Bảng 3 — Luồng Media theo 3.0.0 (Beta, sự kiện `KIEM MEDIA`)

Bằng chứng CI: các test thao tác thật của cửa sổ Media chạy đạt trên Windows
([run 42508195716](https://github.com/hophucluan131201-bit/KiraPick/actions/runs/42508195716)) và trên Linux.

| Thao tác | Làm thế nào | Đúng? (có/không, ghi chú) | Bằng chứng |
|---|---|---|---|
| Chọn / loại | P, X; U bỏ | | CI (test thao tác thật) + Chờ |
| Sao | phím 1–5, 0 xoá | | CI + Chờ |
| Yêu thích | F | | CI + Chờ |
| So sánh 2–4 ảnh | Ctrl+click 2–4 ảnh, C; Esc về lưới | | CI + Chờ |
| Xoay khi xem | ⟳ Xoay xem; mở lại ảnh gốc bằng phần mềm khác: không bị xoay | | CI + Chờ |
| Hoàn tác | Ctrl+Z sau P, sao, nhãn | | CI + Chờ |
| Xuất bản sao | ⤴ Xuất ảnh → `xuat\kiem-media`; ảnh gốc còn nguyên | | CI + Chờ |
| ✂ Tách khoảnh khắc rồi Ctrl+Z | khoảnh khắc trở lại như trước? | | CI + Chờ |
| Gộp khoảnh khắc rồi Ctrl+Z | khoảnh khắc trở lại như trước? | | CI + Chờ |
| Phím 0–5 và Alt+1–5 khi đang gõ ô tìm tên file | không đổi sao / nội dung | | CI + Chờ |

Ghi chú: báo cáo vòng trước ghi "ngoài Ctrl+Z" là nói về **sửa nhóm 🧪**, không phải tách / gộp **khoảnh khắc**. Tách /
gộp khoảnh khắc luôn nằm trong Ctrl+Z. Từ commit `b12f284`, sửa nhóm 🧪 cũng nằm trong Ctrl+Z.

### Bảng 4 — A/B gợi ý ảnh gần trùng

| | Lượt B (🧪 bật) | Lượt A (hiện tại) | Bằng chứng |
|---|---|---|---|
| Phút từ lúc bắt đầu chọn tới khi xuất xong (đồng hồ) | | | Chờ |
| Chuỗi ảnh gần trùng trong một hoạt động: gom thành một nhóm? | | — | CI (ảnh tổng hợp) + Chờ |
| Hai hoạt động sát nhau: có nhóm nào trộn hai hoạt động? (danh sách gợi ý / lưới đầy đủ) | / | — | CI + Chờ |
| Hai hoạt động sát nhau: app tách khoảnh khắc, hay bạn phải ✂? | | | Chờ |
| Hoạt động chỉ một ảnh quan trọng: ảnh đó **có được gợi ý**? (danh sách gợi ý / lưới đầy đủ) | / | — / có | CI + Chờ |
| Hoạt động bị bỏ sót khi giao (có trong chương trình, không có ảnh trong thư mục xuất) | | | Chờ |
| Số lần tách / gộp **khoảnh khắc** bằng tay (từ file zip) | | | Chờ |
| Số lần tách / gộp **nhóm 🧪** bằng tay (từ file zip) | | — | Chờ |
| Bước mất thời gian nhất | | | Chờ |

---

## Nghiệm thu riêng: bốn nhóm phân loại Media

Phần này **không** thuộc lượt test ngắn. Ghi ở đây để không lẫn với kết quả A/B ở trên.

| Nhóm nhãn | Mốc 1 hiện có | Nghiệm thu cần | Trạng thái |
|---|---|---|---|
| Cỡ cảnh (Toàn / Trung / Cận) | app gợi ý, người sửa Alt+T/U/C | nhãn mẫu 100–150 ảnh thật + `--media-score` | Chờ ảnh thật |
| Nội dung (Sân khấu, Booth / Gian hàng, Decor, Sản phẩm, Merch) | gán tay Alt+1–5 (gợi ý bằng AI đang tắt) | thời gian và số thao tác gán tay trong lượt A/B | Chờ |
| Người và vai trò | ngoài Mốc 1 | — | Ngoài phạm vi |
| Lỗi nét (Out nét / Trật nét) | app cảnh báo, người sửa Q / W / R | nhãn mẫu + `--media-score` | Chờ ảnh thật |

Đổi logic phân loại mặc định và build tiếp chỉ làm sau khi có các số trên và bạn quyết định.
