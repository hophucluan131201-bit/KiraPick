# KiraPick beta — Bảng kiểm tra trên Windows của chủ dự án (BR-03)

Làm trên máy của bạn (Windows 10/11), với **bản thử nội bộ** build từ commit `423074b` theo
`docs/internal-test-build.md` — chỉ sau khi bạn cho phép build. Với mỗi dòng ghi **Đạt** / **Lỗi** (+ ảnh chụp màn
hình app nếu lỗi; không cần gửi ảnh chụp của bạn). Mất khoảng 60–90 phút.

> **Bảng này là kiểm tra chấp nhận, KHÔNG phải lệnh phát hành.** Làm xong và "Đạt" hết nghĩa là bản thử dùng được
> trên máy bạn. Phát hành beta (gắn tag, đăng bản cài lên GitHub) là một quyết định riêng: cần báo cáo quyết định
> phát hành sau bước này và **lệnh phát hành rõ ràng** của bạn.

## 0. Chuẩn bị (10 phút)

- Một **thẻ nhớ dùng để thử** có ảnh RAW + JPEG (máy Nikon), và đầu đọc thẻ. **Mọi file trên thẻ phải được sao lưu
  sang chỗ khác trước** (chép cả thư mục DCIM vào ổ cứng). Các bước có **rút thẻ khi đang chạy** (2.3, 6.3, 7.2) chỉ
  làm với thẻ thử này — không bao giờ với thẻ duy nhất đang chứa ảnh của khách. Rút thẻ khi máy đang đọc là việc
  KiraPick chỉ đọc, nhưng bản thân thẻ/đầu đọc vẫn có thể gặp sự cố; vì vậy cần bản sao lưu.
- **Sao lưu dữ liệu KiraPick hiện tại** (bản 2.2.1 bạn đang dùng): đóng KiraPick, chép thư mục
  `%LOCALAPPDATA%\KiraPick` (dán vào thanh địa chỉ File Explorer) sang chỗ khác. Bản thử nâng cấp dữ liệu phiên lên
  v7 (xem K1 trong `docs/beta-release-checklist.md`).
- Trên máy: chép **chỉ các file JPEG** của thẻ vào một thư mục, ví dụ `D:\Test\JPEG_buoi1`. Không chép RAW.
- Một thư mục trống để xuất, ví dụ `D:\Test\Xuat`.
- **Chụp "dấu vân tay" của thẻ và thư mục gốc trước khi thử** (để chứng minh không file gốc nào bị đổi). Mở PowerShell
  (bấm Start, gõ `PowerShell`), dán từng dòng, thay `E:` bằng ổ thẻ nhớ:

  ```powershell
  Get-ChildItem -Recurse -File "E:\DCIM" | Get-FileHash | Select-Object Path, Hash | Export-Csv D:\Test\the_truoc.csv
  Get-ChildItem -Recurse -File "D:\Test\JPEG_buoi1" | Get-FileHash | Select-Object Path, Hash | Export-Csv D:\Test\jpeg_truoc.csv
  ```

  Lệnh này chỉ **đọc** file, không ghi gì lên thẻ.

## 1. Nhập JPEG, chọn Giữ, lấy RAW từ thẻ gốc

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 1.1 | KiraPick → Nhập thư mục `D:\Test\JPEG_buoi1` | Mỗi ảnh một ô; không báo lỗi | |
| 1.2 | Chọn (P/K) khoảng 20 ảnh, trong đó có ảnh **chụp nhóm** (2–3 người) | Thanh dưới đếm đúng số ảnh Chọn | |
| 1.3 | ⤴ Xuất ảnh → ① **Nguồn khác** → Chọn… → thư mục `DCIM` trên thẻ; ② **Chỉ RAW**; ③ **Tất cả vào một thư mục**; đích `D:\Test\Xuat\RAW` | "Đang quét …" rồi "Đã quét N file"; bảng "Sẽ chép" ghi "khớp theo giờ chụp" cho từng RAW | |
| 1.4 | Bấm Sao chép → Có | Thư mục đích có đúng các file `.NEF` của các ảnh đã Chọn; mở 2–3 file trong phần mềm khác: đúng ảnh | |

