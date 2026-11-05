# Gửi bản Private Beta KiraPick 3.0 cho người thử (dành cho chủ dự án)

Đây là cách **gửi riêng**, không phải phát hành công khai.

- **Không** tạo GitHub Release, **không** gắn tag.
- **Không** đăng bộ cài lên trang công khai, nhóm hay diễn đàn.
- Chỉ gửi qua link riêng, cho từng người thử bạn chọn.

Bản dùng là bản ứng viên (RC) đã kiểm tra, không build lại:

| | |
|---|---|
| Mã nguồn | commit `0a68955` (nhánh `beta`) |
| Lần build | run `41918781734` |
| Bản CUDA | `3.0.0b1a` |
| Bản DirectML | `3.0.0b1` |

## 1. Tải và cất bộ cài (làm trước ngày 04/12/2026, sau ngày này GitHub xoá file)

1. Đăng nhập GitHub rồi tải hai gói về.
   - **CUDA** (khoảng 3,1 GB):
     https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41918781734/artifacts/13366729899
   - **DirectML** (khoảng 2,3 GB):
     https://github.com/hophucluan131201-bit/KiraPick/actions/runs/41918781734/artifacts/13367062537
2. Mở PowerShell (Start → gõ `PowerShell` → Enter), dán lệnh sau. Lệnh giải nén mỗi gói vào một thư mục riêng.
   ```powershell
   Expand-Archive "$env:USERPROFILE\Downloads\kirapick-windows-cuda.zip" D:\KiraPick-PhanPhat\CUDA -Force
   Expand-Archive "$env:USERPROFILE\Downloads\kirapick-windows-directml.zip" D:\KiraPick-PhanPhat\DirectML-goc -Force
   "Da giai nen vao D:\KiraPick-PhanPhat"
   ```
3. Kiểm tra mã bằng lệnh ở mục 3 bên dưới. Mọi dòng phải là `KHOP`.
4. Cất thư mục `D:\KiraPick-PhanPhat` ở chỗ an toàn, ví dụ một ổ cứng khác. Từ giờ chỉ gửi đi từ bản này.

## 2. Gửi cái gì cho ai

**Không gửi** file `selftest.json`, `installer-identity.iss`, file `.exe` hay `.bin` lẻ của bản DirectML. Đó là bằng
chứng kiểm tra, không phải bộ cài.

| Người thử có | Gửi bản | Gửi những file |
|---|---|---|
| Card NVIDIA (GTX 10xx trở lên, driver mới) | **KiraPick Beta CUDA 3.0.0b1a** | Trong `D:\KiraPick-PhanPhat\CUDA`: `KiraPick-Beta-CUDA-3.0.0b1a-Setup.exe`, `…-Setup-1.bin`, `…-Setup-2.bin`, `owner_backup.ps1`, `HUONG_DAN_CAI_DAT.txt` |
| Card khác hoặc không có card | **KiraPick Beta 3.0.0b1 (DirectML)** | Chỉ một file: `D:\KiraPick-PhanPhat\DirectML-goc\KiraPick-Beta-3.0.0b1-BoCai.zip` (bên trong đã có bộ cài, file .bin, script sao lưu và hướng dẫn) |

**Luôn gửi kèm** file `NGUOI_THU_doc_truoc.txt`, nằm cùng thư mục với file này. Trong đó có mã SHA-256, cách sao lưu
và các giới hạn đã biết.

**Cách gửi:**
- Dùng link riêng (Google Drive, OneDrive…) chia sẻ cho **đúng từng người**, không bật "ai có link cũng xem được".
- Nhắn mã SHA-256 cho họ qua một kênh khác (ví dụ tin nhắn riêng), để họ tự so.

## 3. Lệnh kiểm tra mã (cho bạn, trước khi gửi)

Dán cả khối vào PowerShell. Phải thấy **mọi dòng bắt đầu bằng `KHOP`**.

```powershell
$mong = @{
  "KiraPick-Beta-CUDA-3.0.0b1a-Setup.exe"   = "7b379701bc276056fcc1604a8062c0664dd55f80545e979842093c3629b18125"
  "KiraPick-Beta-CUDA-3.0.0b1a-Setup-1.bin" = "f0fc1077f6f1ae87e68a7bc9622c3f1389337fc4f4321b1375abf24ad01b699f"
  "KiraPick-Beta-CUDA-3.0.0b1a-Setup-2.bin" = "b9ec4ecc83f79c656f4492efdbbf9c0b50e4abd835b7b92394712a78596cbf7c"
  "KiraPick-Beta-3.0.0b1-BoCai.zip"         = "4f70387316f58514acf23c965434d196b47dd95f755b6cba20485215bf6673ec"
  "KiraPick-Beta-3.0.0b1-Setup.exe"         = "747bd904e4dc0043f32d7e646b97c54ae814d260fcb3597e5721a5b2f0a0a1cd"
  "KiraPick-Beta-3.0.0b1-Setup-1.bin"       = "b1e0f4e213a633fbdf18121d45855008e6d0ff92e49b52d41267df932112df28"
  "owner_backup.ps1"                        = "67dc1097627ff515d0c03f2a957e851ecd388157eb8b34754057e21afd854f51"
}
foreach ($ten in $mong.Keys) {
  $f = Get-ChildItem D:\KiraPick-PhanPhat -Recurse -File -Filter $ten | Select-Object -First 1
  if (-not $f) { "THIEU  $ten" }
  elseif ((Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower() -eq $mong[$ten]) { "KHOP   $ten" }
  else { "SAI    $ten" }
}
```

Có dòng `SAI` hoặc `THIEU` thì **không gửi**, báo lại mình.

## 4. Những điều đã được bảo đảm (đã kiểm tra trên CI và trên máy bạn)

- **Không tự cập nhật từ bản chính thức.**
  - KiraPick 2.2.x không bao giờ tự đưa bản beta cho người dùng.
  - Bản beta không tự nhảy sang bản beta khác. Bản beta mới sẽ được gửi riêng.
- **Cài riêng, không thay bản 2.2.x.** Mỗi bản có tên riêng, thư mục riêng và mục gỡ cài đặt riêng:
  - "KiraPick Beta CUDA": `KiraPick-Beta-CUDA`;
  - "KiraPick Beta": `KiraPick-Beta`.
- **Chạy offline**, không gửi ảnh hay dữ liệu đi đâu. **Không đụng tới ảnh gốc.**
- **Giới hạn đã biết** ghi trong `RELEASE_NOTES.md` (có trong thư mục cài đặt) và tóm tắt trong
  `NGUOI_THU_doc_truoc.txt`.
