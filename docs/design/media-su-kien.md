# Media sự kiện — Đặc tả bản 3 (chờ chủ dự án duyệt)

- **Phạm vi:** nhánh `beta`. Chỉ là tài liệu; **chưa có mã Media nào**.
- **Thời điểm sửa mã:** chỉ sau khi bản 3 được duyệt.
- **Phát hành:** merge vào `main`, gắn tag và phát hành đều cần duyệt riêng.
- **Màn hình chọn chế độ:** giữ nguyên. Đã có trên `beta` từ commit `e05f464` đến `ec744f0`.

**Nguồn sửa đổi:**
- 6 nhóm yêu cầu sửa của chủ dự án (2026-11-06).
- Bản tự phản biện `docs/design/media-su-kien-phan-bien.md`.
- File `media-su-kien_PhanBien_Claude.md` mà chủ dự án nhắc tới **không có** trong các file đã gửi và trong repo.
  Nếu file đó có nội dung khác 6 nhóm yêu cầu trên, cần bổ sung ở bản 4.

**Quy ước trong tài liệu:**
- **[Repo]**: đã xác minh trong mã nguồn hiện tại.
- **[Ảnh mẫu]**: phải kiểm chứng trên bộ ảnh mẫu.
- **[Windows/CUDA]**: phải kiểm chứng trên máy Windows/CUDA.
- **[Chờ duyệt]**: chờ chủ dự án quyết định.

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
- **Thẻ AI là gợi ý:** mọi thẻ do AI gắn chỉ là gợi ý. Thay đổi cuối cùng thuộc về người dùng (mục 2).

## 2. Trạng thái của nhãn và ảnh

Mọi nhãn (nội dung ảnh, cỡ cảnh, cảnh báo nét, người, vai trò, khoảnh khắc) đều ở **một** trong các trạng thái sau:

| Trạng thái | Nghĩa | Hiển thị |
|---|---|---|
| **Đang phân tích** | Ảnh chưa được phân tích xong cho nhóm nhãn này | biểu tượng ⏳; không lọc theo nhãn được |
| **Chưa xác định** | Đã phân tích, nhưng AI không đủ tự tin hoặc không áp dụng được | "?"; lọc riêng được |
| **AI gợi ý** | AI gắn, người dùng chưa xác nhận | chữ thường, kèm mức tự tin |
| **Đã xác nhận** | Người dùng gán, hoặc bấm xác nhận gợi ý | chữ đậm ✓ |
| **Đã bỏ** | Người dùng gỡ một nhãn AI đã gợi ý | không hiện; AI không gợi ý lại nhãn đó cho ảnh này |

**Quy tắc giữ dữ liệu** (áp dụng cho mục 3 tới mục 9):
- **Không thao tác tự động nào** ghi đè nhãn "Đã xác nhận" hoặc "Đã bỏ". Các thao tác tự động gồm: chạy tiếp, phân tích
  lại, chỉnh giờ, AI học lại.
- **P / X / sao / ❤** chỉ đổi khi người dùng bấm.
- **Gộp và tách khoảnh khắc làm tay** được giữ qua mọi lần chạy lại (mục 7).

**Hai việc khác nhau, cần tách riêng:**
1. **Lưu chỉnh sửa** của người dùng: luôn bật, không tắt được.
2. **Dùng ảnh đã sửa để gợi ý lại** cho các ảnh khác (học trong sự kiện):
   - là thao tác riêng, có nút **"Gợi ý lại từ các ảnh đã xác nhận"**;
   - mỗi lần chạy là một bước có thể hoàn tác bằng Ctrl+Z;
   - chỉ đổi các nhãn đang là "AI gợi ý" hoặc "Chưa xác định".

## 3. Nội dung ảnh

- **Nhãn (tên làm việc, có thể đổi sau):** **Sân khấu**, **Booth / Gian hàng**, **Decor**, **Sản phẩm**, **Merch**.
  Booth và Gian hàng gộp thành một nhãn, đã chốt.
- **Một ảnh có thể mang nhiều nhãn**, mỗi nhãn có trạng thái riêng (mục 2). Ví dụ: Booth / Gian hàng (Đã xác nhận) +
  Sản phẩm (AI gợi ý 0,71).
