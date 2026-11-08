# Test ngắn trên máy của bạn (REG-3): nhập ảnh, luồng Media, thử gợi ý ảnh gần trùng

Không cần bộ cài mới. Ba bản chạy từ mã nguồn, ở đúng các commit ghi dưới đây, trong thư mục `%USERPROFILE%\KiraPick-Do`.
Mọi phép thử dùng **profile test riêng** và **thư mục xuất riêng**: dữ liệu KiraPick thật của bạn
(`%LOCALAPPDATA%\KiraPick`, cài đặt trong registry) không bị đọc hay ghi, và thư mục ảnh chỉ được **đọc**.

Bạn chỉ gửi lại **con số** và **bảng ghi tay**. Ảnh, tên ảnh và đường dẫn không rời máy.

## 0. Bản nào dùng cho phép thử nào

| Phép thử | Bản | Commit | Nội dung đã kiểm |
|---|---|---|---|
| Đo nhập (so sánh) | 3.0.0 | `e2fec9d` (tag v3.0.0) | SHA-256 của `app\main.py`, `app\ui\main_window.py` |
| Đo nhập (so sánh) | Beta bạn đã thử (3.0.1b1) | `d45548b` | SHA-256 của `app\main.py`, `app\ui\media_window.py` |
| Đo nhập, luồng Media, A/B | **Beta đã sửa** | **`22201ff`** | SHA-256 của 6 file: cửa sổ Media, 🧪 gom ảnh gần trùng, bộ đếm, profile test, công cụ đo |
| Script đo / mở / đếm | `owner_measure.ps1` | `ab5ab82` | SHA-256 của cả file (bước 1) |

**Vì sao ghim `22201ff`, không ghim HEAD.**
- Ghim một commit cố định thì cả bạn và người duyệt đều biết chắc đang thử đúng mã nào. Commit mới hơn có thể đến sau mà
  không làm đổi phép thử.
- `22201ff` là commit **cuối cùng có thay đổi mã của app**. Các commit sau nó chỉ đổi test, script và tài liệu, không đổi
  `app\`, `configs\` hay `packaging\`.
- Vòng trước báo cáo ghi HEAD `ffb20fe` nhưng hướng dẫn ghim `6398412`: lý do giống hệt. `ffb20fe` chỉ thêm tài liệu và
  script vào sau `6398412`; mã app hai commit đó giống nhau.
- Bản `22201ff` có:
  - 🧪 gom ảnh gần trùng: ⚙ Tuỳ chọn → 🧪, mặc định tắt;
  - các bộ đếm: mỗi thao tác một dòng nhật ký, đọc lại bằng `--media-counts`;
  - đối chiếu với ranh giới hoạt động bạn đánh dấu: `--ranh-gioi`;
  - sửa nhóm nằm trong Ctrl+Z;
  - profile test riêng.

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
$URL = "https://raw.githubusercontent.com/hophucluan131201-bit/KiraPick/ab5ab82e0a2b5b55d8b49e26d57942e2793bc6c7/scripts/owner_measure.ps1"
Invoke-WebRequest -Uri $URL -OutFile "$W\owner_measure.ps1" -UseBasicParsing
$h = (Get-FileHash "$W\owner_measure.ps1" -Algorithm SHA256).Hash
if ($h -ne "503ACCC6EC3730F0F8D1921A6639905E6F9F62BBFBD3C22872B5CB52A64F4949") {
    Write-Host "SAI MÃ SCRIPT: $h — DỪNG, không chạy gì thêm, báo tôi" -ForegroundColor Red
} else {
    Write-Host "OK: script đúng" -ForegroundColor Green
    powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc chuan-bi -Anh "D:\Ảnh\Sự kiện có RAW+JPEG"
}
```

Kết quả mong đợi: dòng xanh "OK: script đúng"; ba dòng "SHA-256 khớp" (hoặc "đúng"); cuối cùng là "Xong bước chuẩn bị … Ba
bản mã nguồn đều khớp SHA-256".

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

```powershell
$W = "$env:USERPROFILE\KiraPick-Do"
powershell -ExecutionPolicy Bypass -File "$W\owner_measure.ps1" -Buoc mo-beta
```

1. Chọn **Media sự kiện**, tạo sự kiện **`KIEM MEDIA`**, nhập cùng thư mục ảnh, bấm 🧠 Phân tích sự kiện.
2. Làm lần lượt các thao tác trong bảng 3 và điền kết quả.
3. Ở bước xuất, chọn thư mục riêng `%USERPROFILE%\KiraPick-Do\xuat\kiem-media`.

---

## 4. Thử A/B: luồng hiện tại và 🧪 gợi ý ảnh gần trùng (1–2 buổi)

### 4.1 Cùng tập ảnh, cùng trạng thái ban đầu

Mở Beta bằng `-Buoc mo-beta` như mục 3. Tạo **ba** sự kiện từ **cùng** thư mục ảnh, gõ tên **đúng** như sau:
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
ở cả ba bản; dừng khi mã nguồn bị sửa; ra `unchanged=True`; không tạo `%LOCALAPPDATA%\KiraPick`.

### Bảng 3 — Luồng Media theo 3.0.0 (Beta, sự kiện `KIEM MEDIA`)

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
