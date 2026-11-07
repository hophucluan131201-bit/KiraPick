# Media — đề xuất phân loại theo việc của người chụp (bản trình 2, 2026-11-07)

**Trạng thái:** trình chủ dự án. **Chưa sửa logic phân loại** cho tới khi chủ dự án duyệt.
Bản 1 (phương án A / B / C) được thay bằng bản này theo kết luận "BETA 3.0.1b1 / b1a CHƯA ĐẠT NGHIỆM THU", mục 3.

**Dữ liệu còn thiếu (nói thẳng):** máy phát triển **không có ảnh sự kiện thật** của chủ dự án. Album VNNIC chưa dùng
vì chưa kiểm xong quyền sử dụng; ảnh mẫu trong repo là ảnh cosplay chân dung. Vì vậy:
- mọi con số "Beta hiện tại" ở mục 6 là **chưa đo**;
- ví dụ ở mục 4 là tình huống mô tả, **không phải** kết quả trên ảnh thật;
- mục 7 là cách lấy số đo trên ảnh thật **tại máy chủ dự án**; ảnh không rời máy, không vào repo hay CI.

---

## 1. Việc người chụp cần làm sau một sự kiện

1. Từ vài trăm tới vài nghìn ảnh, **chọn ảnh giao khách** cho từng hoạt động (khai mạc, phát biểu, trao giải, booth…).
2. Mỗi hoạt động cần **đủ cỡ cảnh**: toàn sân khấu, trung cảnh, cận người phát biểu.
3. Không bỏ sót hoạt động nào, kể cả hoạt động chỉ có **một** ảnh (ảnh đó có cảnh báo nét thì vẫn phải được xem).
4. Không giao ảnh hỏng nét, trùng lặp gần giống nhau.

Beta hiện tại cho chia khoảnh khắc và gắn nhãn, nhưng người dùng vẫn phải **tự xem từng ảnh** trong mỗi khoảnh khắc để
chọn. Đề xuất dưới đây chuyển trọng tâm sang **giảm số ảnh phải xem**.

## 2. Luồng đề xuất

```
Nhập → (1) Gom ảnh giống nhau → (2) Gợi ý ảnh đáng xem trong mỗi nhóm → (3) Người chọn ảnh giao khách → Xuất
```

**(1) Gom ảnh giống nhau** (app tự làm, không cần mô hình mới)
- Trong mỗi khoảnh khắc, ảnh liên tiếp được gom thành **một nhóm** khi: cùng máy, cách nhau ≤ 10 giây, **cùng cỡ cảnh**
  và ảnh thu nhỏ giống nhau (so mã băm hình ảnh trên ảnh thu nhỏ, một quy tắc tính toán, không phải mô hình AI).
- Đổi cỡ cảnh là đổi nhóm: ảnh toàn sân khấu và ảnh cận người phát biểu **không bao giờ chung nhóm**.
- Nhóm chỉ là gợi ý xem cho nhanh: không xoá, không ẩn ảnh nào.

**(2) Gợi ý ảnh đáng xem** (app tự làm)
- Mỗi nhóm hiện **một ảnh đại diện** (nét nhất theo phép đo trên ảnh gốc, không có cảnh báo nét) và số ảnh còn lại
  ("+7"). Bấm vào nhóm để mở các ảnh còn lại cạnh nhau.
- Nhóm **chỉ có một ảnh** thì ảnh đó luôn được gợi ý, **kể cả khi có cảnh báo nét**; thẻ ảnh ghi "ảnh duy nhất của nhóm
  — có cảnh báo nét". Bộ lọc "ẩn ảnh có cảnh báo" không bao giờ ẩn loại ảnh này.
- Trong một khoảnh khắc, app gợi ý **ít nhất một ảnh cho mỗi cỡ cảnh có mặt** (Toàn / Trung / Cận), để không giao thiếu.

**(3) Người chọn ảnh giao khách** (người xác nhận)
- P / X như 3.0.0, trên ảnh đại diện hoặc trong nhóm. P một ảnh không tự loại các ảnh khác trong nhóm.
- Khoảnh khắc chưa có ảnh P nào được đánh dấu "⚠ chưa có ảnh giao" trong danh sách KHOẢNH KHẮC, để không sót hoạt động.

**Ranh giới hoạt động** (app gợi ý, người xác nhận)
- Giữ cách chia theo khoảng nghỉ ≥ 5 phút. Thêm **gợi ý ranh giới** (không tự tách) khi hai nhóm liền nhau khác hẳn
  nhau: đổi cỡ cảnh hàng loạt, ảnh thu nhỏ khác hẳn, hoặc đổi máy. Gợi ý hiện ở dải khoảnh khắc: "Có thể là hoạt động
  mới — ✂ Tách ở đây?". Người bấm ✂ hoặc bỏ qua.

## 3. Bốn nhóm nhãn

| Nhóm nhãn | Giá trị | Mốc 1: app tự gợi ý | Người xác nhận / sửa | Ngoài Mốc 1 |
|---|---|---|---|---|
| **Cỡ cảnh** | Toàn / Trung / Cận | Có (dò người + dò khuôn mặt + quy tắc tỉ lệ) | Alt+T / U / C, cho nhiều ảnh một lúc | Chỉnh ngưỡng trên ảnh thật |
| **Nội dung** | Sân khấu, Booth / Gian hàng, Decor, Sản phẩm, Merch | **Không** (chức năng gợi ý nội dung đang tắt: chờ quyền sử dụng mô hình) | Gán tay Alt+1–5; gán **một lần cho cả khoảnh khắc**, sửa ngoại lệ | Gợi ý nội dung bằng AI khi có mô hình được phép |
| **Người và vai trò** | Người phát biểu, khách mời, MC, khán giả | **Không** (chưa có mô hình được phép để nhận ra cùng một người) | Không có trong Mốc 1 | Gom người thủ công như Chụp cá nhân; vai trò là việc của Mốc sau |
| **Lỗi nét** | Out nét / Trật nét | Có (đo trên ảnh gốc) | Q bỏ cảnh báo, W / R đổi loại | Chỉnh ngưỡng trên ảnh thật |