- **Cách gợi ý:**
  - Dùng mô hình **CLIP ViT-L/14**: so phần nhúng ảnh với mô tả bằng chữ của từng nhãn, rồi gắn mọi nhãn vượt ngưỡng.
  - Mô tả bằng chữ được tính sẵn lúc build, giống cách app đã làm với `clip_prompts_v1.npz` [Repo].
  - Ngưỡng của từng nhãn chỉnh trên tập chỉnh ngưỡng (mục 10). Không nhãn nào vượt ngưỡng thì ảnh ở trạng thái **Chưa
    xác định**.
- **Tên booth / nhà tài trợ:**
  - Người dùng gán, ví dụ "Booth Samsung"; đây là nhãn tự đặt, luôn ở trạng thái Đã xác nhận.
  - App **gợi ý** cùng tên cho ảnh trông giống (theo CLIP) và chụp gần giờ.
  - Không đọc chữ hay logo.
- **Chi phí:** phần nhúng CLIP được tính **một lần** cho mỗi ảnh và lưu lại. App đã có bảng `asset_vectors` loại `clip`
  [Repo]; Media dùng cách tương tự trong cơ sở dữ liệu riêng.

## 4. Cỡ cảnh: Toàn / Trung / Cận

**Tách khỏi đánh giá nét.** Cỡ cảnh chỉ dựa vào **vị trí và kích thước** người trong khung, không phụ thuộc ảnh nét hay
mờ. Một ảnh cận diễn giả bị mờ vẫn là **Cận**, kèm cảnh báo **Out nét** ở mục 5.

- **Chủ thể chính:**
  - Là người có mặt nhìn thấy được và khung người lớn nhất, sau khi loại:
    - người bị mép khung cắt mất quá nửa;
    - người quay lưng (không dò được mặt);
    - đầu khán giả ở tiền cảnh, khi khung người đó chạm mép dưới và mặt không thấy.
  - **Không** dùng độ nét để chọn chủ thể. Đây là thay đổi so với bản 2.
  - Chủ thể **lệch khung** (gần mép, không ở giữa) vẫn được chọn.
- **Cách xếp:** theo tỉ lệ chiều cao khuôn mặt chủ thể so với chiều cao ảnh. Ngưỡng ban đầu là **Cận > 12 %**, **Trung
  4–12 %**, **Toàn < 4 %**, và được chỉnh trên tập chỉnh ngưỡng [Ảnh mẫu].
- **Toàn khác Chưa xác định:**
  - **Toàn:** có người trong ảnh nhưng rất nhỏ, hoặc khung người chiếm ít diện tích (toàn cảnh hội trường).
  - **Chưa xác định:**
    - ảnh không có người dò được (ảnh vật thể, decor, sản phẩm);
    - hoặc có người nhưng không dò được mặt nào đủ tin cậy, ví dụ khuôn mặt quá nhỏ trong ảnh toàn cảnh.
  - Trường hợp sau có thể được xếp **Toàn**, nếu tỉ lệ khung người cho thấy rõ đó là cảnh rộng. Ngưỡng chỉnh trên ảnh mẫu
    [Ảnh mẫu].
- **Giới hạn của bản Beta:**
  - App **chỉ tự xếp cỡ cảnh cho ảnh có người**. Ảnh vật thể để **Chưa xác định**.
  - Người dùng gán tay (phím **T / U / C** trên một hoặc nhiều ảnh đang chọn) thì nhãn thành Đã xác nhận.
  - Ghi rõ giới hạn này trong ghi chú phát hành.

**Ca kiểm thử bắt buộc** [Ảnh mẫu]:

| Mã | Ảnh | Kết quả mong đợi |
|---|---|---|
| SZ-01 | Cận diễn giả, bị mờ | Cận + cảnh báo Out nét |
| SZ-02 | Chủ thể lệch sát mép trái/phải | Đúng cỡ cảnh như khi chủ thể ở giữa |
| SZ-03 | Cận vật thể (sản phẩm, merch), không người | Chưa xác định; gán tay được |
| SZ-04 | Toàn cảnh hội trường, khuôn mặt quá nhỏ | Toàn hoặc Chưa xác định, **không** Cận/Trung |
| SZ-05 | Toàn cảnh có đầu khán giả to, mờ ở tiền cảnh | Toàn, không bị coi là Cận |

