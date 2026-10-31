# Bản thử nội bộ CUDA — KiraPick Internal Test CUDA 3.0.0b1.dev1a

Hướng dẫn cài, kiểm tra card NVIDIA, so sánh với bản DirectML và quay lại như cũ. Làm lần lượt từng bước.
Nếu một bước không ra đúng như mô tả: **dừng lại**, chụp màn hình và gửi lại. Đừng đoán.

Bản này chỉ dùng để **kiểm tra chấp nhận** trên máy của bạn. Nó **không phải** bản phát hành.
Thời gian: khoảng 2–3 giờ, gồm cả phần so sánh.

| | |
|---|---|
| Commit | `dbddef4` |
| Lần build (run) | 41231327565 |
| Gói tải về | `kirapick-windows-cuda`, khoảng 3,1 GB; hết hạn tải ngày 30/11/2026 |
| Phiên bản | `3.0.0b1.dev1a` |

## 0. Đọc trước

### Hãy bỏ qua file `HUONG_DAN_CAI_DAT.txt` có trong gói tải

Trong gói tải có file `HUONG_DAN_CAI_DAT.txt`. **Đừng làm theo file đó. Trang này thay thế nó.**

File đó là hướng dẫn của bản chính thức 2.2.1, được đóng gói kèm theo thói quen. Trong đó có câu "Cài bản này sẽ
thay bản kia". Câu này **sai** với bản thử:
- Bản thử CUDA có tên riêng, thư mục riêng và mục gỡ cài đặt riêng.
- Nó **không thay** KiraPick chính thức (2.2.0a hay 2.2.1) và **không thay** bản thử DirectML.

File hướng dẫn đó được giữ nguyên vì bộ cài đã được duyệt không được sửa lén. Bản phát hành sau này sẽ sửa lại hướng
dẫn trong bộ cài.

### Cài riêng nhưng dữ liệu dùng chung

Mọi bản KiraPick trên máy bạn dùng **chung** hai thứ:
- thư mục dữ liệu `%LOCALAPPDATA%\KiraPick`: phiên làm việc của từng thư mục ảnh, bộ nhớ học, nhật ký;
- các cài đặt `HKCU\Software\KiraPick`.

Ba bản dùng chung là: bản chính thức, bản thử DirectML và bản thử CUDA. Cài thành nhiều bộ riêng **không** tách dữ
liệu ra.

### Điều gì làm thay đổi dữ liệu

- **Trình cài không mở app** và không nâng cấp gì. Điều này đã được kiểm tra tự động.
- Khi bạn **mở một thư mục ảnh** bằng bản thử, phiên của thư mục đó được nâng cấp lên v7. Bộ nhớ học `learning.db`
  cũng được nâng lên v7.
- Sau khi nâng cấp, bản 2.2.x **không mở được** phiên đó, và **bỏ qua** bộ nhớ học. Muốn quay lại 2.2.x đầy đủ
  thì **phải khôi phục** bản sao lưu (bước 9).

### Hai quy tắc bắt buộc

- **Không bao giờ chạy hai bản cùng lúc**: bản thử CUDA, bản thử DirectML và bản chính thức. Mở bản này thì đóng
  hẳn bản kia trước. Mở Task Manager kiểm tra: không còn `KiraPick.exe` nào.
- **Chỉ dùng bản sao.** Chép thư mục ảnh ra một chỗ khác rồi chỉ mở bản sao đó. Thẻ nhớ dùng để thử phải được sao
  lưu toàn bộ trước. Không mở buổi chụp đang làm cho khách bằng bản thử.

## 1. Tải bộ cài và kiểm tra mã SHA-256

1. Đăng nhập GitHub và mở: https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41231327565.
   Kiểm tra đúng số run **41231327565** (bản CUDA). Run 41224104483 là bản DirectML: không dùng file của run đó
   hay của run nào khác cho bước này.
