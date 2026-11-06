# Media sự kiện — Đặc tả bản 4 (chờ chủ dự án duyệt)

- **Phạm vi:** nhánh `beta`. Chỉ là tài liệu; **chưa có mã Media nào**.
- **Thời điểm sửa mã:** chỉ sau khi chủ dự án duyệt bản này.
- **Phát hành:** merge vào `main`, gắn tag và phát hành đều cần duyệt riêng.
- **Màn hình chọn chế độ:** giữ nguyên, đã có trên `beta`.

**Thay đổi so với bản 3:** theo 6 mục trong kết luận rà soát bản 3. Bảng đối chiếu ở **phụ lục A**.

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
  trúc dữ liệu của Chụp cá nhân (phiên bản 7) **không đổi**, và không cần chuyển đổi dữ liệu.
- **Hồi quy Chụp cá nhân:**
  - bộ test hiện có (1209 test Linux, 1001 test Windows, hiệu năng, sức chịu) phải đạt nguyên vẹn;
  - bảng 11 bước của bản RC chạy lại trên Windows/CUDA trước bản thử cuối.
- **Thẻ AI là gợi ý:** quyết định cuối cùng thuộc về người dùng (mục 3).

## 2. Bốn nhóm lọc (đã thống nhất)

| Nhóm | Giá trị | Số nhãn mỗi ảnh |
|---|---|---|
| **Cỡ cảnh** | Toàn / Trung / Cận (thêm trạng thái Chưa xác định) | một |
| **Nội dung ảnh** | Sân khấu / Booth / Gian hàng / Decor / Sản phẩm / Merch | nhiều |
| **Người và vai trò** | Diễn giả / Celeb / Talent / Đại biểu; gom và đặt tên từng người **nếu khả thi** (mục 7) | nhiều người mỗi ảnh |
| **Độ nét** | Out nét / Trật nét (cảnh báo) | không, một hoặc cả hai |

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
- **Cách gợi ý:**
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
| FC-01 | Lia máy: chủ thể nét, nền nhòe ngang | Không cảnh báo |
| FC-02a | Mặt diễn giả mờ, **phông vải / bục** ngay sau nét rõ | **Trật nét** |
| FC-02b | Mặt diễn giả mờ, **chỉ màn LED** phía sau nét | **Out nét**, không Trật nét |
| FC-03 | Toàn cảnh, mặt quá nhỏ | Không Trật nét; Out nét chỉ khi cả ảnh mờ |
| FC-04 | Rung tay toàn ảnh | Theo quyết định UX-4 |
| FC-05 | ISO cao nhưng nét | Không cảnh báo |

## 7. Người: gom, tên và vai trò là ba việc riêng

1. **Gom cùng người (AI):** bằng khuôn mặt, mô hình **SFace** (Apache-2.0) [Repo: `app/ai/detect.py`]. Kết quả là các
   nhóm người chưa có tên.
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
(độ giống CLIP giữa các nhóm ảnh liên tiếp).

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
  - Ảnh nào sau khi chỉnh giờ nằm **ngoài khoảng giờ** của khoảnh khắc 📌 chứa nó (rơi vào khoảng của khoảnh khắc khác)
    thì được đánh dấu **⚠ "lệch giờ"**. Người dùng chọn: **Chuyển** sang khoảnh khắc phù hợp, hoặc **Giữ**.
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

**Ca MED-03: hai máy lệch giờ và ranh giới đã tách** [Repo bằng ảnh tổng hợp; Ảnh mẫu nếu có]:
- **Tình huống:**
  1. Máy B chạy chậm 3 phút so với máy A.
  2. Trước khi chỉnh giờ, người dùng "Tách tại đây" giữa phát biểu và trao giải. Lúc đó ảnh B-7 (thật ra chụp lúc trao
     giải) vẫn nằm trong khoảnh khắc "Phát biểu", vì giờ sai.
  3. Người dùng chỉnh giờ máy B (+3 phút).