## 2. Nguồn đã nhập / Nguồn khác độc lập

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 2.1 | Cùng các ảnh đã Chọn: ① **Thư mục đã nhập** · ② **RAW + JPEG** · đích `D:\Test\Xuat\Nhap` | Chỉ chép các `.JPG` (thư mục đã nhập chỉ có JPEG, nên "RAW + JPEG" ở đây là đúng "những file đã nhập"); **không** có cảnh báo thiếu RAW — điều đó là đúng, không phải lỗi | |
| 2.2 | ① **Nguồn khác** (thẻ) · ② **RAW + JPEG** · đích `D:\Test\Xuat\The` | Cả `.NEF` và `.JPG` đều lấy **từ thẻ**; JPEG ghi "giống hệt nội dung" | |
| 2.3 | (Thẻ thử đã sao lưu) Rút thẻ, mở lại hộp thoại Xuất với ① Nguồn khác | Báo "không tìm thấy thư mục nguồn …"; app không treo | |

## 3. Định dạng: Chỉ RAW / Chỉ JPEG / RAW + JPEG

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 3.1 | Cắm lại thẻ. ① Nguồn khác, đổi lần lượt ② Chỉ RAW → Chỉ JPEG → RAW + JPEG (chưa chép) | Mỗi lần đổi, bảng xem trước cập nhật đúng loại file; không có file nào bị đổi đuôi hay chuyển định dạng | |
| 3.2 | Chép với "Chỉ JPEG" vào `D:\Test\Xuat\JPEG` | Chỉ có `.JPG` | |

## 4. Một thư mục / Mỗi chủ thể một thư mục (cả ảnh nhóm)

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 4.1 | Chạy 📊 Phân tích AI cho buổi chụp, đặt tên 2 người | Danh sách chủ thể có tên | |
| 4.2 | ③ **Mỗi chủ thể một thư mục**, đích `D:\Test\Xuat\ChuThe` | Mỗi người một thư mục; **ảnh nhóm nằm trong thư mục của từng người có mặt**; ảnh chưa rõ người ở "Chưa xác định"; cặp RAW+JPEG cùng tên trong mỗi thư mục | |

## 5. Trường hợp khó: không chắc, thiếu EXIF, máy đếm số lại, trùng tên

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 5.1 | Nếu thẻ có hai thư mục (100NIKON, 101NIKON) cùng tên file `DSC_0001` (máy đếm lại): xuất ① Nguồn khác | Chỉ file chụp đúng giờ được chọn; file của buổi khác ghi "Không khớp", **không bao giờ** bị chép nhầm | |
| 5.2 | Tạo thư mục `D:\Test\Nguon2` có hai thư mục con `A` và `B`. Chép (không phải chuyển) từ thẻ vào `A` file RAW của một ảnh đã Chọn, ví dụ `DSC_0123.NEF`; chép vào `B` file RAW của ảnh chụp liền sau (cách ≤ 2 giây) rồi **đổi tên bản sao** thành `DSC_0123.NEF`. Xuất ① Nguồn khác = `D:\Test\Nguon2`, ② Chỉ RAW | Tab "Cần xem lại" ghi "Không chắc", có danh sách 2 file ứng viên và nút **Dùng file này**; bấm → chuyển sang "Sẽ chép" với dấu ✋ | |
| 5.3 | Nếu có > 50 mục "Không chắc": dùng nút **Sau ›** dưới bảng | Mọi mục đều xem được và chọn được | |
| 5.4 | File không có EXIF (ví dụ ảnh đã chỉnh, lưu lại không có giờ chụp) | Ghi "Không chắc — không đọc được giờ chụp", không tự chép | |

## 6. Sao chép tên ảnh

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 6.1 | Tab **📋 Tên ảnh đã Chọn** → Sao chép tên ảnh → dán vào Notepad/Zalo | Mỗi ảnh một dòng, không có đuôi; cặp RAW+JPEG chỉ một dòng | |
| 6.2 | Tick **Kèm đuôi file** → sao chép lại | Có đuôi (`.NEF` cho cặp) | |
| 6.3 | (Thẻ thử đã sao lưu) Rút thẻ rồi sao chép tên ảnh | Vẫn được, ngay lập tức | |
| 6.4 | Nếu có hai ảnh khác nhau trùng tên (hai buổi chụp) | Dòng cảnh báo "⚠ Có ảnh khác nhau trùng tên" | |