2. Kéo xuống mục **Artifacts** → tải **kirapick-windows-cuda**.
3. Giải nén vào `D:\KiraPick-CUDA-CaiDat\`. Thư mục đó phải có **ba file**, để chung một chỗ:
   - `KiraPick-InternalTest-CUDA-3.0.0b1.dev1a-Setup.exe`
   - `KiraPick-InternalTest-CUDA-3.0.0b1.dev1a-Setup-1.bin`
   - `KiraPick-InternalTest-CUDA-3.0.0b1.dev1a-Setup-2.bin`
4. Mở PowerShell và chạy:
   ```powershell
   cd D:\KiraPick-CUDA-CaiDat
   Get-ChildItem KiraPick-InternalTest-CUDA-* | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_ -Algorithm SHA256).Hash.ToLower(), $_.Name }
   ```
5. So từng dòng với bảng dưới. Phải khớp **đủ cả ba**:

   | File | SHA-256 |
   |---|---|
   | `...-Setup.exe` | `7b63572472e8f7ffeb33de17a54e5c6287046b6dea0db22cadde1281bf3699c3` |
   | `...-Setup-1.bin` | `16b20c7bc2954f6b147271d9dfcef415121d35f81832ac75b8be6f15d9266e9a` |
   | `...-Setup-2.bin` | `528f7bb256a70ad7e9ff78f2efe14a336d70db106be8ae3eb5de8995341c121a` |

   Sai dù chỉ một ký tự → **không cài**, báo lại.

## 2. Script sao lưu

Bạn đã có `D:\KiraPick-SaoLuu\owner_backup.ps1` từ lần thử DirectML. Kiểm tra lại mã của file:

```powershell
(Get-FileHash D:\KiraPick-SaoLuu\owner_backup.ps1 -Algorithm SHA256).Hash.ToLower()
```

Kết quả phải là: `96306f5dd04844322306a73da5089e293ea3588d015e87fa5a6d5ad6ab179c26`.

Chưa có file thì tải ở đây (bấm chuột phải → Save as…):
https://raw.githubusercontent.com/hophucluan131201-bit/KiraPick/7265d2bd709d42d7678e8ad38aa1835635bea176/scripts/owner_backup.ps1

## 3. Sao lưu (bắt buộc, trước khi cài)

1. Đóng mọi KiraPick. Kiểm tra trong Task Manager: không còn `KiraPick.exe`.
2. Chạy:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
   ```
3. Cuối cùng phải có hai dòng màu xanh: "Đã sao lưu … SHA-256: khớp" và "Bản sao lưu nằm ở:
   D:\KiraPick-SaoLuu\<ngày-giờ>". **Ghi lại đường dẫn này.**
4. Mở thư mục đó, kiểm tra có đủ:
   - `DOC_TOI.txt`;
   - `KiraPick\sessions`;
   - `kirapick-settings.reg`.
5. Nếu bạn đã thử bản DirectML **sau** lần sao lưu trước, bản sao lưu mới này chứa dữ liệu đã lên v7. Muốn quay về
   2.2.x thì dùng **bản sao lưu cũ**, tức bản làm trước khi cài DirectML. Đừng xoá bản nào.

## 4. Chuẩn bị bộ ảnh để so sánh

1. Chọn một buổi chụp khoảng 200–500 ảnh JPEG, có nhiều người, nhiều bộ đồ.
2. Chép nó thành **hai bản giống hệt nhau**:
   - `D:\Test\SoSanh-CUDA\`
   - `D:\Test\SoSanh-DirectML\`

   Cần hai thư mục khác nhau vì KiraPick nhớ kết quả phân tích theo thư mục. Nếu dùng chung một thư mục, lần chạy
   thứ hai sẽ dùng lại kết quả của lần đầu và thời gian đo sẽ sai.
3. Không đổi bất kỳ cài đặt nào giữa hai lần chạy. Cài đặt là dùng chung, nên hai bản tự dùng cùng cài đặt. Hai bản
   3.0 cũng dùng cùng bộ mô hình AI.

## 5. Cài bản thử CUDA

1. Chạy `KiraPick-InternalTest-CUDA-3.0.0b1.dev1a-Setup.exe`. Nếu SmartScreen cảnh báo: **More info → Run anyway**.
   Lý do: bộ cài chưa được ký số.
2. Trình cài phải ghi "KiraPick Internal Test CUDA 3.0.0b1.dev1a". Giữ thư mục mặc định:
   `%LOCALAPPDATA%\Programs\KiraPick-InternalTest-CUDA`.
   Cuối cùng trình cài **không** mở app. Đó là đúng thiết kế.
3. Kiểm tra Start Menu có đủ:
   - **KiraPick Internal Test CUDA**;
   - **KiraPick** (bản chính thức);
   - **KiraPick Internal Test** (bản DirectML, nếu bạn còn giữ).

   Settings → Apps cũng phải có đủ các mục tương ứng.

## 6. Xác nhận app thật sự dùng card NVIDIA (CUDA)

Bước này không mở thư mục ảnh nào và không đụng dữ liệu của bạn.

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\KiraPick-InternalTest-CUDA\KiraPick.exe" -ArgumentList '--self-test', 'D:\Test\selftest-cuda.json' -Wait
Get-Content D:\Test\selftest-cuda.json
```

