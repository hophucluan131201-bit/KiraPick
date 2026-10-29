# UI part 1 beta — release checklist, known issues, Windows manual validation

Status words: **done** (evidence linked), **pending** (not run yet), **blocked** (needs the owner's PC).
Do not declare the beta ready until every row of section 1 is done (pre-beta review, Task 14 approval).
No release marker is pushed until the owner gives the release command.

## 0. Two separate decisions (final review, 2026-10-29)

| Decision | Status |
|---|---|
| Code review of UI part 1 (Tasks 1–15) | **passed** — Task 15 APPROVED WITH NOTES (implementation only) |
| Release ready (beta may be published) | **NO** — open: B3, B4, B5, B6, K2. Next phase: release-candidate validation, nothing published |

Rules for the release-candidate phase (review):
- Report Windows manual validation step by step (section 3), with the GC log line and any errors.
- Read Windows perf / stress from each step's notice, never from the non-blocking job's green status.
- Finish version (B4), release notes with backup + rollback steps (B5), packaged offline self-test (B6).
- No tag, publish or release without the owner's release command.
- GC (K2): **no `gc.freeze()` in production now**; keep the tested GUI-thread GC guard; decide after numbers from
  the target laptop. One passing CI run does not prove the latency outlier gone.

## 1. Release blockers

| # | Item | Status | Evidence / what is missing |
|---|---|---|---|
| B1 | Full test suite on Linux (offscreen), 3 runs | done | `docs/IMPLEMENTATION_STATUS.md` → Task 15 |
| B2 | Windows CI job `perf` — read EACH notice, the job itself is non-blocking (RV14-01): `suite`, `gui-windows` (real `windows` platform, Segoe UI), `snap-dpi 1 / 1.25 / 1.5 / 2`, `perf`, `stress` | **run 6 (`d6afca4`): all five pass. perf failed in runs 3–5 (K2)** | runs 3–6: suite 500 passed / 150 skipped (models and RAW samples absent in CI); GUI on the real platform 62 passed / 7 skipped (sizes larger than the runner's 1920×1040 desktop); Snap/DPI all fitting sizes pass, no cut-off button with Segoe UI 9 pt; stress 0 of 6 failed. perf failed in runs 3, 4, 5: one P/X press of 188 ms (run 3 only, 159 ms outside the measured parts, not seen again in 3 runs with the finer breakdown: the decision transaction is 7–13 ms on Windows, no WAL checkpoint) and long-session GC pauses of 147 / 115 ms (runs 4, 5); run 6 passed (worst GC 10.7 ms) |
| B3 | Windows manual validation on the owner's laptop (section 3) | blocked | needs the owner's PC; nothing in this container runs a real Windows GUI |
| B4 | Version for the beta (`app/__init__.py` still says 2.2.1): a pre-release suffix (e.g. 2.3.0b1) so the build is published as a pre-release | pending | at release time, with the owner's command |
| B5 | Beta release notes: the v7 session upgrade, the `.v5.bak` / `.v6.bak` copy, what 2.2.1 shows for an upgraded folder, how to go back (section 2, K1) | pending | `packaging/notes/RELEASE_NOTES.md` at release time |
| B6 | Packaged build self-test with the network blocked (`scripts/build_windows.ps1`, run by the build job) | pending | runs with the release build only |

## 2. Known issues (not blockers unless the owner decides otherwise)

| # | Issue | Impact | Mitigation / next step |
|---|---|---|---|
| K1 | A folder opened by this beta is upgraded to session schema v7. KiraPick 2.2.1 then refuses it with its generic "Lỗi không mong muốn … SchemaTooNewError … update the app" box (English text; 2.2.1 cannot be changed). Checked with the real 2.2.1 code: refused, file unchanged byte for byte. | Going back to 2.2.1 loses that folder's remembered choices in 2.2.1 only | Before the upgrade the beta keeps `project.snorlu.db.v5.bak` in the session folder. To go back: close KiraPick, in the session folder delete `project.snorlu.db`, `-wal`, `-shm`, rename the `.v5.bak` to `project.snorlu.db` (changes made in the beta are lost). Release notes must say this. |
| K2 | **Target missed on Windows VMs:** a full GUI-thread GC run in a 10,000-photo long session took 74, 147, 115 ms (CI runs 1, 4, 5 of this task; 12 and 10.7 ms in runs 3 and 6; target 100 ms) | A pause of ~0.1 s now and then while culling a very large session | RV14-03: no `gc.freeze()` in the app without the owner-PC numbers and a decision. Evidence so far: the test-only experiment (`gc.collect(); gc.freeze()` once the session is open) in CI run 6: worst full-session GC 0.11 ms vs 10.7 ms without in the same run (75–147 ms in earlier runs); the cost of that one `gc.collect()` at open and the memory kept by frozen cycles are not measured yet. Owner-PC numbers: the app's `GUI-thread GC: … worst … ms` log line. Decision needed before the beta |
| K3 | Performance numbers come from a Linux VM and a GitHub Windows VM, not the owner's laptop; the AI ran on CPU here (no GPU in the container) | The real laptop may differ (faster CPU/GPU, slower disk?) | Section 3 step 8 |
| K4 | A third-of-screen Snap at 150 % (426 px) is below the 560 px minimum window: Windows shows the window 560 px wide, overlapping the next slot | Cosmetic | Accepted (TINY layout); minimum chosen in Task 12 |
| K5 | Closing or switching folders during an export stops it after the current file (Task 11); the user is now asked first. Exporting again into the same folder copies only what is missing | — | Tested with 34 real RAW files (Task 15) |
| K6 | No real camera JPEG folder from the owner: JPEG numbers use the full-size JPEGs embedded in RAW samples | Unknown for very large JPEGs | Optional: a JPEG shoot in step 8 |
| K7 | Disk full: opening a folder explains it; a failed HD thumbnail leaves no file and keeps the small thumbnail; a full disk DURING an import or the AI analysis was not tested | Import / analysis would report the error and stop | Accept for the beta; test when a full-disk VM is available |
| K8 | `test_real_raw_*`, RV2-04 pair test and RAW HD numbers skip in CI (RAW samples are git-ignored, some are not redistributable) | Covered on Linux only | — |

Not an issue (checked on the real `windows` platform): the detail tabs need 349 px with full titles in Segoe UI
(368 px panel in WIDE), so full titles show; Qt's offscreen platform on Windows has no Windows fonts ("Sans Serif"
fallback, text ~1.7–2× wider), so font-dependent tests skip there and run on the real platform.

## 3. Windows manual validation (owner, in Vietnamese)

Ghi kết quả từng bước (Đạt / Lỗi + ảnh chụp màn hình nếu lỗi). Không cần gửi ảnh chụp của bạn, chỉ cần màn hình app.

1. **Cài đặt:** gỡ thì không cần; cài bản beta đè lên. Mở app → mở một thư mục đã dùng ở 2.2.1 → lựa chọn Chọn/Loại, sao, ❤ vẫn còn. Trong `%LOCALAPPDATA%\KiraPick\sessions\` (dán vào thanh địa chỉ của File Explorer), thư mục phiên của buổi đó có file `project.snorlu.db.v5.bak`.
2. **Snap:** kéo cửa sổ vào nửa trái, nửa phải, 1/4 góc, nửa trên (nếu màn hình cho phép), toàn màn hình. Mỗi lần: không nút nào bị cắt chữ, không thanh cuộn ngang, bảng chi tiết/ngăn bên trái mở được (nút ☰ và Tab).
3. **DPI:** Settings → Display → Scale 100 %, 125 %, 150 % (và 200 % nếu có màn 4K / màn ngoài). Đổi khi app đang mở; kéo app sang màn hình khác tỉ lệ (nếu có). Ảnh nhỏ nét, chữ không bị cắt.
4. **Phím:** P / K chọn, X loại, Tab ẩn/hiện chi tiết, Escape, E phóng mắt, xoay xem; gõ tên file vào ô tìm kiếm thì P/X không chọn ảnh.
5. **RAW + JPEG:** một thư mục chụp RAW+JPEG → mỗi cặp là 1 ô; Chọn → Xuất → thư mục xuất có cả .NEF và .JPG, dung lượng đúng như thanh dưới báo; ảnh gốc không đổi (ngày sửa file giữ nguyên).
6. **Đóng khi đang chạy:** bấm ✕ khi đang nhập ảnh; khi đang 📊 phân tích AI (GPU); khi đang xuất nhiều ảnh (phải hỏi "Dừng xuất và thoát?"). App đóng trong vài giây hoặc ghi "Đang đợi … dừng hẳn", không bao giờ treo/văng.
7. **Đổi thư mục khi đang chạy:** như bước 6 nhưng mở thư mục khác.
8. **Tốc độ:** một buổi chụp lớn (≥ 1.000 ảnh): mở, cuộn nhanh, kéo thanh cỡ ảnh lớn nhất, P/X liên tục 2–3 phút, chạy 📊 phân tích AI rồi cuộn trong lúc chạy. Ghi lại chỗ nào thấy giật. Thoát app rồi gửi dòng `GUI-thread GC` cuối cùng trong `kirapick.log`.
9. **Ổ đầy (không bắt buộc):** USB gần đầy làm nơi xuất → app báo không đủ chỗ trước khi chép.
