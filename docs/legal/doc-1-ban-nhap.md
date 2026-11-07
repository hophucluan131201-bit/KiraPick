# DOC-1 — Bản nháp giấy tờ cho bản test đầy đủ (2026-11-07)

**Trạng thái: BẢN NHÁP.** Chưa thay `LICENSE.md`, chưa sửa ghi chú phát hành trong bộ cài, chưa gửi cho ai. Phần A và
phần B **trình riêng** để chủ dự án quyết định. Phần C hoàn thiện **sau khi có kết quả test**.

Đây là bản nháp kỹ thuật dựa trên giấy tờ có trong repo, **không phải tư vấn pháp lý**. Xác nhận của chủ dự án chỉ duyệt
việc triển khai trong dự án; quyền dùng từng thành phần căn cứ vào điều khoản của bên cấp quyền
(`docs/legal/kiem-ke-quyen-su-dung.md`, `configs/model-policy.json`).

---

## A. Điều khoản dùng thử cho người test (trình riêng)

**Hiện trạng:** `LICENSE.md` của KiraPick là **PolyForm Noncommercial 1.0.0**: người nhận được dùng, chép, sửa, chia sẻ
cho mục đích **không thương mại**; bán hoặc dùng trong sản phẩm thương mại cần tác giả cho phép. Bộ cài kèm
`LICENSE.md` này.