Kết quả **đạt** khi có **tất cả** những điều sau:

- `"ok": true`, `"version": "3.0.0b1.dev1a"`, `"edition": "cuda"`, `"network_attempts": []`.
- `"providers"` có `"CUDAExecutionProvider"`.
- Phần `"gpu"`: `"device": "cuda"`, `"note": null`, và `"speed_check"` ghi "Dùng GPU NVIDIA (CUDA)".
- Trong `"steps"`: dòng "people: … device cuda" và "quality: … device cuda".
- `"aesthetic_gpu_check"` và từng mục trong `"quality_plus_models"` (clip, tech_iqa, face_iqa) có
  `"device": "cuda"`. Mục nào ghi `"cpu"` thì mô hình đó **đang chạy bằng CPU**.

**Nếu `gpu.device` là `"cpu"` hoặc `note` có ghi lỗi:**
- **Dừng phần đo tốc độ GPU.** Không so sánh tốc độ nữa.
- Gửi lại `selftest-cuda.json` và `kirapick-ai.log` (bước 8).
- Bạn vẫn có thể gỡ bản thử (bước 9).

Nếu chỉ vài mô hình rơi về CPU: vẫn làm tiếp, nhưng ghi rõ những mô hình đó.

## 7. So sánh CUDA và DirectML trên cùng bộ ảnh

Chuẩn bị trước khi chạy:
- Cắm sạc laptop.
- Chọn chế độ hiệu năng như mọi lần.
- Đóng các ứng dụng nặng.

**Lần A — CUDA**

1. Mở **KiraPick Internal Test CUDA**. Tiêu đề cửa sổ phải ghi **KiraPick 3.0.0b1.dev1a**.
2. Mở thêm một cửa sổ PowerShell để ghi lại bộ nhớ card đồ hoạ (VRAM) mỗi 2 giây:
   ```powershell
   nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -l 2 > D:\Test\vram-cuda.csv
   ```
   - Không có lệnh `nvidia-smi` thì bỏ qua dòng này. Khi đó ghi số cao nhất của **Dedicated GPU memory** trong
     Task Manager → Performance → GPU (NVIDIA).
3. Mở `D:\Test\SoSanh-CUDA`. Ghi giờ bắt đầu, rồi chạy phân tích AI như bình thường. Ghi giờ phân tích xong.
4. Trong lúc chạy, xem Task Manager → Performance. Ghi lại:
   - **Memory**: mức cao nhất (GB);
   - **GPU NVIDIA**: có chạy không, mức "Dedicated GPU memory" cao nhất.
5. Phân tích xong thì ghi lại:
   - số **chủ thể**;
   - số mục **cần xem lại**;
   - chụp màn hình danh sách chủ thể.
6. Bấm Ctrl+C trong cửa sổ PowerShell để dừng `nvidia-smi`. Đóng hẳn app. Kiểm tra Task Manager không còn
   `KiraPick.exe`.

**Lần B — DirectML**

1. Mở **KiraPick Internal Test** (bản DirectML). Tiêu đề cửa sổ phải ghi **KiraPick 3.0.0b1.dev1**.
2. Ghi VRAM giống lần A, nhưng ghi ra file khác:
   ```powershell
   nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -l 2 > D:\Test\vram-directml.csv
   ```
3. Mở `D:\Test\SoSanh-DirectML`. Làm đúng các bước 3–6 như lần A.

Nếu bạn đã gỡ bản DirectML: dùng lại kết quả lần thử DirectML trước (ngày 01/11 trong nhật ký). Khi gửi kết quả,
nhớ ghi rõ đó là bộ ảnh khác.