## 5. Cảnh báo nét: Out nét / Trật nét

- **Cảnh báo, không phải nhãn loại bỏ.** App không tự đánh dấu X; không tự loại ảnh khỏi chọn ảnh tự động, trừ khi
  người dùng bật lọc.
- **Out nét:** vùng chủ thể (hoặc cả ảnh, nếu không có chủ thể) mờ.
- **Trật nét:**
  - Chủ thể có mặt dò được và bị mờ, trong khi một vùng **gần chủ thể** lại nét rõ.
  - Vùng màn LED và đèn quá sáng bị loại khỏi phép so.
  - Ảnh không có chủ thể thì không bao giờ bị báo Trật nét.
- **Đo trên ảnh độ phân giải gốc**, ở vùng chủ thể, có tính tới ISO. [Repo: phép đo nét theo vùng trên ảnh gốc đã có ở
  `app/quality/measure.py`; phần riêng cho Media cần viết thêm.]
- **[Chờ duyệt] Rung máy và nhòe chuyển động xếp vào đâu:**
  - **(a)** gộp vào **Out nét**;
  - **(b)** thêm cảnh báo thứ ba **"Nhòe chuyển động"**. Phân biệt bằng hướng của vệt mờ; độ chính xác cần đo trên ảnh
    mẫu;
  - **(c)** không cảnh báo riêng.
  - Đề xuất: **(a)** cho bản Beta, vì đơn giản và ít báo nhầm. Ghi nhận (b) cho sau.

**Ca kiểm thử bắt buộc** [Ảnh mẫu]:

| Mã | Ảnh | Kết quả mong đợi |
|---|---|---|
| FC-01 | Ảnh lia máy: chủ thể nét, nền nhòe ngang | **Không** cảnh báo |
| FC-02 | Backdrop / màn LED nét hơn mặt diễn giả | Trật nét **chỉ khi** mặt thật sự mờ; LED không gây báo nhầm |
| FC-03 | Toàn cảnh, khuôn mặt quá nhỏ | Không Trật nét; Out nét chỉ khi cả ảnh mờ |
| FC-04 | Rung tay toàn ảnh | Out nét (theo quyết định ở trên) |
| FC-05 | ISO cao, nét | Không cảnh báo (hạt nhiễu không bị coi là nét giả) |

## 6. Người: gom, tên và vai trò là ba việc riêng

1. **Gom cùng người (AI):**
   - Bằng khuôn mặt, dùng mô hình **SFace** (Apache-2.0) [Repo: đã có, `app/ai/detect.py`].
   - Kết quả là các **nhóm người** chưa có tên.
2. **Gán tên (người dùng):** đặt tên cho một nhóm người; tuỳ chọn.
3. **Gán vai trò (người dùng):**
   - Một trong các vai trò: Diễn giả / Celeb / Talent / Đại biểu.
   - Gán được cả khi chưa đặt tên, và gán được **cho từng ảnh** khi không có nhóm người.

**Sửa lỗi gom:**
- **Gộp nhầm** (hai người khác nhau trong cùng nhóm):
  - Mở nhóm, chọn các ảnh mặt không phải người đó, rồi bấm **"Tách thành người mới"**, hoặc kéo sang nhóm khác.
  - App ghi lại cặp này là **"khác nhau"**, nên lần phân tích sau không gộp lại.
- **Tách nhầm** (một người bị chia thành hai nhóm): tick hai nhóm, bấm **🔗 Gộp**.
- Cả hai thao tác đều hoàn tác được bằng Ctrl+Z, và được giữ qua các lần chạy lại.
- [Repo: cơ chế gộp, tách, đánh dấu "khác nhau" và hoàn tác đã có trong Chụp cá nhân (`app/identity/actions.py`,
  `app/undo/`); Media dùng lại cách làm, trên dữ liệu riêng.]

**Danh sách NGƯỜI:**
- Hiện mặc định người **xuất hiện từ 5 ảnh trở lên**, hoặc đã được đặt tên / vai trò.
- Những người khác nằm ở **"Khách khác"**, mở ra được.
- **Gán tên cho người chỉ xuất hiện vài ảnh, ngoài sân khấu:**
  - Mở "Khách khác", hoặc bấm vào khuôn mặt ngay trên ảnh, rồi chọn **"Đặt tên…"**.
  - Người đó lập tức lên danh sách chính, dù chỉ có 1–2 ảnh.