- **Booth / Gian hàng là một nhãn**, không tách hai.
- Một ảnh có **nhiều nhãn** cùng lúc (ví dụ Sân khấu + Sản phẩm; Toàn + Out nét). Nhóm "Cỡ cảnh" chỉ có một giá trị.

## 4. Ba tình huống người duyệt nêu (cách luồng mới xử lý)

| Tình huống | Beta hiện tại | Đề xuất |
|---|---|---|
| Tìm riêng ảnh toàn sân khấu và ảnh cận người phát biểu | Có bộ lọc cỡ cảnh, nhưng ảnh vẫn trộn trong một lưới dài | Nhóm luôn tách theo cỡ cảnh; trong khoảnh khắc, lọc Toàn hoặc Cận chỉ hiện ảnh đại diện của các nhóm đó |
| Hai hoạt động liền nhau, không nghỉ 5 phút | Thành **một** khoảnh khắc; người phải tự thấy và tách | Gợi ý ranh giới ở chỗ đổi cảnh; người bấm ✂ một lần |
| Hoạt động chỉ có một ảnh, ảnh đó có cảnh báo nét | Nếu người lọc "không cảnh báo" thì ảnh bị ẩn, dễ sót | Ảnh duy nhất của nhóm luôn hiện và luôn được gợi ý, ghi rõ có cảnh báo nét |

## 5. POSE-DB-01: chỉ tham khảo cách bày

Chỉ lấy **cách bày các góc chụp cạnh nhau** (một hàng ảnh cùng nhóm, so được ngay) cho màn hình mở nhóm ở bước (2).
**Không** dùng ảnh trong thư viện đó làm dữ liệu, không huấn luyện, không so mẫu. Thử nghiệm gom theo dáng người ở Chụp
cá nhân là việc **sau**, không thuộc đề xuất này.

## 6. So sánh Beta hiện tại với đề xuất

| Số đo | Beta hiện tại | Đề xuất | Trạng thái |
|---|---|---|---|
| Thời gian từ nhập tới thư mục giao khách | chưa đo | chưa đo | **Cần ảnh thật** (mục 7) |
| Số ảnh phải mở để chọn | = tổng số ảnh | ≈ số nhóm + số nhóm phải mở ra | Chưa đo |
| Số thao tác (P/X, nhãn, ✂ ⊕ ✎, Ctrl+Z) | chưa đo | chưa đo | Cần đếm thao tác (mục 8) |
| Gộp sai (hai hoạt động thành một khoảnh khắc) | chưa đo | chưa đo | Từ nhãn mẫu B (ranh giới) |
| Tách sai (một hoạt động thành hai) | chưa đo | chưa đo | Từ nhãn mẫu B |
| Hoạt động bị sót (không có ảnh giao) | chưa đo | chưa đo | Người ghi tay sau khi giao |

Chỉ tiêu đề xuất để chủ dự án chốt: thời gian từ nhập tới thư mục giao khách **ngắn hơn ít nhất 30 %** so với cách làm
3.0.0 trên cùng sự kiện; **không sót** hoạt động nào; số lần sửa nhãn AI ít hơn số thao tác AI tiết kiệm được.

## 7. Lấy số đo trên ảnh sự kiện thật (tại máy chủ dự án)

1. Chọn **một** sự kiện 300–500 ảnh, tốt nhất 2 máy, có sân khấu + booth + khán phòng + một đoạn hai hoạt động liền nhau.
2. Làm hai lần trên cùng sự kiện: (a) cách 3.0.0: P / X rồi tự chép ảnh theo hoạt động; (b) Beta Media hiện tại. Bấm
   giờ từ lúc nhập tới lúc có thư mục giao khách.
3. 🏷 Dán nhãn mẫu 100–150 ảnh (cỡ cảnh, nét, B ranh giới) → `KiraPick.exe --media-score` → gửi `cham.json` (chỉ số, không
   có ảnh hay tên file).
4. Ghi tay: hoạt động nào app gộp sai / tách sai; hoạt động nào suýt sót; bước nào mất thời gian nhất.
5. Sau khi chủ dự án duyệt đề xuất và có bản làm thử, lặp lại bước 2 với luồng mới để so.

## 8. Việc kỹ thuật nếu đề xuất được duyệt (chưa làm)

1. Mã băm hình ảnh trên ảnh thu nhỏ + gom nhóm trong khoảnh khắc (quy tắc, có test trên ảnh tổng hợp).
2. Ảnh đại diện + "+N", mở nhóm thành hàng ảnh cạnh nhau (dùng lại lưới và so sánh của 3.0.0).
3. Gợi ý ranh giới (không tự tách) + "⚠ chưa có ảnh giao" trong danh sách khoảnh khắc.
4. Nội dung theo khoảnh khắc (gán một lần, sửa ngoại lệ).
5. Một dòng nhật ký cho mỗi thao tác (`kind` + thời điểm, không tên ảnh) và `--media-counts` để in bảng số mục 6.

## 9. Cần chủ dự án quyết định

1. Duyệt luồng mục 2 (hoặc sửa), trước khi đổi logic phân loại.
2. Duyệt bảng bốn nhóm nhãn mục 3 (nhất là: "Người và vai trò" ngoài Mốc 1).
3. Chỉ tiêu mục 6 (≥ 30 % thời gian, không sót hoạt động).
4. Có thể làm mục 7 trên một sự kiện thật không, và khi nào.