## 7. Dừng, rút thẻ, thử lại, danh sách xuất

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 7.1 | Xuất nhiều RAW (≥ 50) từ thẻ; trong lúc chép bấm **Dừng** | Dừng ngay; thư mục đích **không có file dở dang** (mọi file mở được); cặp RAW+JPEG không bị lẻ | |
| 7.2 | (Chỉ với thẻ thử đã sao lưu) Xuất lại; giữa chừng **rút thẻ** | Báo "Nguồn không còn truy cập được"; các file đã chép mở được; app không treo | |
| 7.3 | Cắm thẻ, bấm **Thử lại các file chưa chép** | Chỉ chép phần còn thiếu; không tạo file "(1)" | |
| 7.4 | Mở thư mục `_kirapick_danh_sach` trong thư mục đích → file `.csv` bằng Excel | Mỗi file có một dòng: copied / already_present / failed / not_started …, có cột sha256 | |
| 7.5 | Xuất lần nữa vào cùng thư mục | "có vẻ đã có sẵn"; chép xong: "đã có sẵn, giống hệt từng byte" | |

## 8. So sánh (Compare) với chuột thật

| # | Làm | Kết quả đúng | Đạt / Lỗi |
|---|---|---|---|
| 8.1 | Ctrl+click 2, 3 rồi 4 ảnh → **C** | Mở So sánh; ảnh đang chọn có khung xanh | |
| 8.2 | Rê chuột chậm và nhanh qua từng ảnh | Khung xanh và bảng chi tiết đi theo ảnh dưới chuột | |
| 8.3 | Mở So sánh khi chuột **đang đứng yên** trên chỗ một ảnh sẽ hiện ra | Ảnh đang chọn ban đầu giữ nguyên tới khi bạn **di chuột** | |
| 8.4 | P / X / 1–5 / ⟳ / Z | Chỉ đổi ảnh có khung xanh; Z 100 % không làm cửa sổ đứng | |
| 8.5 | Esc / G về lưới; bấm ✕ khi đang ở So sánh | Về lưới đúng vị trí; app đóng bình thường | |

## 9. File gốc không đổi (bắt buộc)

Sau khi làm xong mọi bước, chạy lại (cùng cửa sổ PowerShell):

```powershell
Get-ChildItem -Recurse -File "E:\DCIM" | Get-FileHash | Select-Object Path, Hash | Export-Csv D:\Test\the_sau.csv
Get-ChildItem -Recurse -File "D:\Test\JPEG_buoi1" | Get-FileHash | Select-Object Path, Hash | Export-Csv D:\Test\jpeg_sau.csv
Compare-Object (Import-Csv D:\Test\the_truoc.csv) (Import-Csv D:\Test\the_sau.csv) -Property Path, Hash
Compare-Object (Import-Csv D:\Test\jpeg_truoc.csv) (Import-Csv D:\Test\jpeg_sau.csv) -Property Path, Hash
```

| # | Kết quả đúng | Đạt / Lỗi |
|---|---|---|
| 9.1 | Hai lệnh `Compare-Object` **không in ra gì** (không file nào bị đổi, thêm hay xoá trên thẻ và thư mục gốc) | |
| 9.2 | Lần sau cắm thẻ, Windows **không** hỏi "quét và sửa lỗi thẻ" | |

## 10. Ghi thêm cho quyết định phát hành

| # | Ghi lại | Giá trị |
|---|---|---|
| 10.1 | Dòng `GUI-thread GC` cuối cùng trong `kirapick.log` sau bước 8 (cho K2) | |
| 10.2 | Ở bước 8, có lần nào bấm P/X trong So sánh thấy app khựng rõ (≈ ⅓ giây) không? Nếu có: ảnh nào, mấy lần | |
| 10.3 | Máy: Windows 10 hay 11, CPU, RAM, card đồ hoạ, tỉ lệ màn hình (100 % / 125 % / 150 %) | |
| 10.4 | Dòng tiêu đề cửa sổ KiraPick (tên + số phiên bản) và tên file bộ cài / zip bạn đã cài | |

## Gửi lại

Gửi bảng này (Đạt / Lỗi), ảnh chụp màn hình app ở các dòng Lỗi, file `kirapick.log` (trong
`%LOCALAPPDATA%\KiraPick\logs`), và mục 10. Không gửi ảnh chụp của bạn.

**Sau khi gửi:** mình viết báo cáo quyết định phát hành beta (rủi ro còn lại, K2, ngoại lệ 331 ms, B4–B6). Bạn đọc
rồi mới ra lệnh phát hành hoặc không. Hoàn thành bảng này **không** tự động là đồng ý phát hành.