**Gợi ý vai trò:**
- Gợi ý "có thể là Diễn giả / Talent" khi người đó xuất hiện nhiều ở ảnh có nhãn **Sân khấu** đã xác nhận, hoặc AI gợi
  ý với độ tự tin cao.
- Luôn ở trạng thái AI gợi ý.

**Không nhớ người qua các sự kiện.** Khi người dùng xoá sự kiện khỏi app, dữ liệu khuôn mặt của sự kiện đó bị xoá theo.

## 7. Khoảnh khắc

- **AI tự chia** theo giờ chụp đã chỉnh lệch (mục 8), theo hai tiêu chí:
  - khoảng nghỉ dài;
  - **đổi cảnh về hình ảnh** (độ giống CLIP giữa các nhóm ảnh liên tiếp).
- **Người dùng sửa:** gộp, tách, **"Tách tại đây"**, đổi tên; đều hoàn tác được.
- **Ranh giới làm tay được ghi lại** dưới dạng "tách ngay trước ảnh X" và "gộp hai khoảnh khắc chứa ảnh Y và Z".
  - Ranh giới gắn với **ảnh** (mã ảnh cố định), không gắn với giờ.
  - Nhờ vậy, khi chạy lại, phân tích lại hay chỉnh giờ, ranh giới làm tay vẫn đúng chỗ. AI chỉ chia lại phần **chưa có
    ranh giới làm tay**.
- **Ảnh không có giờ chụp** nằm ở khoảnh khắc **"Không rõ giờ"**.
- **Mỗi khoảnh khắc báo đủ cỡ cảnh hay chưa** (dựa trên ảnh đã P), ví dụ "Toàn ✓ Trung ✓ Cận ✗".

**Ca MED-02 (bắt buộc)** [Ảnh mẫu]:
- **Bộ ảnh:** phần phát biểu chuyển **ngay** sang trao giải, **trên cùng sân khấu**, không có khoảng nghỉ. Cùng một
  người (ví dụ diễn giả A) có mặt ở cả hai phần.
- **Mong đợi:**
  - Hai phần thành hai khoảnh khắc. AI có thể chia sai, nhưng người dùng phải sửa được bằng "Tách tại đây".
  - Người A nằm trong một nhóm người, có mặt ở **cả hai** khoảnh khắc.
  - Chọn ảnh riêng cho từng phần được.
- **Báo cáo hai con số riêng:**
  1. **AI tự chia:** ranh giới đúng / sai / thừa / thiếu so với nhãn ranh giới của người dùng.
  2. **Sau khi sửa tay:** cần bao nhiêu thao tác sửa để đạt đúng.

## 8. Nhập nhiều máy và chỉnh giờ

**Hiện trạng repo:**
- **Máy ảnh:** app đọc **hãng** và **dòng máy** (`make`, `model`), **không đọc số serial**. Đây là chủ ý, để bảo vệ
  quyền riêng tư (`app/ingest/metadata.py`).
- **Ghép RAW+JPEG:** ghép trong **cùng thư mục** và **cùng tên file** (`app/ingest/scanner.py`). Hai cặp trùng tên ở hai
  thư mục khác nhau là hai ảnh riêng.
- **Giờ chụp:** lưu ở `assets.capture_time`.
- **Lựa chọn của người dùng:** lưu theo **mã ảnh cố định** (`decisions.asset_id`), không theo giờ hay tên file.

**Nguồn máy:**
- Mặc định, mỗi **thư mục con có ảnh** cộng với **hãng / dòng máy** là một nguồn máy. Ví dụ `Máy A/` + "NIKON Z 6_2".
- **Hai máy cùng dòng, thiếu serial:** nếu ảnh của hai máy nằm ở **hai thư mục khác nhau**, app tách được theo thư mục.
  Nếu nằm **chung một thư mục**, app không tách được.
- **Chỉ định nguồn máy thủ công:**
  - Màn "🕒 Máy ảnh & giờ" liệt kê các nguồn. Người dùng **đổi tên, tách hoặc gộp nguồn**, hoặc chọn nhiều ảnh rồi gán
    **"Thuộc máy: B"**.
  - Dùng được cả khi EXIF thiếu hãng / dòng máy.
