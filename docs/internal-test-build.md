# Bản thử nội bộ cho chủ dự án — commit `423074b` (chỉ hướng dẫn, CHƯA build)

Dùng cho bước kiểm tra chấp nhận (`docs/owner-acceptance-checklist.md`). **Không phải phát hành:** không gắn tag, không
đăng GitHub Release, không có marker `[release…]` trong commit. Chỉ build khi chủ dự án cho phép rõ ràng.

## 1. Bạn cần quyết định trước khi build

| # | Câu hỏi | Ghi chú |
|---|---|---|
| Q1 | Cho phép build bản thử nội bộ (chỉ DirectML) từ commit `423074b`? | Chưa có lệnh này thì không build |
| Q2 | Số phiên bản của bản thử | Mã nguồn ở `423074b` vẫn ghi `2.2.1` (`app/__init__.py`, mục B4 của `beta-release-checklist.md`). Build nguyên trạng thì cửa sổ hiện "KiraPick 2.2.1" và file tên `KiraPick-Setup-2.2.1.exe` — **trùng tên bản chính thức**, dễ nhầm. Hai cách: (a) giữ `423074b` nguyên trạng và chỉ dùng **bản giải nén (portable)**, ghi rõ ở tên thư mục "KiraPick-TEST-423074b"; (b) cho một commit chỉ đổi số phiên bản (ví dụ `3.0.0b1.dev1`) rồi build commit đó — khi đó bản build không còn đúng là `423074b` |
| Q3 | Cài kiểu nào | Khuyên dùng **bản giải nén**: không ghi đè chương trình 2.2.1 đã cài. Bộ cài `Setup.exe` sẽ thay 2.2.1 |

Cả hai kiểu đều dùng chung dữ liệu `%LOCALAPPDATA%\KiraPick`: phiên làm việc của các thư mục ảnh được nâng cấp lên v7
khi bản thử mở chúng (2.2.1 sau đó từ chối mở các thư mục đó — K1). **Sao lưu thư mục này trước** (bước 0 của bảng
kiểm tra).

## 2. Cách A (khuyên dùng): GitHub Actions, chỉ tạo file tải về (artifact)

Workflow "Build Windows installer" chạy thủ công (`workflow_dispatch`) **chỉ build và lưu artifact 30 ngày**; bước
"Publish release" chỉ chạy khi có `push` kèm marker, nên không phát hành gì.

1. Ghim đúng commit bằng một nhánh tạm (một lệnh đẩy lên GitHub — chỉ làm khi Q1 = có):
   ```
   git push origin 423074b:refs/heads/internal-build-423074b
   ```
2. GitHub → Actions → **Build Windows installer** → **Run workflow** → Branch `internal-build-423074b`,
   editions `directml`, bỏ chọn "Also run the Windows tests". Hoặc:
   ```
   gh workflow run "Build Windows installer" --repo hophucluan131201-bit/KiraPick --ref internal-build-423074b -f editions=directml -f run_perf=false
   ```
3. Job `build` (Windows Server 2022, Python 3.12): thư viện đúng phiên bản trong `packaging/requirements-directml.txt`
   → tải mô hình và kiểm tra SHA-256 → PyInstaller → **tự kiểm tra bản đóng gói với mạng bị chặn** (B6; notice
   "self-test (directml) ok=True version=…") → Inno Setup → artifact `kirapick-windows-directml`
   (`KiraPick-2.2.1-portable.zip`, `KiraPick-2.2.1-BoCai.zip`, `selftest.json`).
4. Ghi lại để tái lập: số run, commit `423074b`, notice self-test, và SHA-256 của file tải về
   (`Get-FileHash .\KiraPick-2.2.1-portable.zip`). Thời gian trong file zip khác nhau giữa các lần build; mã nguồn,
   thư viện và mô hình thì như nhau.
5. Xoá nhánh tạm sau khi xong: `git push origin --delete internal-build-423074b`.

## 3. Cách B: build trên máy Windows của bạn

Cần: Git, Python 3.12 (64-bit), Inno Setup 6 (chỉ để có `Setup.exe`; bản giải nén không cần). Có Internet trong
lúc build (tải thư viện và mô hình); bản build xong chạy hoàn toàn offline.

```powershell
git clone https://github.com/hophucluan131201-bit/KiraPick.git KiraPick-build
cd KiraPick-build
git checkout 423074b
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Edition directml
```

Kết quả trong `dist\installer\`; `dist\selftest.json` phải có `"ok": true`. Bước 5/6 của script là tự kiểm tra bản
đóng gói với mạng bị chặn (B6).

## 4. Dùng bản thử

- **Bản giải nén:** giải nén `KiraPick-2.2.1-portable.zip` vào `D:\KiraPick-TEST-423074b\`, chạy `KiraPick.exe`.
- Làm theo `docs/owner-acceptance-checklist.md`.

## 5. Quay lại 2.2.1

1. Đóng bản thử, xoá thư mục `D:\KiraPick-TEST-423074b\` (bản giải nén) — hoặc cài lại 2.2.1 từ GitHub Release
   `v2.2.1` nếu đã dùng `Setup.exe`.
2. Chép bản sao lưu `%LOCALAPPDATA%\KiraPick` trở lại (hoặc, cho từng thư mục ảnh, đổi `project.snorlu.db.v5.bak` về
   `project.snorlu.db` như mục K1).

## 6. Trạng thái các mục phát hành (kiểm tra 2026-10-31 từ mã nguồn và lịch sử CI, không suy đoán)

| # | Mục | Trạng thái thật | Bằng chứng |
|---|---|---|---|
| B3 | Kiểm tra thủ công trên máy chủ dự án | **chưa làm** | cần bản thử + bảng kiểm tra; không chạy được trong container |
| B4 | Số phiên bản beta 3.0.0b1 | **chưa làm** | `app/__init__.py` ở `423074b`: `__version__ = "2.2.1"` |
| B5 | Ghi chú phát hành beta (nâng cấp phiên v7, `.v5.bak`, cách quay lại) | **chưa làm** | `packaging/notes/RELEASE_NOTES.md` vẫn là nội dung "KiraPick 2.2.1" |
| B6 | Tự kiểm tra bản đóng gói với mạng bị chặn | **chưa chạy trên mã phần 1–3** | có trong `scripts/build_windows.ps1` (bước 5/6); không job `build` nào chạy trong 60 lần CI gần nhất; lần cuối là khi phát hành `v2.2.1` (2026-10-28) |