- **Mong đợi:**
  - Hai khoảnh khắc 📌 giữ nguyên danh sách ảnh.
  - B-7 vẫn ở "Phát biểu", nhưng bị đánh **⚠ lệch giờ**. Bấm **Chuyển** đưa nó sang "Trao giải".
  - P/X, nhãn và người của B-7 không đổi.
  - **Ctrl+Z** lần 1 hoàn tác "Chuyển"; lần 2 hoàn tác chỉnh giờ: B-7 về chỗ cũ, hết ⚠.
  - Phân tích lại sau đó không đổi gì ở hai khoảnh khắc 📌.

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

Media là việc **có thu tiền**. Bảng dưới liệt kê từng bộ trọng số trong `configs/model-manifest.json` [Repo].

| Mô hình | Nguồn và phiên bản | Giấy phép mã / trọng số | Media dùng? | Điều khoản dữ liệu huấn luyện |
|---|---|---|---|---|
| YOLOX-S / -M (dò người) | Megvii YOLOX 0.1.1rc0 | Apache-2.0 | **Có** | **Chờ xác minh** (COCO) |
| YuNet 2023mar (dò mặt) | opencv_zoo@48b10fa | MIT | **Có** | **Chờ xác minh** |
| SFace 2021dec (nhận mặt) | opencv_zoo@48b10fa | Apache-2.0 | **Có** | **Chờ xác minh** |
| CLIP ViT-L/14 ảnh + mô tả chữ | OpenAI ViT-L-14.pt, chuyển lúc build | MIT (mã); model card: "deployed use out of scope" | **Có** | Đã chấp nhận 2026-10-28; **chờ xác nhận lại cho việc có thu tiền** (MOD-1) |
| MediaPipe Face Landmarker v2 + blendshapes | `face_landmarker.task` v1, chuyển ONNX | Apache-2.0 | **Có** (mắt mở) | **Chờ xác minh** (model card) |
| eDifFIQA(T) | opencv_zoo@48b10fa | CC-BY-4.0 | Không | — |
| ArcFace w600k_r50 | InsightFace buffalo_l v0.7 | **Phi thương mại** | **Không** | Cấm dùng thương mại |
| YoutuReID | opencv_zoo@48b10fa | Apache-2.0 | Không | Dữ liệu nghiên cứu |
| TOPIQ ×3 | IQA-PyTorch | **PolyForm Noncommercial** | **Không** | Cấm dùng thương mại |
| LAION aesthetic head | improved-aesthetic-predictor | Apache-2.0 | Không | Chờ xác minh |

**Rủi ro "nạp qua bước dùng chung"** [Repo]:
- Bước phân tích của Chụp cá nhân tự nạp ArcFace + YoutuReID khi có sẵn (`app/workers/embed_job.py`,
  `registry.ready("identity_plus")`).
- TOPIQ nằm ở `app/ai/aesthetic.py` và `app/ai/iqa.py`.

**Kiểm tra mô hình là bước bắt buộc trước bản build đầu tiên** có dùng hoặc đóng gói trọng số Media, **kể cả bản dán
nhãn mẫu ở Mốc 1**. Kiểm tra gồm năm phần:
1. **Danh sách cho phép** `MEDIA_MODELS`: `person_detector_s/m`, `face_detector`, `face_embedder`, `clip_l14_image`,
   `clip_prompts`, `face_mesh`, `face_blendshapes`.
   - Media nạp mô hình qua một lớp bọc `ModelRegistry`; lớp này **báo lỗi ngay** nếu có yêu cầu nạp mô hình ngoài danh
     sách.
2. **Test quét mã:** mã Media không được import `identity_plus`, `aesthetic`, `iqa`, `embed_job`, hay phần LAION của
   `clip_aesthetic`.
3. **Báo cáo A — mô hình Media thực sự nạp khi chạy:**
   - lệnh `--self-test` có thêm bước Media;
   - bước này chạy phân tích Media trên ảnh tổng hợp, rồi ghi **từng mô hình đã nạp kèm SHA-256** vào `selftest.json`;
   - CI so với `MEDIA_MODELS` và manifest; có mô hình ngoài danh sách thì **lỗi**.