- **[Chờ duyệt] Đọc số serial thân máy cho Media:**
  - Có thể đọc **chỉ để phân biệt nguồn máy**, lưu dạng mã băm trong dữ liệu Media, không hiển thị.
  - Việc này đổi chính sách quyền riêng tư hiện tại, nên cần duyệt.
  - Đề xuất: **không đọc** cho bản Beta, dùng thư mục và gán tay.

**Chỉnh giờ:**
- Chọn hai ảnh "chụp cùng lúc" từ hai nguồn; app tính độ lệch, hoặc người dùng nhập tay (giây).
- Độ lệch lưu theo **nguồn máy** trong dữ liệu Media. **Không sửa EXIF**, không sửa `capture_time` gốc. Giờ đã chỉnh
  luôn được tính lại từ giờ gốc cộng độ lệch.
- Sau khi chỉnh giờ:
  - thứ tự ảnh và khoảnh khắc **do AI chia** được tính lại;
  - **ranh giới làm tay** (gắn với ảnh), nhãn đã xác nhận, P/X/sao/❤, người, tên và vai trò **giữ nguyên**.

**Ca kiểm thử bắt buộc** [Repo, bằng ảnh tổng hợp; và Ảnh mẫu nếu có]:

| Mã | Tình huống | Mong đợi |
|---|---|---|
| CAM-01 | Hai máy cùng dòng, không có serial, ở hai thư mục | Hai nguồn riêng; chỉnh giờ một nguồn không ảnh hưởng nguồn kia |
| CAM-02 | Hai máy cùng dòng, chung thư mục | Một nguồn; gán tay tách được; sau khi tách, chỉnh giờ đúng |
| CAM-03 | Hai cặp RAW+JPEG trùng tên (`DSC_0001.NEF/.JPG`) ở hai thư mục | Hai ảnh riêng, mỗi ảnh ghép đúng cặp; xuất không ghi đè (tên " (1)") |
| CAM-04 | Chỉnh giờ sau khi đã P/X, gán nhãn, gán người, tách tay khoảnh khắc | Mọi thứ còn nguyên, gắn đúng ảnh; chỉ thứ tự và phần AI chia thay đổi |
| CAM-05 | Ảnh thiếu EXIF giờ / hãng | Nằm ở "Không rõ giờ" / "Máy không rõ"; gán tay được |

## 9. Phân tích: chạy tiếp và phân tích lại

- **Chạy tiếp** (sau khi tạm dừng hoặc tắt app): chỉ xử lý ảnh còn **Đang phân tích**.
- **Phân tích lại** (ví dụ sau khi đổi ngưỡng hoặc cập nhật app): chỉ ghi lại nhãn ở trạng thái **AI gợi ý** và **Chưa
  xác định**. Nhãn **Đã xác nhận** và **Đã bỏ**, P/X, người đã đặt tên và ranh giới làm tay được giữ nguyên (mục 2).
- **Ghi phiên bản:** mỗi nhãn AI ghi kèm phiên bản mô hình và ngưỡng, giống cách app đang ghi nguồn gốc điểm số [Repo].
  Nhờ vậy biết nhãn nào cần tính lại.
- **Hiện dần:** ảnh xong trước hiện và lọc được trước. Ảnh chưa xong có trạng thái **Đang phân tích** (⏳), phân biệt với
  **Chưa xác định** (?).

## 10. Kiểm chứng: thu nhãn và chấm điểm

**Loại nhãn mẫu người dùng có thể gán:**
- cỡ cảnh;
- nội dung ảnh (nhiều nhãn);
- Out nét / Trật nét / Nét;
- người: "cùng người với ảnh X" / tên;
- **ranh giới khoảnh khắc**: "tách trước ảnh này";
- **"Chưa đánh giá"**, cho ảnh người dùng bỏ qua. Ảnh này **không tính** vào tỉ lệ.

**Hai tập tách riêng:**
- **Tập chỉnh ngưỡng:** khoảng 40 % ảnh có nhãn. Chỉ dùng để chỉnh ngưỡng.
- **Tập chấm:** khoảng 60 %. **Không bao giờ** dùng để chỉnh.
- Chia theo **khoảnh khắc**, không chia theo ảnh lẻ, để tránh ảnh gần giống nhau rơi vào cả hai tập.

