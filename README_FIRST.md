# Khởi chạy Snorlu AI Photo Culling bằng Claude Code

Gói này là **bộ lệnh/brief giao cho Claude Code**, không phải ứng dụng AI đã hoàn thiện. Claude Code cần Internet khi phát triển; **ứng dụng sau khi tạo xong mới có yêu cầu hoàn toàn offline**.

## Cách chạy (Windows 10/11)

1. Nếu chưa cài Claude Code, mở PowerShell và chạy:

   `winget install Anthropic.ClaudeCode`

2. Mở lại PowerShell, kiểm tra: `claude --version`. Đăng nhập khi Claude Code yêu cầu.
3. Giải nén **toàn bộ** gói vào thư mục làm việc của dự án, ví dụ `D:\Snorlu-AI-Culling` hoặc `C:\Users\<user>\Documents\Snorlu-AI-Culling`.
4. Vào thư mục bằng PowerShell: `cd 'D:\Snorlu-AI-Culling'` (thay bằng đường dẫn bạn dùng).
5. Chạy một lệnh:

   `claude "Read CLAUDE.md, BUILD_TASK.md, docs/TECHNICAL_SPEC_v1.1.md and configs/rtx2080_maxq_8gb.yaml. Implement this app in milestones, write executable code now starting with M0 and M1, run tests, and update docs/IMPLEMENTATION_STATUS.md. Continue with later milestones as feasible. Do not fake model outputs or claim incomplete features done."`

   HOẶC chạy file `Start-Claude.ps1` sau khi đã xem nội dung file, bằng PowerShell:
   `& '.\Start-Claude.ps1'`

6. Lúc Claude Code hỏi quyền chạy lệnh hoặc sửa file, đọc và duyệt các thao tác phù hợp. **Không dùng** `--dangerously-skip-permissions`.
7. Khi session kết thúc, dùng `claude -c` để tiếp tục và lấy lệnh trong `NEXT_PROMPTS.md`.

## Nội dung

- `CLAUDE.md`: quy tắc lâu dài cho toàn bộ dự án, tự tải trong phiên Claude Code.
- `BUILD_TASK.md`: bản giao việc chi tiết và phạm vi xây dựng.
- `docs/TECHNICAL_SPEC_v1.1.md`: đặc tả kỹ thuật v1.1 đã thống nhất.
- `configs/rtx2080_maxq_8gb.yaml`: profile GPU/CPU/RAM.
- `scripts/diagnose_hardware.py`: script chẩn đoán (thành phần tùy chọn).
- `NEXT_PROMPTS.md`: câu lệnh tiếp tục, kiểm thử và đóng gói.
- `Start-Claude.ps1`: launcher đọc lệnh và bắt đầu phiên Claude Code ngay trong thư mục dự án.

Lưu ý: cài dependencies, tải các bộ trọng số open-source để phục vụ phát triển có thể cần mạng. Bản phát hành sau cùng không được tải mô hình khi chạy. Một số pretrained weight có điều khoản riêng, phải kiểm tra trước khi đóng gói/phân phối.