4. **Báo cáo B — mô hình có mặt trong bộ cài:**
   - CI liệt kê mọi file trong thư mục `models\` của bản đóng gói, kèm SHA-256 và giấy phép theo manifest;
   - đánh dấu file nào **không phải** mô hình Media. Bộ cài hiện vẫn chứa ArcFace / TOPIQ cho Chụp cá nhân (MOD-2).
5. **Điều khoản chờ xác minh:** các mục "Chờ xác minh" ở bảng trên được kiểm tra trên model card / LICENSE gốc và ghi
   vào `docs/model-licenses.md` **trước bản dán nhãn mẫu**. Mục nào chưa xác minh được thì ghi rõ "chưa xác minh" trong
   báo cáo build.

## 13. Quyết định chờ chủ dự án duyệt

| Mã | Câu hỏi | Các phương án | Đề xuất |
|---|---|---|---|
| **UX-1** | Phân tích chạy thế nào? | (a) **một nút "Phân tích sự kiện" chạy chung** (phương án bản 3); (b) nút riêng cho từng nhóm (cỡ cảnh + nét / nội dung / người) | (a): ít thao tác; vẫn tạm dừng được, và kết quả hiện dần |
| **UX-2** | Chọn ảnh tự động có vào Beta không? | (a) có, **chỉ gợi ý**: không đổi P/X, có nút "Áp dụng gợi ý" (hoàn tác được), ảnh đã P/X không bao giờ bị đổi; (b) để sang bản sau, Beta chỉ có báo "đủ cỡ cảnh" | (b): giữ Beta gọn |
| **UX-3** | Có đọc số serial thân máy không? | (a) đọc, chỉ để phân biệt nguồn, lưu dạng băm, không hiển thị (đổi chính sách quyền riêng tư); (b) không đọc, dùng thư mục + gán tay | (b) |
| **UX-4** | Rung máy và nhòe chuyển động xếp vào đâu? | (a) gộp vào **Out nét**; (b) thêm cảnh báo riêng **"Nhòe chuyển động"**; (c) không cảnh báo | (a) |
| **MOD-1** | Chấp nhận rủi ro CLIP cho việc có thu tiền? | có / không (không thì nhãn nội dung ảnh chỉ gán tay) | Chủ dự án quyết |
| **MOD-2** | Bộ cài vẫn chứa ArcFace / TOPIQ cho Chụp cá nhân | (a) giữ; (b) tách bộ cài; (c) cho phép bỏ khi cài | Chủ dự án quyết (liên quan việc chụp cá nhân có thu tiền không) |
| **NAME** | Tên hiển thị các nhãn | giữ tên làm việc / đổi | Giữ cho Beta |
| **THR** | Ngưỡng đạt ở mục 11 | đồng ý / sửa | Đồng ý |

## 14. Phạm vi Beta và mốc làm việc

**Có trong Beta:**
- nhập nhiều máy, nguồn máy, chỉnh giờ;
- 4 nhóm lọc;
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
- ArcFace / YoutuReID được `embed_job.py` tự nạp; TOPIQ ở `aesthetic.py` / `iqa.py`.
- Phần nhúng CLIP lưu theo ảnh (`asset_vectors`); mô tả chữ tính lúc build (`scripts/convert_clip.py`).
- Đã có: gộp / tách / "khác nhau" / hoàn tác; bước tự kiểm tra bản đóng gói; test chặn mạng; lệnh chẩn đoán chỉ ra số.

**Cần ảnh mẫu:**
- Mọi ngưỡng và tỉ lệ ở mục 11.
- Các ca SZ-01a…05, FC-01…05, MED-02, MED-03 (ảnh thật).
- Tỉ lệ nhận được mặt và mức độ gom của SFace.

**Cần Windows/CUDA:**
- Thời gian phân tích 1.000 / 5.000 ảnh.
- Báo cáo A/B trên bản đóng gói.
- Hồi quy Chụp cá nhân (11 bước).
- Màn hình chọn chế độ ở 1080p / 150 %.

**Chờ xác minh (tài liệu gốc):**
- Điều khoản dữ liệu huấn luyện của YOLOX, YuNet, SFace, MediaPipe, LAION.
- Phạm vi chấp nhận rủi ro CLIP (MOD-1).

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