| Mốc | Thu nhãn | Có kết quả AI để chấm |
|---|---|---|
| **Mốc 1** | Cỡ cảnh, nét, ranh giới khoảnh khắc, **nội dung ảnh** (thu sớm), người | Cỡ cảnh, cảnh báo nét, khoảnh khắc |
| **Mốc 2** | Bổ sung nếu thiếu mẫu | **Nội dung ảnh** (dùng nhãn thu ở Mốc 1), **gom người** |
| **Mốc 3** | — | Chọn ảnh tự động (nếu được duyệt) |

**Báo cáo mỗi lần chấm** (chỉ có số, không gửi ảnh đi đâu):
- Mỗi tỉ lệ ghi **kèm số mẫu**, ví dụ "Cận đúng 41/47 (87 %)". Nhóm có **dưới 15 mẫu** ghi "chưa đủ mẫu", không kết luận.
- **Cỡ cảnh:** bảng nhầm lẫn Toàn / Trung / Cận / Chưa xác định.
- **Nội dung ảnh:** cho từng nhãn, tỉ lệ đúng và tỉ lệ bỏ sót.
- **Cảnh báo nét:** báo **riêng** Out nét và Trật nét:
  - tỉ lệ bắt được (ảnh lỗi được báo);
  - tỉ lệ báo nhầm (ảnh tốt bị báo);
  - kèm số mẫu.
- **Gom người:** báo **riêng**:
  - **gộp nhầm**: số nhóm chứa hơn một người thật;
  - **tách nhầm**: số người thật bị chia thành nhiều nhóm;
  - số ảnh **không nhận được mặt**.
- **Khoảnh khắc:** ranh giới đúng / thừa / thiếu (mục 7).
- **Ngưỡng đạt:**
  - cỡ cảnh ≥ 85 %;
  - nội dung ảnh ≥ 80 % mỗi nhãn;
  - Out nét: bắt ≥ 90 %, báo nhầm ≤ 10 %;
  - gom người: **0 gộp nhầm** với người đã đặt tên.
  - Nhãn nào chưa đạt thì hiện "(thử nghiệm)" và không dùng cho chọn ảnh tự động.

**Công cụ:**
- Chế độ **"Dán nhãn mẫu"** trong app, gán bằng phím tắt.
- Lệnh chấm chạy offline, đầu ra là JSON chỉ có số, giống `--diagnose-grouping` [Repo].
- Khoảng **100–150 ảnh có nhãn** cho Mốc 1, chia theo khoảnh khắc.

## 11. Mô hình và giấy phép

Media là việc **có thu tiền**. Bảng dưới liệt kê **từng bộ trọng số thực tế** trong `configs/model-manifest.json` [Repo]
và dự kiến của Media.

| Mô hình | Nguồn và phiên bản (theo manifest) | Giấy phép mã / trọng số | Media dùng? | Điều khoản trọng số / dữ liệu huấn luyện |
|---|---|---|---|---|
| YOLOX-S / YOLOX-M (dò người) | Megvii YOLOX release 0.1.1rc0, `yolox_s.onnx`, `yolox_m.onnx` | Apache-2.0 | **Có** | **Chưa xác minh**: huấn luyện trên COCO (ảnh Flickr nhiều giấy phép) |
| YuNet 2023mar (dò mặt) | opencv_zoo@48b10fa | MIT | **Có** | **Chưa xác minh**: dữ liệu huấn luyện (WIDER FACE?) |
| SFace 2021dec (nhận mặt) | opencv_zoo@48b10fa | Apache-2.0 | **Có** | **Chưa xác minh**: dữ liệu huấn luyện của SFace |
| CLIP ViT-L/14 ảnh (`clip_l14_image`) + mô tả chữ (`clip_prompts`, thêm nhãn Media) | OpenAI ViT-L-14.pt, chuyển lúc build | MIT (mã); model card: "deployed use out of scope" | **Có** | Chủ dự án đã chấp nhận (2026-10-28). **Rủi ro còn đó** khi dùng thương mại; cần chủ dự án xác nhận lại cho Media |
| MediaPipe Face Landmarker v2 + blendshapes (mắt nhắm/mở) | `face_landmarker.task` v1, chuyển ONNX | Apache-2.0 | **Đề xuất có** (mắt mở khi chọn ảnh) | **Chưa xác minh**: điều khoản model card của Google |
| eDifFIQA(T) (chất lượng mặt) | opencv_zoo@48b10fa | CC-BY-4.0 | **Không** cho bản Beta | Chưa xác minh: dữ liệu huấn luyện |
| ArcFace w600k_r50 | InsightFace buffalo_l v0.7 | **Phi thương mại** | **Không** | Cấm dùng thương mại |
| YoutuReID | opencv_zoo@48b10fa | Apache-2.0 | **Không** cho bản Beta | Dữ liệu nghiên cứu (Market-1501, DukeMTMC, MSMT17) |
| TOPIQ (thẩm mỹ, kỹ thuật, mặt) | IQA-PyTorch, chuyển lúc build | **PolyForm Noncommercial** | **Không** | Cấm dùng thương mại |
| LAION aesthetic head | improved-aesthetic-predictor | Apache-2.0 | **Không** | Huấn luyện trên điểm AVA (điều khoản dữ liệu chưa xác minh) |