**Lưu ý khi đọc kết quả.** Hai bản dùng **cùng một chương trình** và **cùng mô hình**; chỉ khác cách chạy trên card
đồ hoạ. Vì vậy:
- Nếu nhóm chủ thể khác nhau giữa A và B, ghi lại cụ thể: ai bị gộp sai, ai bị tách sai.
- Đừng kết luận "CUDA phân loại tốt hơn" khi chưa có số đo cụ thể.
- Cảm giác "phân loại kém hơn bản 2.2" (lần trước) đến từ chương trình 3.0, không phải từ CUDA. Phần đó sẽ được
  xem riêng.

## 8. Gửi lại những gì

1. `D:\Test\selftest-cuda.json`.
2. `%LOCALAPPDATA%\KiraPick\logs\kirapick-ai.log` và `kirapick.log`. Chép ra `D:\Test\` **trước** khi gỡ hay khôi
   phục.
3. `D:\Test\vram-cuda.csv` và `D:\Test\vram-directml.csv`, nếu có.
4. Một bảng nhỏ như sau (thời gian tính bằng phút:giây):

   | | CUDA (A) | DirectML (B) |
   |---|---|---|
   | Số ảnh | | |
   | Thời gian phân tích từ đầu đến xong | | |
   | RAM cao nhất (GB) | | |
   | VRAM cao nhất (GB) | | |
   | GPU NVIDIA có chạy không | | |
   | Số chủ thể / số mục cần xem lại | | |
   | Lỗi hay thông báo lạ | | |

5. Hai ảnh chụp danh sách chủ thể (A và B). Ghi chú nếu nhóm nào khác nhau.

Nhật ký chỉ ghi tên thiết bị và thời gian. Nó không chứa ảnh hay thông tin trong ảnh của bạn.

## 9. Gỡ bản thử và quay lại như cũ

1. Đóng app. Start Menu → **Gỡ cài đặt KiraPick Internal Test CUDA**.
   - Bản chính thức và bản DirectML vẫn còn.
   - Dữ liệu `%LOCALAPPDATA%\KiraPick` vẫn còn: trình gỡ không xoá dữ liệu.
2. Muốn bản 2.2.x mở lại được các thư mục đã mở bằng bản thử, và dùng lại bộ nhớ học, thì **phải** khôi phục:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\KiraPick-SaoLuu\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\<ngày-giờ>
   ```
   - Dùng bản sao lưu làm **trước khi cài bản thử đầu tiên** (bản DirectML).
   - Script không xoá gì: dữ liệu hiện tại được đổi tên thành `KiraPick.truoc-khoi-phuc-<ngày-giờ>`.
   - Nếu khôi phục hỏng giữa chừng, dữ liệu trước đó được đặt lại đúng chỗ và script báo lỗi.
   - Việc khôi phục này đã được kiểm tra tự động trên Windows.

## 10. Những việc còn lại trước khi phát hành

Bản thử này **không** gỡ được việc nào dưới đây. Mỗi việc cần kết quả hoặc lệnh riêng.

1. **B3 — bạn kiểm tra chấp nhận:** bảng kiểm tra `docs/owner-acceptance-checklist.md` và kết quả CUDA ở trang này.
2. **Cần sửa sau khi được duyệt:**
   - F4: tuỳ chọn không tạo thư mục `_kirapick_danh_sach` khi xuất ảnh;
   - F5/F6: nút gộp chủ thể khó tìm; nút "Chọn ảnh" bị khoá trong lúc phân tích;
   - ghi vào nhật ký thiết bị của từng mô hình chất lượng;
   - tìm nguyên nhân phân loại chủ thể kém hơn 2.2.
3. **Hướng dẫn trong bộ cài:** sửa `HUONG_DAN_CAI_DAT.txt` cho mọi bản phát hành sau, rồi build và kiểm tra lại.
4. **B4–B6:** báo cáo quyết định phát hành và **lệnh phát hành beta riêng của bạn**. Chưa có lệnh đó thì không gắn
   tag, không tạo GitHub Release, không phát hành.
5. **Theo dõi tiếp:** K2 và trường hợp chậm bất thường 331 ms trong đo hiệu năng.