**Bản nháp đề xuất** (một trang tiếng Việt, đặt cạnh bộ cài và trong `{app}\docs\`; tên file đề xuất
`DIEU_KHOAN_DUNG_THU.txt`):

> **KiraPick — bản dùng thử <phiên bản>**
>
> 1. **Đây là bản thử trước khi phát hành.** Có thể còn lỗi. Bạn dùng theo hiện trạng, không có bảo hành.
> 2. **Ảnh của bạn:** KiraPick không sửa, không xoá, không di chuyển ảnh gốc; xuất ảnh là sao chép. Dù vậy, hãy thử
>    trên **bản sao** của buổi chụp và giữ bản gốc ở nơi khác.
> 3. **Offline:** KiraPick chạy trên máy bạn. Không gửi ảnh, nhãn hay dữ liệu nào ra ngoài. Chỉ mục "Cập nhật KiraPick"
>    dùng mạng, khi bạn bấm hoặc khi bạn bật kiểm tra hằng ngày (mặc định tắt).
> 4. **Nhãn AI là thử nghiệm.** Cỡ cảnh, cảnh báo nét có ghi "(thử nghiệm)": chưa được chấm trên ảnh thật đủ nhiều.
>    Đừng dựa hoàn toàn vào chúng để giao ảnh cho khách.
> 5. **Phạm vi dùng:** theo `LICENSE.md` (không thương mại), trừ khi chủ dự án cho phép khác **bằng văn bản** (xem
>    phần B).
> 6. **Thành phần bên thứ ba** (mô hình AI, thư viện) theo giấy phép riêng, liệt kê trong `THIRD_PARTY_NOTICES.md` và
>    `docs\licenses\`.
> 7. **Góp ý:** gửi cho người đã mời bạn test: bước làm, ảnh chụp màn hình, file `--self-test` nếu được hỏi. Đừng gửi
>    ảnh khách hàng.
> 8. Gỡ cài đặt không xoá ảnh của bạn. Dữ liệu của KiraPick nằm ở `%LOCALAPPDATA%\KiraPick`.

**Câu hỏi cho chủ dự án (A):**
- A-1. Dùng bản nháp trên cho người test? Có muốn thêm thời hạn dùng thử không?
- A-2. Người test có được dùng bản thử cho **job có thu tiền của họ** không? (Theo `LICENSE.md` hiện tại: **không**,
  nếu không có văn bản cho phép; xem B.)

## B. Phạm vi dùng cho job có thu tiền (trình riêng)

**B1. Chủ dự án tự dùng cho job có thu tiền.** Chủ dự án là tác giả mã KiraPick, nên giấy phép PolyForm Noncommercial
không giới hạn chính tác giả. Phần cần căn cứ là **thành phần bên thứ ba** trong bộ cài (theo
`docs/legal/kiem-ke-quyen-su-dung.md` mục 4 và `configs/model-policy.json`):

| Thành phần trong bộ cài | Giấy phép | Job có thu tiền | Còn chưa xác minh |
|---|---|---|---|
| YOLOX-S / -M (dò người) | Apache-2.0 (repo Megvii; file opencv_zoo giống từng byte cho S) | Có theo giấy phép trọng số | Dữ liệu huấn luyện COCO 2017 (ảnh theo giấy phép Flickr từng ảnh) |
| YuNet (dò mặt) | MIT + BSD-3 | Có theo giấy phép trọng số | Dữ liệu WIDER FACE |
| eDifFIQA(T) (chất lượng mặt, chỉ Chụp cá nhân) | CC BY 4.0, phải ghi công | Có | Dữ liệu backbone |
| MediaPipe ×2 (mắt nhắm / mở, chỉ Chụp cá nhân) | Apache-2.0 theo model card; đã chuyển sang ONNX (chuyển đổi tái lập, kiểm trên CI) | Có theo model card | Giấy phép riêng của file `.task` gốc (bảng mục 4 của bản kiểm kê ghi "chưa xác minh" trước khi kiểm tái lập: cần chủ dự án xác nhận dòng này đã đóng) |
| ONNX Runtime, OpenCV, Python | MIT / Apache-2.0 / PSF | Có | — |
| Qt 6 / PySide6, LibRaw | LGPL-3.0 / LGPL-2.1, CDDL | Có, kèm nghĩa vụ LGPL (toàn văn có trong `docs\licenses\`) | — |
| DirectML.dll | Điều khoản tái phân phối của Microsoft | Có | Điều khoản nhắc việc "có thể thu thập thông tin": app vẫn chạy khi tắt mạng; chưa đo riêng DirectML |
| DLL CUDA (bản CUDA) | NVIDIA EULA | Có theo EULA | **Không kèm cuDNN** (LIC-7 b): người dùng tự cài theo SLA của NVIDIA |
| **Không có trong bộ cài:** ArcFace, TOPIQ (`never`); CLIP, LAION, SFace, YoutuReID (`pending`) | — | — | Cần căn cứ quyền mới chuyển được sang `verified` |

**B2. Người test dùng cho job có thu tiền của họ.** Ba phương án, chủ dự án chọn:
- **B2-a (đề xuất cho đợt test):** giữ PolyForm Noncommercial; người test chỉ dùng thử, không dùng cho job có thu tiền.
- **B2-b:** chủ dự án cho phép bằng văn bản riêng từng người (thư / tin nhắn có ghi tên, phiên bản, thời hạn). Thành
  phần bên thứ ba vẫn theo bảng B1.
- **B2-c:** đổi giấy phép của KiraPick. Việc này thay `LICENSE.md` và là quyết định riêng, nên làm trước một bản phát
  hành công khai, không làm giữa đợt test.

**Câu hỏi cho chủ dự án (B):** B-1 chọn B2-a, B2-b hay B2-c? B-2 dòng MediaPipe ở B1 đã đủ căn cứ cho job có thu tiền
chưa?

## C. Ghi chú phát hành (khung; hoàn thiện sau khi có kết quả test)

> **KiraPick <phiên bản>** — <ngày>
>
> **Mới**
> - Chế độ **Media sự kiện** (Beta): mỗi sự kiện có dữ liệu riêng; nhập nhiều máy; chỉnh giờ theo máy; khoảnh khắc tự
>   chia theo khoảng nghỉ, sửa tay được; cỡ cảnh và cảnh báo nét **(thử nghiệm)**; nội dung ảnh và tên booth gán tay;
>   lọc theo cỡ cảnh, nội dung, lỗi nét; xuất ảnh đã chọn theo khoảnh khắc hoặc cỡ cảnh; dán nhãn mẫu và lệnh chấm.
> - Màn hình chọn chế độ khi mở app.
>
> **Thay đổi ở Chụp cá nhân**
> - Bỏ các mô hình không có căn cứ dùng cho việc có thu tiền (ArcFace, TOPIQ). Không còn gom người tự động: gom tay.
>   Không còn điểm thẩm mỹ. Nhóm tự động cũ được ẩn, không mất; nhóm đã sửa tay giữ nguyên.
> - Bản CUDA không kèm cuDNN: cài cuDNN 9 theo `HUONG_DAN_CUDNN.txt`; chưa cài thì app chạy bằng CPU và báo lý do.
>
> **Giới hạn đã biết** <điền từ kết quả test: tỉ lệ thật của cỡ cảnh / nét, ca LED, ISO cao, chi tiết một hướng>
>
> **Nâng cấp** từ 3.0.0 / 3.0.0a: dữ liệu giữ nguyên (CSDL cũ được sao lưu `.v7.bak`). <CLEAN-2: điền theo quyết định>

**Chưa làm:** điền số phiên bản (VER-1), kết quả test, quyết định CLEAN-2; sau đó mới chép vào `packaging/release-notes/`.