**Rủi ro "nạp qua pipeline dùng chung"** [Repo]:
- Bước phân tích của Chụp cá nhân **tự nạp ArcFace + YoutuReID** khi có sẵn (`app/workers/embed_job.py`,
  `registry.ready("identity_plus")`).
- Bước chấm chất lượng nạp **TOPIQ** (`app/ai/aesthetic.py`, `app/ai/iqa.py`).
- Nếu Media gọi lại các bước này nguyên trạng, Media sẽ dùng mô hình cấm thương mại.

**Đề xuất kiểm tra để bản build chỉ nạp mô hình đã duyệt:**
1. **Danh sách cho phép** trong mã Media, `MEDIA_MODELS`: gồm `person_detector_s/m`, `face_detector`, `face_embedder`,
   `clip_l14_image`, `clip_prompts`, `face_mesh`, `face_blendshapes`.
   - Media nạp mô hình qua một lớp bọc `ModelRegistry`.
   - Lớp này **báo lỗi ngay** nếu có yêu cầu nạp mô hình ngoài danh sách.
2. **Test đơn vị:** chạy toàn bộ phân tích Media trên ảnh tổng hợp, ghi lại mọi mô hình được nạp, rồi khẳng định danh
   sách đó nằm trong `MEDIA_MODELS`.
3. **Test quét mã:** mã Media không được import `identity_plus`, `aesthetic`, `iqa`, `clip_aesthetic` (phần LAION),
   hay `embed_job`.
4. **Bản đóng gói:**
   - lệnh `--self-test` thêm một bước Media, ghi **mã SHA-256 của từng mô hình Media đã nạp** vào `selftest.json`;
   - CI so các mã đó với manifest và hiện kết quả trong thông báo CI.
5. **Mục chưa xác minh:** điều khoản dữ liệu huấn luyện của từng mô hình (cột cuối của bảng) sẽ được kiểm tra trên model
   card / LICENSE gốc. Mình ghi kết quả vào `docs/model-licenses.md` trước khi build bản thử cuối.
6. **[Chờ duyệt]** Bộ cài vẫn chứa ArcFace / TOPIQ cho chế độ Chụp cá nhân.
   - Nếu chủ dự án cũng nhận tiền cho việc chụp cá nhân, đó là vấn đề giấy phép riêng của chế độ đó.
   - Cần quyết định có tách bộ cài không.

## 12. Phạm vi bản Beta

**Có trong Beta (đề xuất):**
- nhập nhiều máy và chỉnh giờ;
- nội dung ảnh;
- cỡ cảnh (ảnh người);
- cảnh báo nét;
- gom người, tên và vai trò;
- khoảnh khắc;
- lọc, P/X, Ctrl+Z, so sánh;
- xuất ảnh (theo khoảnh khắc / nội dung / người / tên booth);
- chế độ dán nhãn mẫu.

