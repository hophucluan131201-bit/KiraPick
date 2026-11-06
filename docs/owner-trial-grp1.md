# Ca thử GRP-1: gom người bằng tay trên một buổi chụp thật

**Mục đích:** có số liệu để anh quyết có chấp nhận phát hành bản **chưa tự gom người** hay không (GRP-1).
- Đây **không** phải nghiệm thu kỹ thuật.
- Kết quả chỉ gồm các con số: không có tên khách, không có ảnh.

**Khi nào làm:**
- Sau khi anh duyệt **build thử nội bộ** (BUILD-1). Mình sẽ gửi đường tải và mã băm.
- Bản này cài vào một thư mục riêng ("KiraPick-InternalTest"), không đè lên KiraPick đang dùng.

**Ảnh dùng để thử:** một buổi chụp thật do anh chọn.
- Dùng **bản sao** thư mục ảnh, không dùng thư mục gốc.
- Ảnh không rời máy anh.

---

## 1. Chuẩn bị (PowerShell)

Mở **PowerShell**: bấm Start, gõ `powershell`, Enter. Dán từng khối lệnh, đổi `D:\Anh\BuoiChup` thành thư mục buổi chụp anh chọn.

```powershell
# 1a. Chép buổi chụp sang một thư mục thử (ảnh gốc không bị đụng)
$goc  = "D:\Anh\BuoiChup"
$thu  = "D:\Anh\BuoiChup_GRP1_thu"
robocopy $goc $thu /E /COPY:DAT /R:1 /W:1 | Out-Null
(Get-ChildItem $thu -Recurse -File).Count

# 1b. Ghi giờ bắt đầu (để đếm thao tác từ lúc này)
$batDau = Get-Date -Format "yyyy-MM-dd HH:mm"
$batDau
```

Ghi lại con số ở 1a (số file) và giờ ở 1b.

## 2. Làm trong KiraPick

1. Mở KiraPick bản thử nội bộ → chọn **Chụp cá nhân** → **Nhập** thư mục `BuoiChup_GRP1_thu`.
2. Bấm **🧠 Nhận diện chủ thể**, chờ xong. Thanh trạng thái sẽ ghi "Đã dò người … gom người tự động chưa có trong bản này".
3. **Bấm giờ bắt đầu** (đồng hồ điện thoại).
4. Gom tay mọi người / bộ trang phục cần giao khách:
   - chọn ảnh → chuột phải → **➕ Tạo chủ thể mới**, hoặc **Gán cho chủ thể…**;
   - đặt tên, gộp, tách như bình thường.
5. Xong thì **bấm dừng đồng hồ**. Ghi lại số phút.
6. Ghi thêm:
   - số người / bộ trang phục anh đã gom;
   - các ảnh **không gom được** (menu bị khoá, ghi "chưa có người được dò") và lý do nếu nhìn ra: quay lưng, quá xa, bị che…

## 3. Lấy số liệu (PowerShell)

Lệnh này **chỉ đọc**: không sửa phiên, không gửi gì đi.

```powershell
$app = "$env:LOCALAPPDATA\Programs\KiraPick-InternalTest\KiraPick.exe"
$ra  = "$env:USERPROFILE\Desktop\kirapick-grp1.txt"
Start-Process -FilePath $app -ArgumentList @("--grp1-counts", "`"$thu`"", "--since", "`"$batDau`"", "--out", "`"$ra`"") -Wait
Get-Content $ra -Encoding UTF8
```

Lệnh tạo file `kirapick-grp1.txt` trên Desktop và in nội dung ra màn hình. Anh gửi lại cho mình phần chữ đó.

**Phần chữ hiện ra gồm:**

| Dòng | Nghĩa |
|---|---|
| `photos` | số ảnh trong buổi |
| `photos_with_a_person` | số ảnh app tìm thấy người |
| `photos_blocked_no_person` | số ảnh **không gom tay được** vì app không tìm thấy người |
| `people` | số người / bộ đã gom |
| `photos_grouped_by_hand` | số ảnh đã gom tay |
| `grouping_actions` | số thao tác gom (từ log trên máy; không có tên hay đường dẫn) |

## 4. Gửi lại cho mình

- Số phút ở bước 2.
- Phần chữ ở bước 3.
- Ước lượng của anh: với 3.0.0, cùng loại buổi chụp này thường mất bao lâu để kiểm và sửa nhóm. Ghi rõ là **ước lượng**.
- Nhận xét ngắn: chỗ nào mất công nhất.

Mình sẽ ghi kết quả vào một trang chỉ có số liệu (`docs/owner-trial-grp1-ketqua.md`), để anh quyết GRP-1.

## 5. Dọn sau khi thử (tuỳ anh)

```powershell
Remove-Item -Recurse -Force "D:\Anh\BuoiChup_GRP1_thu"   # chỉ bản sao; thư mục gốc không bị đụng
```
