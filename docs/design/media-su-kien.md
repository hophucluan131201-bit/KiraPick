# Media sự kiện — Đặc tả bản 6 (2026-11-07)

- **Phạm vi:** nhánh `beta`. Mốc 1 đang được viết mã (đợt 1: M1–M5 đã có; kế hoạch ở `docs/design/media-moc1-ke-hoach.md`).
- **Bản 5** đã được chủ dự án duyệt ngày 2026-11-06. **Bản 6** chỉ sửa phần kỹ thuật theo LIC-1 và các quyết định
  ngày 2026-11-07 (mục 0). Không đổi quyết định nào của chủ dự án ngoài những quyết định ghi ở mục 0.
- **Phát hành:** merge vào `main`, gắn tag và phát hành đều cần duyệt riêng.
- **Màn hình chọn chế độ:** giữ nguyên, đã có trên `beta`.

## 0. Thay đổi của bản 6

| # | Thay đổi | Lý do / quyết định |
|---|---|---|
| 0.1 | **Mốc 1 có ba nhóm lọc:** cỡ cảnh, nội dung ảnh, lỗi nét. **Người & vai trò thuộc Mốc 2** | Review 2026-11-07 |
| 0.2 | **CLIP `pending`** ở Media (MED-CLIP): MOD-1 là hồ sơ chấp nhận rủi ro, **không phải căn cứ quyền**. Mốc 1 chạy **phương án dự phòng §12a**: nội dung ảnh chỉ gán tay (CT-F1, CT-F2), "Gợi ý lại" nội dung tắt (CT-F3), khoảnh khắc chỉ chia theo khoảng nghỉ (MT-F1), tên booth gợi ý trong cùng khoảnh khắc (BT-F1) | LIC-1, MED-CLIP |
| 0.2a | **Mục 12, 12a, 13, 14 viết lại theo LIC-1:** Media chỉ nạp trọng số `verified` cho chế độ `media` trong `configs/model-policy.json`; CLIP và SFace `pending`; phương án dự phòng §12a là cách chạy hiện hành | Review 2026-11-07 (sau đợt 2) |
| 0.3 | **SFace `pending`**: Mốc 2 gom người **chỉ gán tay**, trừ khi có căn cứ (R1). Danh sách cho phép là `configs/model-policy.json` dùng chung (thay `configs/media-models.json`); trạng thái chỉ còn verified / pending / never | LIC-1 |
| 0.4 | **Mọi nhãn AI** (cỡ cảnh, lỗi nét) hiện kèm **"(thử nghiệm)"** cho tới khi có kết quả chấm trên ảnh thật đạt ngưỡng §11 | Review 2026-11-07 |
| 0.5 | **Dữ liệu:** mỗi sự kiện một thư mục và một cơ sở dữ liệu ở `%LOCALAPPDATA%\KiraPick\media\<mã>\`. CSDL sự kiện dùng chung cấu trúc bảng ảnh với phiên Chụp cá nhân (nay là v8, có ghi nguồn kết quả), cộng các bảng Media riêng (`app/media/schema.py`) chỉ áp cho sự kiện. Cùng một thư mục ảnh mở ở hai chế độ là hai CSDL: P/X, sao, nhãn tách riêng | Kế hoạch M1 |
| 0.6 | **Xuất ảnh cơ bản** chuyển từ Mốc 3 vào **Mốc 1** (commit M11) | Chủ dự án duyệt MED-EXP 2026-11-07 |
| 0.7 | **Hai ca lỗi nét mới:** FC-06 (màn LED sắc nét nhưng chưa bão hoà) và FC-07 (trang phục trắng sáng còn chi tiết), mục 6 | Review 2026-11-07 |
| 0.8 | **Ảnh mẫu (MED-SAMPLE):** album VNNIC Internet Conference 2026 (19/6) là nguồn hội nghị chính; album tổng kết IPv6, trao bằng khen (18/6) là nguồn bổ sung. Quy tắc dùng: kế hoạch Mốc 1 §4a | Review 2026-11-07, chủ dự án |
| 0.9 | Hồi quy Chụp cá nhân: bộ test Linux nay là **1307** (gồm test Media), không phải 1209 | Thực tế repo |
| 0.10 | **Phím ở cửa sổ Media:** P / K chọn, X loại, **Backspace** bỏ P/X, F ❤, **Alt+0…5** sao (vì 1–5 là nội dung), **T / U / C** cỡ cảnh, 1–5 nội dung, Space ảnh lớn, Ctrl+Z. Chế độ 🏷 Dán nhãn mẫu: thêm N nét, O out nét, R trật nét, B bắt đầu khoảnh khắc, 0 chưa đánh giá | Đợt 2 (M8, M9) |
| 0.11 | **Cảnh báo nét có thêm "Không đo được"** (ảnh phẳng, quá tối): khác với "Không cảnh báo"; không bao giờ đoán thành Out nét | Đợt 2 (M7) |
| 0.12 | **R1-UNDO-AI giữ cho Mốc 1:** hoàn tác một thao tác khoảnh khắc làm trước "Phân tích lại" trả cả cách chia trước đó; cửa sổ báo rõ điều này | Review 2026-11-07 |
| 0.13 | **Xuất ảnh cơ bản:** ảnh P sao chép vào thư mục theo khoảnh khắc ("01 …", ảnh chưa có khoảnh khắc vào "Chưa chia khoảnh khắc") hoặc theo cỡ cảnh; dùng bộ xuất của Chụp cá nhân (không đè, kiểm SHA-256, tên trùng được đặt khác) | MED-EXP, M11 |

**Quy ước trong tài liệu:**
- **[Repo]**: đã xác minh trong mã nguồn hiện tại.
- **[Ảnh mẫu]**: phải kiểm chứng trên bộ ảnh mẫu.
- **[Windows/CUDA]**: phải kiểm chứng trên máy Windows/CUDA.
- **[Chờ duyệt]**: chờ chủ dự án quyết định. Tất cả các mục này được gom lại ở **mục 13**.

---

## 1. Nguyên tắc không đổi

- **Offline:** chạy hoàn toàn trên máy. Chế độ Media không có mã nào gọi mạng. [Repo: một test đã kiểm tra rằng chỉ
  `app/updates/` được dùng mạng; sẽ mở rộng test này cho mã Media.]
- **Ảnh gốc:** không sửa, xoá, đổi tên hay di chuyển ảnh gốc, và không sửa EXIF. Xuất ảnh chỉ là sao chép. [Repo: phần
  xuất ảnh hiện có đã đáp ứng.]
- **Dữ liệu tách riêng:** Media có thư mục dữ liệu riêng `%LOCALAPPDATA%\KiraPick\media\` và cơ sở dữ liệu riêng. Cấu
  trúc bảng ảnh dùng chung với Chụp cá nhân (v8, ghi nguồn kết quả, LIC-1); các bảng Media chỉ áp cho CSDL sự kiện
  (`app/media/schema.py`), phiên Chụp cá nhân không bao giờ có chúng.
- **Hồi quy Chụp cá nhân:**
  - bộ test hiện có (1307 test Linux gồm test Media, bộ Windows đầy đủ, hiệu năng, sức chịu) phải đạt nguyên vẹn;
  - bảng 11 bước của bản RC chạy lại trên Windows/CUDA trước bản thử cuối.
- **Thẻ AI là gợi ý:** quyết định cuối cùng thuộc về người dùng (mục 3).

## 2. Nhóm lọc: ba nhóm ở Mốc 1, nhóm Người ở Mốc 2

| Nhóm | Giá trị | Số nhãn mỗi ảnh |
|---|---|---|
| **Cỡ cảnh** (Mốc 1) | Toàn / Trung / Cận (thêm trạng thái Chưa xác định) | một |
| **Nội dung ảnh** (Mốc 1) | Sân khấu / Booth / Gian hàng / Decor / Sản phẩm / Merch | nhiều |
| **Người và vai trò** (Mốc 2) | Diễn giả / Celeb / Talent / Đại biểu; gom và đặt tên từng người **nếu khả thi** (mục 7) | nhiều người mỗi ảnh |
| **Độ nét** (Mốc 1) | Out nét / Trật nét (cảnh báo) | không, một hoặc cả hai |

- Tên hiển thị là **tên làm việc**; đổi tên không ảnh hưởng dữ liệu.
- **Booth / Gian hàng** là **một** nhãn.
- Có thêm **tên booth / nhà tài trợ** do người dùng đặt (mục 4). Đây không phải một nhóm lọc thứ năm, mà là nhãn tự đặt
  gắn kèm nội dung ảnh.

## 3. Trạng thái của nhãn

Mọi nhãn (cỡ cảnh, nội dung, cảnh báo nét, người, vai trò, khoảnh khắc) đều ở **một** trong các trạng thái sau:

| Trạng thái | Nghĩa | Hiển thị |
|---|---|---|
| **Đang phân tích** | Ảnh chưa được phân tích xong cho nhóm nhãn này | ⏳; không lọc theo nhãn đó |
| **Chưa xác định** | Đã phân tích, nhưng AI không đủ tự tin hoặc không áp dụng được | "?"; lọc riêng được |
| **AI gợi ý** | AI gắn, người dùng chưa xác nhận | chữ thường + mức tự tin |
| **Đã xác nhận** | Người dùng gán, hoặc bấm xác nhận gợi ý | chữ đậm ✓ |
| **Đã bỏ** | Người dùng gỡ một nhãn AI đã gợi ý | không hiện; AI không gợi ý lại nhãn đó cho ảnh này |

**Quy tắc giữ dữ liệu:**
- Không thao tác tự động nào ghi đè nhãn "Đã xác nhận" hoặc "Đã bỏ". Các thao tác tự động gồm: chạy tiếp, phân tích
  lại, chỉnh giờ, gợi ý lại.
- **P / X / sao / ❤** chỉ đổi khi người dùng bấm.
- Khoảnh khắc đã sửa tay giữ nguyên danh sách ảnh (mục 8).

**Hai việc khác nhau, cần tách riêng:**
1. **Lưu chỉnh sửa** của người dùng: luôn bật.
2. **Dùng ảnh đã sửa để gợi ý lại** cho các ảnh khác:
   - là nút riêng **"Gợi ý lại từ các ảnh đã xác nhận"**;
   - hoàn tác được;
   - chỉ đổi nhãn đang ở trạng thái "AI gợi ý" hoặc "Chưa xác định".

## 4. Nội dung ảnh

- **Nhãn:** Sân khấu, Booth / Gian hàng, Decor, Sản phẩm, Merch. **Một ảnh mang được nhiều nhãn**, mỗi nhãn có trạng
  thái riêng.
- **Cách gợi ý** (chỉ khi CLIP `verified`; **hiện CLIP `pending`**: nội dung chỉ gán tay, §12a CT-F1/F2/F3):
  - Dùng **CLIP ViT-L/14**: so phần nhúng ảnh với mô tả bằng chữ của từng nhãn. Mô tả được tính sẵn lúc build, như
    `clip_prompts_v1.npz` [Repo].
  - Gắn mọi nhãn vượt ngưỡng; ngưỡng của từng nhãn chỉnh trên tập chỉnh ngưỡng (mục 11).
  - Không nhãn nào vượt ngưỡng thì ảnh ở trạng thái **Chưa xác định**.
- **Tên booth / nhà tài trợ:**
  - Người dùng tự đặt, nên luôn ở trạng thái Đã xác nhận.
  - App gợi ý cùng tên cho ảnh trông giống và chụp gần giờ.
  - Không đọc chữ hay logo.
- **Chi phí:** phần nhúng CLIP tính **một lần** cho mỗi ảnh và lưu lại. App đã có bảng `asset_vectors` loại `clip`
  [Repo]; Media dùng cách tương tự trong cơ sở dữ liệu riêng.

## 5. Cỡ cảnh: Toàn / Trung / Cận

**Tách khỏi độ nét.** Cỡ cảnh chỉ dựa vào **vị trí và kích thước** người trong khung. Ảnh cận bị mờ vẫn là Cận, kèm
cảnh báo nét (mục 6).

**Chủ thể chính:**
- Là người có khung lớn nhất sau khi loại:
  - người bị mép khung cắt mất quá nửa;
  - người quay lưng;
  - đầu khán giả ở tiền cảnh (khung chạm mép dưới, không thấy mặt).
- **Không** dùng độ nét để chọn chủ thể. Chủ thể lệch khung vẫn được chọn.

**Hai đường xếp cỡ cảnh:**
1. **Có mặt dò được:** xếp theo tỉ lệ **chiều cao mặt / chiều cao ảnh**. Ngưỡng ban đầu: Cận > 12 %, Trung 4–12 %,
   Toàn < 4 % [Ảnh mẫu].
2. **Chỉ dò được người, không dò được mặt** (mặt quá mờ, quay nghiêng, quá nhỏ): dùng **khung người dự phòng**, theo
   quy tắc thận trọng:
   - khung người cao **dưới khoảng 25 %** ảnh → **Toàn**;
   - các trường hợp còn lại → **Chưa xác định**. Không đoán Trung hay Cận khi không có mặt, vì khung người không cho
     biết chụp từ hông hay từ gối.
   - Ngưỡng 25 % chỉnh trên ảnh mẫu [Ảnh mẫu].

**Toàn khác Chưa xác định:**
- **Toàn:** có người, và người nhỏ trong khung (theo đường 1 hoặc 2).
- **Chưa xác định:** không dò được người (ảnh vật thể, decor, sản phẩm), hoặc thuộc nhánh "còn lại" của đường 2.

**Giới hạn của bản Beta:**
- App chỉ tự xếp cỡ cảnh cho **ảnh có người**.
- Ảnh vật thể để Chưa xác định; người dùng gán tay bằng phím **T / U / C** (một hoặc nhiều ảnh).
- Ghi rõ giới hạn này trong ghi chú phát hành.

**Ca kiểm thử** [Ảnh mẫu]:

| Mã | Ảnh | Kết quả mong đợi |
|---|---|---|
| SZ-01a | Cận diễn giả bị mờ, **vẫn dò được mặt** | Cận (theo tỉ lệ mặt) + cảnh báo Out nét |
| SZ-01b | Cận diễn giả bị mờ, **chỉ dò được người**, không dò được mặt | **Chưa xác định** (khung người lớn) + cảnh báo Out nét; gán tay được |
| SZ-02 | Chủ thể lệch sát mép trái/phải | Cùng cỡ cảnh như khi chủ thể ở giữa |
| SZ-03 | Cận vật thể (sản phẩm, merch), không người | Chưa xác định; gán tay được |
| SZ-04 | Toàn cảnh hội trường, mặt quá nhỏ để dò | Toàn (khung người nhỏ) hoặc Chưa xác định; **không** Cận/Trung |
| SZ-05 | Toàn cảnh, đầu khán giả to, mờ ở tiền cảnh | Toàn; đầu khán giả không bị chọn làm chủ thể |

## 6. Cảnh báo nét: Out nét / Trật nét

- **Là cảnh báo, không phải nhãn loại bỏ.** App không tự đánh dấu X và không tự loại ảnh.
- **Out nét:** vùng chủ thể bị mờ. Nếu không có chủ thể thì xét cả ảnh.
- **Trật nét** cần đủ cả ba điều kiện:
  1. có chủ thể và chủ thể bị mờ;
  2. có một vùng **gần chủ thể** nét rõ, ví dụ phông vải, bục phát biểu, người đứng cạnh;
  3. vùng nét đó **không phải** màn LED hay đèn: hai loại vùng này bị loại khỏi phép so.
  - Nếu chỉ có màn LED nét, ca đó **không đủ căn cứ** để báo Trật nét; ảnh chỉ nhận cảnh báo **Out nét**.
- **Đo trên ảnh độ phân giải gốc**, có tính tới ISO. [Repo: phép đo nét theo vùng trên ảnh gốc đã có ở
  `app/quality/measure.py`; phần riêng cho Media cần viết thêm.]
- **Rung máy và nhòe chuyển động** xếp vào đâu: **[Chờ duyệt]**, xem UX-4 ở mục 13.

**Ca kiểm thử** [Ảnh mẫu]:

| Mã | Ảnh | Kết quả mong đợi |
|---|---|---|
| FC-06 (v6) | Mặt diễn giả mờ, phía sau là **màn LED sắc nét nhưng chưa bão hoà** (nội dung trình chiếu có chi tiết) | **Out nét**, không Trật nét: màn LED phải bị nhận ra theo vùng phát sáng phẳng, viền thẳng, độ tương phản cao, không chỉ theo độ bão hoà |
| FC-07 (v6) | Diễn giả nét, mặc **trang phục trắng sáng còn chi tiết** (vải, nếp gấp) | Không cảnh báo; vùng trắng sáng của chủ thể **không** bị coi là đèn / LED và không bị loại khỏi phép đo nét |
| FC-01 | Lia máy: chủ thể nét, nền nhòe ngang | Không cảnh báo |
| FC-02a | Mặt diễn giả mờ, **phông vải / bục** ngay sau nét rõ | **Trật nét** |
| FC-02b | Mặt diễn giả mờ, **chỉ màn LED** phía sau nét | **Out nét**, không Trật nét |
| FC-03 | Toàn cảnh, mặt quá nhỏ | Không Trật nét; Out nét chỉ khi cả ảnh mờ |
| FC-04 | Rung tay toàn ảnh | Theo quyết định UX-4 |
| FC-05 | ISO cao nhưng nét | Không cảnh báo |

## 7. Người: gom, tên và vai trò là ba việc riêng

1. **Gom cùng người (AI):** bằng khuôn mặt, mô hình **SFace** (Apache-2.0) [Repo: `app/ai/detect.py`]. Kết quả là các
   nhóm người chưa có tên. **Hiện SFace `pending`** (mục 12): Mốc 2 gom người chỉ gán tay cho tới khi có căn cứ quyền.
2. **Gán tên (người dùng):** tuỳ chọn.
3. **Gán vai trò (người dùng):** Diễn giả / Celeb / Talent / Đại biểu.
   - Gán được khi chưa có tên.
   - Gán được **cho từng ảnh** khi không có nhóm người.

**"Nếu khả thi":**
- Gom từng người chỉ đáng tin khi mặt đủ lớn và đủ rõ.
- App báo **tỉ lệ ảnh nhận được mặt**. Ảnh không nhận được mặt vẫn gán vai trò tay được.
- Nếu gom bằng SFace không đạt ngưỡng ở mục 11, nhóm "Người" vẫn có trong Beta, nhưng chỉ ở dạng **gán tay**, kèm ghi
  chú "(thử nghiệm)" cho phần gom tự động.

**Sửa lỗi gom:**
- **Gộp nhầm:**
  - mở nhóm, chọn các mặt sai, bấm **"Tách thành người mới"** hoặc kéo sang nhóm khác;
  - app ghi lại cặp này là "khác nhau", lần sau không gộp lại.
- **Tách nhầm:** tick hai nhóm, bấm **🔗 Gộp**.
- Cả hai đều hoàn tác được và được giữ qua các lần chạy lại.
- [Repo: cơ chế gộp, tách, "khác nhau" và hoàn tác đã có ở `app/identity/actions.py`, `app/undo/`; Media dùng lại
  cách làm, trên dữ liệu riêng.]

**Danh sách NGƯỜI:**
- Mặc định hiện người xuất hiện **từ 5 ảnh trở lên**, hoặc đã có tên / vai trò.
- Những người khác nằm ở **"Khách khác"**.
- Người chỉ xuất hiện vài ảnh ngoài sân khấu: mở "Khách khác", hoặc bấm vào khuôn mặt trên ảnh, rồi chọn **"Đặt
  tên…"**. Người đó lên danh sách chính ngay.

**Gợi ý vai trò:**
- Gợi ý "có thể là Diễn giả / Talent" khi người đó xuất hiện nhiều ở ảnh có nhãn Sân khấu đã xác nhận, hoặc được AI gợi
  ý với độ tự tin cao.
- Luôn ở trạng thái AI gợi ý.

**Không nhớ người qua các sự kiện.** Xoá sự kiện thì xoá luôn dữ liệu khuôn mặt của sự kiện đó.

## 8. Khoảnh khắc

**AI tự chia** theo giờ chụp đã chỉnh lệch (mục 9), dựa trên hai tiêu chí: khoảng nghỉ dài, và đổi cảnh về hình ảnh
(độ giống CLIP giữa các nhóm ảnh liên tiếp). **Hiện CLIP `pending`**: chỉ chia theo khoảng nghỉ (MT-F1, §12a).

**Khoảnh khắc đã sửa tay giữ nguyên danh sách ảnh** (thay cho cách "ranh giới gắn với ảnh" của bản 3):
- Khi người dùng **tách, gộp, "Tách tại đây", chuyển ảnh** hoặc **đổi tên**, khoảnh khắc đó trở thành **"đã sửa tay"**
  (biểu tượng 📌).
- App lưu **danh sách mã ảnh** của nó.
- **Phân tích lại / chạy tiếp:**
  - Khoảnh khắc 📌 **giữ nguyên** danh sách ảnh và tên.
  - AI chỉ chia lại các ảnh **không** thuộc khoảnh khắc 📌 nào.
- **Chỉnh giờ:**
  - Khoảnh khắc 📌 **giữ nguyên** danh sách ảnh; không ảnh nào tự chuyển đi.
  - Thứ tự ảnh **bên trong** khoảnh khắc sắp lại theo giờ đã chỉnh.
  - Khoảnh khắc 📌 được đặt trên dòng thời gian theo giờ của ảnh **sớm nhất** trong nó.
  - Ảnh có thể bị đánh dấu **⚠ "lệch giờ"** theo **quy tắc lệch giờ** dưới đây. Người dùng chọn **Chuyển** sang
    khoảnh khắc được gợi ý, hoặc **Giữ**.
  - Phần ảnh AI chia (không 📌) được chia lại.
- **Hoàn tác (Ctrl+Z):**
  - Hoàn tác **chỉnh giờ** trả lại độ lệch cũ, thứ tự cũ và phần AI chia cũ. Danh sách ảnh của khoảnh khắc 📌 vốn
    không đổi.
  - Hoàn tác **thao tác sửa tay** trả khoảnh khắc về trạng thái trước. Nếu đó là thao tác đầu tiên, khoảnh khắc trở lại
    là "do AI chia".
- **Ảnh không có giờ chụp** nằm ở khoảnh khắc "Không rõ giờ".
- **Báo đủ cỡ cảnh** trong mỗi khoảnh khắc, dựa trên ảnh đã P. Ví dụ "Toàn ✓ Trung ✓ Cận ✗".

**Ca MED-02** [Ảnh mẫu]:
- **Bộ ảnh:** phần phát biểu chuyển **ngay** sang trao giải, **trên cùng sân khấu**, không có khoảng nghỉ. Cùng một
  người có mặt ở cả hai phần.
- **Mong đợi:**
  - Hai khoảnh khắc. AI có thể chia sai; người dùng sửa được bằng "Tách tại đây".
  - Người đó nằm trong một nhóm, có mặt ở cả hai khoảnh khắc.
  - Chọn ảnh riêng cho từng phần được.
- **Báo riêng:**
  1. **AI tự chia:** ranh giới đúng / thừa / thiếu.
  2. **Sửa tay:** số thao tác cần để đạt đúng.

**Quy tắc lệch giờ (áp dụng cho khoảnh khắc 📌):**
- **Khi nào kiểm tra:** chỉ khi người dùng **chỉnh giờ một nguồn máy S** (độ lệch của S thay đổi).
  - **Ảnh được kiểm tra:** các ảnh **của S** nằm trong khoảnh khắc 📌.
  - Giờ dùng để so là **giờ đã chỉnh** (giờ gốc + độ lệch).
- **Khoảng đối chiếu, độc lập với ảnh được kiểm tra:** với mỗi khoảnh khắc K (📌 hoặc do AI chia), tính
  R(K) = [giờ sớm nhất, giờ muộn nhất] của **các ảnh trong K không thuộc nguồn S**, tức là các ảnh mà lần chỉnh giờ
  này không làm đổi giờ.
  - Mở rộng mỗi đầu một **dung sai τ = 30 giây**, chỉnh trên ảnh mẫu.
  - Ảnh của S không bao giờ góp vào R(K). Vì vậy một ảnh như B-7 **không thể kéo dài khoảng** của khoảnh khắc chứa nó,
    và một ảnh đang nằm sai chỗ cũng không làm lệch khoảng dùng để kiểm tra ảnh khác.
  - K có **dưới 2 ảnh** không thuộc S thì **không có khoảng đối chiếu**.
- **Ảnh p (của S) trong khoảnh khắc 📌 M bị ⚠ khi và chỉ khi:**
  1. M có khoảng đối chiếu, **và** giờ của p nằm **ngoài** R(M) ± τ;
  2. giờ của p nằm **trong** R(N) ± τ của ít nhất một khoảnh khắc khác N.
- **Khoảng chồng nhau:**
  - p nằm trong **cả** R(M) ± τ và R(N) ± τ: **không cảnh báo** (điều 1 không thoả).
  - p nằm ngoài M nhưng trong khoảng của **nhiều** khoảnh khắc khác: gợi ý khoảnh khắc có **tâm khoảng gần p nhất**.
  - p nằm ngoài M và **không** thuộc khoảng nào khác (rơi vào khoảng trống): **không cảnh báo**.
- **Ảnh không có giờ:** không bao giờ bị cảnh báo.
- **Cảnh báo là kết quả của lần chỉnh giờ và được lưu cùng bước đó:**
  - **Chuyển:** đưa p sang khoảnh khắc được gợi ý và **xoá cảnh báo của p**. Hoàn tác Chuyển thì p về chỗ cũ và cảnh
    báo hiện lại.
  - **Giữ:** xoá cảnh báo của p. Hoàn tác thì cảnh báo hiện lại.
  - **Hoàn tác lần chỉnh giờ:** trả độ lệch cũ và xoá mọi cảnh báo do lần đó tạo ra.
  - **Phân tích lại hoặc chạy tiếp:** không tạo, không xoá cảnh báo.
  - **Chỉnh giờ S lần nữa:** thay toàn bộ cảnh báo của ảnh thuộc S bằng kết quả kiểm tra mới.

**Ca MED-03: hai máy lệch giờ và ranh giới đã tách** [Repo bằng ảnh tổng hợp; Ảnh mẫu nếu có]:
**Dữ liệu** (ảnh tổng hợp; máy A đúng giờ, máy B chậm 180 giây):

| Ảnh | Giờ thật | Giờ gốc trong EXIF | Phần |
|---|---|---|---|
| A-1 … A-5 | 10:00:00 → 10:04:00 (mỗi phút một ảnh) | như giờ thật | Phát biểu |
| B-1 … B-6 | 10:00:30, 10:01:30, 10:02:30, 10:03:30, 10:04:00, 10:04:30 | giờ thật − 3 phút (09:57:30 … 10:01:30) | Phát biểu |
| A-6 … A-10 | 10:05:00 → 10:09:00 | như giờ thật | Trao giải |
| **B-7** | **10:05:20** | **10:02:20** | Trao giải |
| B-8 … B-10 | 10:08:30, 10:09:00, 10:09:30 | 10:05:30, 10:06:00, 10:06:30 | Trao giải |

**Diễn biến và trạng thái mong đợi:**

| Bước | Thao tác | "Phát biểu" (📌) | "Trao giải" (📌) | Cảnh báo | Giải thích |
|---|---|---|---|---|---|
| S0 | Trước khi chỉnh giờ: "Tách tại đây" ngay trước A-6 | A-1…A-5, B-1…B-7 | A-6…A-10, B-8…B-10 | không | Theo giờ gốc, B-7 (10:02:20) nằm trong khoảng của "Phát biểu" |
| S1 | Chỉnh giờ máy B **+180 s** | không đổi | không đổi | **chỉ ⚠ B-7**, gợi ý "Trao giải" | Kiểm tra các ảnh B. R(Phát biểu) = A-1…A-5 = [10:00:00, 10:04:00] ± 30 s = [09:59:30, 10:04:30]. R(Trao giải) = A-6…A-10 = [10:05:00, 10:09:00] ± 30 s = [10:04:30, 10:09:30]. **B-7** = 10:05:20: ngoài Phát biểu, trong Trao giải → ⚠. B-1…B-5 (10:00:30–10:04:00) nằm trong Phát biểu → không ⚠. **B-6** = 10:04:30 nằm ở điểm chồng của hai khoảng → không ⚠. B-8…B-10 (10:08:30–10:09:30) nằm trong Trao giải → không ⚠. Ảnh của máy A không được kiểm tra |
| S2 | Bấm **Chuyển** | A-1…A-5, B-1…B-6 | A-6…A-10, **B-7**, B-8…B-10 | không | Chuyển xoá cảnh báo của B-7 |
| S3 | **Ctrl+Z** | A-1…A-5, B-1…B-7 | A-6…A-10, B-8…B-10 | **⚠ B-7** | Hoàn tác Chuyển: trở về đúng S1 |
| S4 | **Ctrl+Z** lần 2 | A-1…A-5, B-1…B-7 | A-6…A-10, B-8…B-10 | không | Hoàn tác chỉnh giờ: độ lệch của máy B về 0, cảnh báo của lần đó bị xoá; trở về đúng S0 |

- **Ở mọi bước:** P/X, sao, ❤, nhãn và người của B-7 không đổi.
- **Phân tích lại** ở S2: hai khoảnh khắc 📌 không đổi; không có ⚠.
- **Ca phụ MED-03b (vùng chồng):** B-6 = 10:04:30 nằm trong cả R(Phát biểu) ± τ và R(Trao giải) ± τ. Mong đợi:
  **không** ⚠ (đã có trong S1).
- **Ca phụ MED-03c (không có khoảng đối chiếu):** một khoảnh khắc 📌 chỉ gồm ảnh máy B, cộng một ảnh máy A. Sau khi
  chỉnh giờ máy B, khoảnh khắc này có dưới 2 ảnh không thuộc B. Mong đợi: **không** ⚠ cho ảnh nào trong nó.
- **Ca phụ MED-03d (A-6 không bị kéo theo):** ở S1, A-6 (10:05:00) nằm sát B-7, nhưng **không** bị kiểm tra, vì A không
  phải nguồn vừa chỉnh. Mong đợi: **không** ⚠ cho A-6.

## 9. Nhập nhiều máy và chỉnh giờ

**Hiện trạng repo** [Repo]:
- **Máy ảnh:** app đọc **hãng / dòng máy** (`make`, `model`), **không đọc số serial**. Đây là chủ ý, để bảo vệ quyền
  riêng tư (`app/ingest/metadata.py`).
- **Ghép RAW+JPEG:** theo **cùng thư mục + cùng tên** (`app/ingest/scanner.py`). Cặp trùng tên ở hai thư mục là hai ảnh
  riêng.
- **Giờ chụp:** lưu ở `assets.capture_time`.
- **Lựa chọn của người dùng:** lưu theo **mã ảnh cố định** (`decisions.asset_id`).

**Nguồn máy:**
- Mặc định: **thư mục con + hãng / dòng máy**.
- Hai máy cùng dòng ở hai thư mục → tách được.
- Hai máy cùng dòng **chung một thư mục** → không tách được tự động.
- **Chỉ định nguồn thủ công** trong màn "🕒 Máy ảnh & giờ": đổi tên, tách, gộp nguồn, hoặc chọn ảnh rồi gán "Thuộc
  máy: B". Dùng được cả khi EXIF thiếu.
- **Đọc số serial:** [Chờ duyệt], xem UX-3 ở mục 13.

**Chỉnh giờ:**
- Chọn hai ảnh "chụp cùng lúc" từ hai nguồn, hoặc nhập tay số giây.
- Độ lệch lưu theo nguồn máy, trong dữ liệu Media. Không sửa EXIF, không sửa `capture_time`; giờ đã chỉnh luôn tính lại
  từ giờ gốc.
- Sau khi chỉnh, áp dụng mục 8 (khoảnh khắc 📌, cảnh báo lệch giờ, hoàn tác).
- P/X, nhãn và người giữ nguyên, vì chúng gắn theo mã ảnh.

**Ca kiểm thử:**

| Mã | Tình huống | Mong đợi |
|---|---|---|
| CAM-01 | Hai máy cùng dòng, không serial, hai thư mục | Hai nguồn; chỉnh giờ một nguồn không ảnh hưởng nguồn kia |
| CAM-02 | Hai máy cùng dòng, chung thư mục | Một nguồn; gán tay tách được; chỉnh giờ sau khi tách áp đúng ảnh |
| CAM-03 | Hai cặp `DSC_0001.NEF/.JPG` ở hai thư mục | Hai ảnh riêng, mỗi ảnh ghép đúng cặp; xuất không ghi đè |
| CAM-04 | Chỉnh giờ sau khi đã P/X, gán nhãn, gán người, sửa tay khoảnh khắc | Mọi thứ còn nguyên, gắn đúng ảnh |
| CAM-05 | Ảnh thiếu EXIF giờ / hãng | "Không rõ giờ" / "Máy không rõ"; gán tay được |
| MED-03 | Như mục 8 | Như mục 8 |

## 10. Luồng Media sau khi nhập ảnh

**Phương án của bản 3:** một nút **Phân tích sự kiện** chạy chung mọi bước. **[Chờ duyệt]**, xem UX-1 ở mục 13.

| Bước | Người dùng bấm | Khi nào duyệt được |
|---|---|---|
| 1. **📂 Nhập ảnh** | chọn thư mục | **Ngay khi ảnh hiện trong lưới**: xem lớn, P/X/sao, so sánh, lọc theo nguồn máy. Ảnh theo thứ tự giờ gốc |
| 2. **🕒 Máy ảnh & giờ** | hiện tự động nếu có **từ 2 nguồn máy**; bấm **Bỏ qua** hoặc chỉnh giờ | Vẫn duyệt được; có thể quay lại bước này bất cứ lúc nào |
| 3. **🧠 Phân tích sự kiện** | một nút; tạm dừng / chạy tiếp được | Duyệt **trong lúc** phân tích: nhãn xuất hiện dần, ảnh chưa xong có ⏳ |
| 4. **Rà và sửa** | sửa nhãn, người, khoảnh khắc; tuỳ chọn bấm "Gợi ý lại từ các ảnh đã xác nhận" | Bất cứ lúc nào |
| 5. **⤴ Xuất ảnh** | chọn cách chia thư mục | Bất cứ lúc nào; ảnh có ⏳ vẫn xuất được theo P/X |

**Thứ tự trong bước 3** (để hiện dần nhanh nhất):
1. cỡ cảnh + cảnh báo nét + nội dung ảnh, theo từng ảnh;
2. khoảnh khắc, khi đủ ảnh;
3. gom người, sau cùng.

**Không bước nào tự chạy** khi người dùng chưa bấm.

## 11. Kiểm chứng: thu nhãn và chấm điểm

**Loại nhãn mẫu:**
- cỡ cảnh;
- nội dung ảnh (nhiều nhãn);
- Nét / Out nét / Trật nét;
- người: "cùng người với ảnh X" / tên;
- **ranh giới khoảnh khắc**;
- **"Chưa đánh giá"**: ảnh bỏ qua, **không tính** vào tỉ lệ.

**Hai tập tách riêng, chia theo khoảnh khắc** (để ảnh gần giống nhau không rơi vào cả hai tập):
- **Tập chỉnh ngưỡng:** khoảng 40 %, chỉ dùng để chỉnh ngưỡng.
- **Tập chấm:** khoảng 60 %, không bao giờ dùng để chỉnh.

| Mốc | Thu nhãn | Có kết quả AI để chấm |
|---|---|---|
| **Mốc 1** | cỡ cảnh, nét, ranh giới khoảnh khắc, **nội dung ảnh (thu sớm)**, người | cỡ cảnh, cảnh báo nét, khoảnh khắc |
| **Mốc 2** | bổ sung nếu thiếu mẫu | **nội dung ảnh** (dùng nhãn thu ở Mốc 1), **gom người** |
| **Mốc 3** | — | chọn ảnh tự động (nếu được duyệt) |

**Tiêu chí nghiệm thu:**
- Mỗi tỉ lệ ghi **kèm số mẫu**, ví dụ "41/47 (87 %)".
- Nhóm có **dưới 15 mẫu** ghi **"chưa đủ mẫu"**, không kết luận đạt hay không.

| Nhóm | Báo cáo | Ngưỡng đạt (đề xuất) |
|---|---|---|
| **Cỡ cảnh** | (1) **Độ chính xác** trên các ảnh AI đã xếp Toàn/Trung/Cận; (2) **tỉ lệ Chưa xác định** trên ảnh có người; bảng nhầm lẫn | (1) ≥ 85 %; (2) ≤ 20 % |
| **Nội dung ảnh**, mỗi nhãn | **Tỉ lệ gắn đúng** (trong các ảnh AI gắn nhãn đó, bao nhiêu đúng) và **tỉ lệ tìm thấy** (trong các ảnh đúng là nhãn đó, AI tìm ra bao nhiêu) | gắn đúng ≥ 85 %; tìm thấy ≥ 70 % |
| **Out nét** | tỉ lệ bắt được; tỉ lệ báo nhầm | bắt ≥ 90 %; nhầm ≤ 10 % |
| **Trật nét** | tỉ lệ bắt được; tỉ lệ báo nhầm | bắt ≥ 60 %; nhầm ≤ 10 %; dưới 15 ca thì "chưa đủ mẫu" |
| **Gom người** | (1) **gộp nhầm**: số nhóm chứa hơn một người thật; (2) **tách nhầm**: số người thật bị chia thành nhiều nhóm; (3) **tỉ lệ nhận được mặt** | (1) **0** với người đã đặt tên, ≤ 2 % số nhóm còn lại; (2) báo số, chưa đặt ngưỡng; (3) báo số |
| **Khoảnh khắc** | ranh giới đúng / thừa / thiếu (AI); số thao tác sửa tay (MED-02, MED-03) | báo số, chưa đặt ngưỡng |

- **Không đạt ngưỡng:** nhãn đó hiện "(thử nghiệm)" và không dùng cho chọn ảnh tự động.
- **Công cụ:**
  - chế độ **"Dán nhãn mẫu"** trong app;
  - lệnh chấm chạy offline, đầu ra JSON chỉ có số, giống `--diagnose-grouping` [Repo];
  - khoảng 100–150 ảnh có nhãn cho Mốc 1.

## 12. Mô hình và giấy phép

Media là việc **có thu tiền**. **Căn cứ duy nhất** để Media nạp một trọng số là `configs/model-policy.json` (LIC-1,
dùng chung cho cả hai chế độ, thay `configs/media-models.json` của bản 5). Trạng thái chỉ có ba loại:
- **verified**: có căn cứ quyền, SHA-256 của file được ghim trong danh sách; nạp được ở các chế độ ghi trong `modes`;
- **pending**: chưa có căn cứ; **không nạp ở chế độ nào**, chức năng dùng phương án dự phòng;
- **never**: không bao giờ nạp, không đóng gói.

**Media chỉ nạp trọng số `verified` có chế độ `media`**, qua `MediaRegistry` (`app/media/models.py`); yêu cầu nào khác bị
từ chối trước khi mở file. Xác nhận của chủ dự án chỉ duyệt việc triển khai, **không phải căn cứ quyền**; vì vậy MOD-1
(chấp nhận rủi ro CLIP) không làm CLIP thành `verified`.

| Trọng số (id) | Trạng thái hiện tại | Chế độ | Media dùng cho | Khi không nạp được |
|---|---|---|---|---|
| YOLOX-S (`person_detector_s`) | **verified** | cá nhân, media | cỡ cảnh, chủ thể, nét | **Chặn build** từ Mốc 1 |
| YOLOX-M (`person_detector_m`) | **verified** | cá nhân, media | như trên, khi GPU nhanh hơn | Dùng YOLOX-S |
| YuNet (`face_detector`) | **verified** | cá nhân, media | cỡ cảnh, nét | **Chặn build** từ Mốc 1 |
| SFace (`face_embedder`) | **pending** | — | gom người (Mốc 2) | Gom người **chỉ gán tay** |
| CLIP ViT-L/14 (`clip_l14_image`, `clip_prompts`) | **pending** | — | nội dung, đổi cảnh, gần trùng | **Phương án dự phòng §12a** (đang dùng) |
| eDifFIQA(T), MediaPipe ×2 | verified | chỉ cá nhân | không dùng ở Media | — |
| LAION aesthetic | pending | — | không dùng ở Media | — |
| YoutuReID | pending | — | không dùng | — |
| ArcFace, TOPIQ ×3 | **never** | — | không dùng | Không đóng gói |

Điều khoản dữ liệu huấn luyện và nguồn của từng trọng số: `docs/model-licenses.md`, `docs/legal/`.

**Kiểm chứng đã có trong repo** (LIC-1, Mốc 1 M10):
1. `MediaRegistry` từ chối mọi trọng số không `verified` cho Media; test `tests/unit/test_media_models.py`.
2. **Quét mã:** mã Media (kể cả cửa sổ Media) không import luồng phân tích Chụp cá nhân (`identity_plus`, `aesthetic`,
   `iqa`, `clip_aesthetic`, `embed_job`, `quality_job`, `analyze_job`) và không tự tạo `ModelRegistry`.
3. **Báo cáo A** (`--self-test`): bước Media chạy phân tích trên ảnh tổng hợp và ghi từng trọng số đã mở kèm SHA-256 và
   provider; mở trọng số ngoài danh sách Media thì self-test **lỗi**. Kết quả Linux / CI: chỉ `person_detector_s` +
   `face_detector` (YOLOX-M khi có GPU).
4. **Báo cáo B** (`scripts/check_package.py`): mọi file trong `models\` của bản đóng gói phải là trọng số `verified`
   có SHA-256 ghim; không có trọng số `never` hay `pending`.
5. Mỗi lượt phân tích Media ghi `analysis_runs` (chế độ `media`) và trọng số thật đã mở; mỗi nhãn AI mang `run_id`.

## 12a. Các chức năng phụ thuộc CLIP và phương án dự phòng

CLIP ViT-L/14 chỉ được nạp trong Media khi `configs/model-policy.json` ghi nó là **`verified`** cho chế độ `media`
(mục 12). **Hiện CLIP là `pending`**, nên Media đang chạy **phương án dự phòng** dưới đây (đã làm ở Mốc 1). Báo cáo A ghi
CLIP trong danh sách "không nạp" kèm phương án dự phòng.

| Chức năng | Dùng CLIP để làm gì | Phương án dự phòng (không CLIP) | Ca nghiệm thu khi dự phòng |
|---|---|---|---|
| **Gợi ý nhãn nội dung ảnh** (mục 4) | So ảnh với mô tả chữ của từng nhãn | **Không có gợi ý AI.** Mọi ảnh để **Chưa xác định**; người dùng gán tay (phím số 1–5, gán nhiều ảnh một lúc, gán cho cả khoảnh khắc) | CT-F1: không ảnh nào có nhãn "AI gợi ý". CT-F2: gán tay 5 nhãn, nhiều nhãn trên một ảnh, hoàn tác. Không chấm tỉ lệ gắn đúng / tìm thấy (ghi "không áp dụng") |
| **Gợi ý lại** nhãn nội dung từ ảnh đã xác nhận (mục 3) | Độ giống CLIP giữa ảnh | **Tắt** nút "Gợi ý lại" cho nhãn nội dung | CT-F3: nút ẩn hoặc mờ, kèm giải thích |
| **Chia khoảnh khắc theo đổi cảnh** (mục 8) | Độ giống CLIP giữa các nhóm ảnh liên tiếp | Chỉ chia theo **khoảng nghỉ** của giờ đã chỉnh; người dùng tách tay ("Tách tại đây") | MT-F1: chia đúng khi có khoảng nghỉ ≥ ngưỡng. **MED-02 (không có khoảng nghỉ):** AI **được phép** không tách; báo số thao tác sửa tay (dự kiến 1 lần "Tách tại đây"). MED-03 không đổi, vì không dùng CLIP |
| **Gợi ý tên booth** (mục 4) | Ảnh trông giống + chụp gần giờ | Chỉ theo **giờ**: ảnh trong cùng khoảnh khắc với ảnh đã gán tên, chưa có tên booth, được gợi ý cùng tên | BT-F1: gợi ý chỉ trong cùng khoảnh khắc; không gợi ý sang khoảnh khắc khác |
| **Tránh chọn ảnh gần trùng** (chỉ khi UX-2 = có) | Độ giống CLIP | Dùng **burst theo giờ** (ảnh cách nhau ≤ 3 giây), như `app/quality/burst.py` [Repo] | PK-F1: không chọn hai ảnh cùng burst |

**Ảnh hưởng tới bản dán nhãn mẫu (Mốc 1):**
- **Có CLIP:** bản dán nhãn hiện gợi ý nội dung, để chấm sau ở Mốc 2.
- **Không CLIP:** bản dán nhãn vẫn **thu nhãn nội dung bằng tay**, giống hệt. Các nhãn này dùng làm dữ liệu chấm nếu
  sau này CLIP được duyệt.
  - Không có kết quả AI nội dung để chấm.
  - Khoảnh khắc chỉ được chấm theo khoảng nghỉ.
  - Ghi rõ hai giới hạn này trong báo cáo chấm.

**Chế độ Chụp cá nhân** cũng theo cùng danh sách: CLIP `pending` nên Chụp cá nhân hiện cũng không nạp CLIP (LIC-1).

## 13. Quyết định của chủ dự án (đã chốt 2026-11-06)

| Mã | Quyết định |
|---|---|
| **Bản 5** | **Duyệt**; bắt đầu viết mã Media trên nhánh `beta` |
| **UX-1** | Một nút **"Phân tích sự kiện"** chạy chung, tạm dừng / chạy tiếp được, kết quả hiện dần |
| **UX-2** | **Chưa làm** Chọn ảnh tự động; để bản sau. Bản Beta chỉ báo "đủ cỡ cảnh" theo khoảnh khắc |
| **UX-3** | **Không đọc** số serial; nguồn máy theo thư mục + hãng / dòng máy, và gán tay |
| **UX-4** | Rung máy và nhòe chuyển động tính là **Out nét** |
| **MOD-1** | Chủ dự án chấp nhận rủi ro của model card CLIP (2026-11-06). **Sau LIC-1:** đây là hồ sơ chấp nhận rủi ro, **không phải căn cứ quyền**; CLIP vẫn `pending` trong `configs/model-policy.json` (MED-CLIP) và Media chạy phương án dự phòng §12a |
| **MOD-2** | Chủ dự án **có thu tiền** khi chụp cá nhân → ArcFace và TOPIQ trong chế độ Chụp cá nhân là **vấn đề giấy phép cần xử lý**. Đây là việc riêng, ngoài phạm vi Media; mình sẽ trình đề xuất thay thế riêng |
| **NAME** | Giữ tên làm việc |
| **THR** | Đồng ý các ngưỡng ở mục 11 |

## 14. Phạm vi Beta và mốc làm việc

**Có trong Beta:**
- nhập nhiều máy, nguồn máy, chỉnh giờ;
- 3 nhóm lọc ở Mốc 1 (cỡ cảnh, nội dung, lỗi nét); nhóm Người & vai trò ở Mốc 2;
- trạng thái nhãn;
- khoảnh khắc (📌, ⚠ lệch giờ);
- lọc, P/X, Ctrl+Z, so sánh;
- xuất ảnh;
- dán nhãn mẫu.

**Chờ duyệt:** chọn ảnh tự động (UX-2).

**Không có trong Beta:**
- nhớ người qua sự kiện;
- đọc chữ / logo;
- tự xếp cỡ cảnh cho ảnh vật thể;
- cảnh báo "Nhòe chuyển động" riêng (nếu UX-4 = a).

**Mốc làm việc:**
- **Mốc 0** (trước mọi bản build có trọng số Media):
  - `MEDIA_MODELS`, lớp bọc registry, test quét mã;
  - báo cáo A/B trong CI;
  - xác minh điều khoản (mục 12).
- **Mốc 1:**
  - dữ liệu Media riêng, nhập nhiều máy, chỉnh giờ;
  - khoảnh khắc (📌, ⚠);
  - cỡ cảnh, cảnh báo nét, gợi ý nội dung (chưa chấm);
  - chế độ dán nhãn mẫu.
  - → **Bản dán nhãn mẫu**, có báo cáo A/B. Chấm cỡ cảnh / nét / khoảnh khắc.
- **Mốc 2:** gom người, tên, vai trò, sửa gộp/tách; gợi ý lại. Chấm nội dung ảnh và người.
- **Mốc 3:** xuất ảnh; chọn ảnh tự động (nếu duyệt); hồi quy Chụp cá nhân; test Windows.
  - → **Một bản thử cuối**, kèm bảng kiểm tra hai chế độ và báo cáo chấm điểm.

## 15. Đã xác minh / cần kiểm chứng

**Đã xác minh trong repo:**
- Không đọc serial; chỉ đọc hãng / dòng máy (`app/ingest/metadata.py`).
- RAW+JPEG ghép theo thư mục + tên; trùng tên ở hai thư mục là hai ảnh (`app/ingest/scanner.py`).
- Lựa chọn lưu theo `decisions.asset_id`; giờ chụp ở `assets.capture_time`.
- Manifest: nguồn, SHA-256, giấy phép của từng mô hình ở mục 12.
- Đường nạp ArcFace / YoutuReID (`embed_job.py`) và TOPIQ (`aesthetic.py`, `iqa.py`) đã gỡ khỏi phân tích (LIC-1 C4);
  ArcFace, TOPIQ là `never`, YoutuReID `pending`.
- Danh sách cho phép `configs/model-policy.json` (verified / pending / never, SHA-256 ghim); `MediaRegistry` chỉ nạp
  `verified` cho Media; CLIP và SFace `pending`.
- Đã có: gộp / tách / "khác nhau" / hoàn tác; bước tự kiểm tra bản đóng gói; test chặn mạng; lệnh chẩn đoán chỉ ra số.

- Burst theo giờ (≤ 3 giây) đã có ở `app/quality/burst.py`; đây là phương án dự phòng cho việc tránh chọn ảnh trùng.

**Cần ảnh mẫu:**
- Mọi ngưỡng và tỉ lệ ở mục 11.
- Các ca SZ-01a…05, FC-01…05, MED-02 (ảnh thật).
- Dung sai τ của quy tắc lệch giờ.
- MT-F1 và MED-02 ở chế độ dự phòng (CLIP `pending`).
- MED-03 / 03b / 03c chạy được **bằng ảnh tổng hợp** trong test tự động, không cần ảnh mẫu.
- Tỉ lệ nhận được mặt và mức độ gom của SFace.

**Cần Windows/CUDA:**
- Thời gian phân tích 1.000 / 5.000 ảnh.
- Báo cáo A/B trên bản đóng gói.
- Hồi quy Chụp cá nhân (11 bước).
- Màn hình chọn chế độ ở 1080p / 150 %.

**Chờ xác minh (tài liệu gốc):**
- Điều khoản dữ liệu huấn luyện của YOLOX, YuNet, SFace, MediaPipe, LAION.
- Căn cứ quyền cho CLIP và SFace (để chuyển từ `pending` sang `verified`; xác nhận của chủ dự án không thay được).

---

## Phụ lục A — Đối chiếu sáu mục rà soát bản 3

| # | Yêu cầu | Đã sửa ở |
|---|---|---|
| 1 | Giữ bốn nhóm lọc; nội dung nhiều nhãn; Booth / Gian hàng gộp; người "nếu khả thi"; tên làm việc | Mục 2 (bảng 4 nhóm), mục 4, mục 7 ("Nếu khả thi") |
| 2 | Tách quyết định UX; mô tả luồng sau nhập ảnh, bước bấm, khi nào duyệt được; nút chung là phương án bản 3; giữ chọn ảnh tự động / serial / nhòe ở trạng thái chờ | Mục 10 (bảng luồng), mục 13 (UX-1…UX-4) |
| 3 | Giữ khoảnh khắc sửa tay; ca hai máy lệch giờ, ảnh đổi vị trí qua ranh giới; giữ danh sách ảnh; mong đợi khi chỉnh giờ, phân tích lại, hoàn tác | Mục 8 (📌 danh sách ảnh, ⚠ lệch giờ, hoàn tác), ca MED-03 |
| 4 | Tiêu chí nghiệm thu: tỉ lệ Chưa xác định; gắn đúng + tìm thấy cho từng nhãn; gộp nhầm / tách nhầm / nhận được mặt; ngưỡng Trật nét, số mẫu, "chưa đủ mẫu" | Mục 11 (bảng tiêu chí) |
| 5 | Ca ảnh cận mờ: tách dò được mặt / chỉ dò được người, khung người dự phòng hoặc Chưa xác định; ca LED: không đủ căn cứ Trật nét | Mục 5 (hai đường xếp, SZ-01a/b), mục 6 (ba điều kiện Trật nét, FC-02a/b) |
| 6 | Kiểm tra mô hình trước bản build đầu tiên, kể cả bản dán nhãn; báo riêng mô hình nạp khi chạy và có trong bộ cài; đánh dấu điều khoản chờ xác minh | Mục 12 (kiểm tra bắt buộc, báo cáo A/B), mục 14 (Mốc 0) |

## Phụ lục B — Đối chiếu hai mục rà soát bản 4

| # | Yêu cầu | Đã sửa ở |
|---|---|---|
| 1 | Chốt quy tắc lệch giờ MED-03; khoảng đối chiếu độc lập với ảnh đang kiểm tra; dữ liệu giờ cụ thể; khoảng chồng nhau; trạng thái sau Chuyển → Ctrl+Z → Ctrl+Z | Mục 8: "Quy tắc lệch giờ" (chỉ kiểm tra ảnh của nguồn vừa chỉnh; khoảng đối chiếu chỉ tính từ ảnh **không** thuộc nguồn đó, nên độc lập với ảnh được kiểm tra; τ = 30 s; chồng nhau thì không cảnh báo; gợi ý theo tâm gần nhất; khoảng trống thì không cảnh báo; cảnh báo lưu cùng bước chỉnh giờ và hoàn tác theo nó); bảng dữ liệu MED-03; bảng trạng thái S0–S4 có giải thích từng ảnh; ca phụ MED-03b (vùng chồng), MED-03c (không có khoảng đối chiếu), MED-03d (ảnh máy kia không bị kéo theo) |
| 2 | Ghi đủ chức năng phụ thuộc CLIP; dự phòng cho nội dung **và** khoảnh khắc; ca nghiệm thu; giới hạn bản dán nhãn; giữ báo cáo A/B; trọng số chưa kiểm tra thì loại khỏi build hoặc chặn build | Mục 12a (5 chức năng, dự phòng, ca CT-F1…3, MT-F1, BT-F1, PK-F1, ảnh hưởng tới bản dán nhãn); mục 12 (bản 6: `configs/model-policy.json` thay `configs/media-models.json`, bảng chặn / dự phòng, báo cáo A/B tách riêng); MOD-1 ở mục 13 |