**[Chờ duyệt] Chọn ảnh tự động.** Nếu đưa vào Beta, đề xuất:
- Chỉ là **gợi ý**: ảnh được gợi ý có viền / nhãn **"Gợi ý"**. **Không đổi P/X.**
- Nút **"Áp dụng gợi ý"** mới đặt P cho các ảnh gợi ý chưa có lựa chọn. Thao tác này hoàn tác được bằng Ctrl+Z.
- Ảnh người dùng **đã P hoặc X không bao giờ bị đổi**.
- Chạy lại gợi ý chỉ thay **gợi ý cũ**, không đụng P/X.
- Nếu không duyệt: để sang bản sau. Bản Beta chỉ có báo "đủ cỡ cảnh" theo khoảnh khắc.

**Không có trong Beta:**
- nhớ người qua sự kiện;
- đọc chữ / logo;
- cảnh báo "Nhòe chuyển động" riêng (nếu chọn phương án (a) ở mục 5);
- tự xếp cỡ cảnh cho ảnh vật thể.

## 13. Mốc làm việc

Chủ dự án chỉ thử **bản cuối**, cộng **một lần dán nhãn mẫu** ở Mốc 1.

1. **Mốc 1:**
   - dữ liệu Media riêng; nhập nhiều máy, nguồn máy, chỉnh giờ;
   - khoảnh khắc; cỡ cảnh; cảnh báo nét;
   - gợi ý nội dung ảnh (chưa chấm);
   - danh sách cho phép mô hình;
   - chế độ dán nhãn mẫu.
   → **Một bản để dán nhãn mẫu.** Mình chấm cỡ cảnh / nét / khoảnh khắc và chỉnh ngưỡng trên tập chỉnh ngưỡng.
2. **Mốc 2:** gom người (SFace), tên, vai trò, sửa gộp/tách; học trong sự kiện. Chấm nội dung ảnh và người trên tập chấm.
3. **Mốc 3:** xuất ảnh; chọn ảnh tự động (nếu được duyệt); hồi quy Chụp cá nhân; test Windows; bản tự kiểm tra Media
   trong bản đóng gói.
   → **Một bản thử cuối**, kèm bảng kiểm tra hai chế độ và báo cáo chấm điểm.

## 14. Đã xác minh trong repo / cần kiểm chứng

**Đã xác minh trong repo (đọc mã, 2026-11-06):**
- App không đọc số serial máy; chỉ đọc hãng / dòng máy (`app/ingest/metadata.py`).
- RAW+JPEG ghép theo cùng thư mục + cùng tên (`app/ingest/scanner.py`); trùng tên ở hai thư mục là hai ảnh riêng.
- Lựa chọn lưu theo mã ảnh cố định (`decisions.asset_id`); giờ chụp lưu ở `assets.capture_time`.
- SFace, YuNet, YOLOX có trong manifest với nguồn, mã SHA-256 và giấy phép như bảng mục 11.
- ArcFace / YoutuReID được bước dùng chung tự nạp (`embed_job.py`); TOPIQ nằm ở `aesthetic.py` / `iqa.py`.
- Phần nhúng CLIP được lưu theo ảnh (`asset_vectors`); mô tả chữ CLIP được tính lúc build (`scripts/convert_clip.py`).
- Đã có sẵn cơ chế gộp / tách / "khác nhau" / hoàn tác, bước tự kiểm tra bản đóng gói, test chặn mạng, và lệnh chẩn đoán
  chỉ ra số.

**Cần kiểm chứng trên ảnh mẫu:**
- Ngưỡng và độ chính xác: cỡ cảnh, nội dung ảnh, cảnh báo nét, gom người bằng SFace (SFace kém ArcFace; mức kém thực
  tế chưa biết), ranh giới khoảnh khắc.
- Các ca SZ-01…05, FC-01…05, MED-02.

**Cần kiểm chứng trên máy Windows/CUDA:**
- Thời gian phân tích 1.000 / 5.000 ảnh.
- Bản đóng gói chỉ nạp mô hình trong `MEDIA_MODELS` (bước tự kiểm tra Media).
- Hồi quy Chụp cá nhân (bảng 11 bước).
- Màn hình chọn chế độ ở 1080p / 150 %.

**Chưa xác minh (cần đọc tài liệu gốc):**
- Điều khoản dữ liệu huấn luyện của YOLOX, YuNet, SFace và MediaPipe.
- Phạm vi chấp nhận rủi ro CLIP cho việc có thu tiền.
