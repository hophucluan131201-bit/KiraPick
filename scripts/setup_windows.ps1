# Snorlu AI Culling - cài đặt môi trường phát triển trên Windows.
# Chạy trong thư mục dự án (KHÔNG cần quyền Administrator):
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
# Script chỉ tạo thư mục .venv trong dự án; không sửa cài đặt hệ thống.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
Write-Host "Thư mục dự án: $root"

function Test-Python([string]$exe, [string[]]$pre) {
    try {
        $out = & $exe @pre -c "import sys; v=sys.version_info; print(f'{v[0]}.{v[1]}'); sys.exit(0 if (3,11) <= v[:2] < (3,15) else 3)" 2>$null
        if ($LASTEXITCODE -eq 0) { return $out }
    } catch { }
    return $null
}

# 1) Tìm Python 3.11-3.14 (ưu tiên 3.12, 3.13, 3.14).
$pyExe = $null; $pyArgs = @(); $pyVer = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in @('3.12', '3.13', '3.14', '3.11')) {
        $found = Test-Python 'py' @("-$v")
        if ($found) { $pyExe = 'py'; $pyArgs = @("-$v"); $pyVer = $found; break }
    }
}
if (-not $pyExe) {
    foreach ($cand in @('python', 'python3')) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            $found = Test-Python $cand @()
            if ($found) { $pyExe = $cand; $pyVer = $found; break }
        }
    }
}
if (-not $pyExe) {
    Write-Host ""
    Write-Host "KHÔNG tìm thấy Python 3.11-3.14." -ForegroundColor Red
    Write-Host "Các bản Python đang có trên máy:"
    if (Get-Command py -ErrorAction SilentlyContinue) { py --list } else { Write-Host "  (không có lệnh 'py')" }
    Write-Host "Cài Python 3.12 bằng lệnh sau, rồi MỞ LẠI PowerShell và chạy lại script này:"
    Write-Host "  winget install --id Python.Python.3.12 -e" -ForegroundColor Yellow
    exit 1
}
Write-Host "Dùng Python $pyVer ($pyExe $pyArgs)" -ForegroundColor Green

# 2) Tạo môi trường ảo .venv (chỉ trong thư mục dự án).
$venvPy = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "Tạo .venv ..."
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Tạo .venv thất bại." -ForegroundColor Red; exit 1 }
}

# 3) Cài thư viện (cần Internet lúc cài; ứng dụng chạy offline sau này).
Write-Host "Cài thư viện (vài phút lần đầu) ..."
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { Write-Host "Cài thư viện thất bại - chụp màn hình lỗi phía trên gửi lại." -ForegroundColor Red; exit 1 }

# 4) Chạy kiểm thử.
Write-Host "Chạy kiểm thử ..."
& $venvPy -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "Có test LỖI - chụp màn hình phần cuối gửi lại." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "XONG." -ForegroundColor Green

# 5) Lối tắt trên Desktop (chỉ khi bạn đồng ý).
$answer = Read-Host "Tạo biểu tượng 'Snorlu AI Culling' trên Desktop? (Y/N)"
if ($answer -match '^[YyCc]') {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut((Join-Path $desktop 'Snorlu AI Culling.lnk'))
    $lnk.TargetPath = (Join-Path $root '.venv\Scripts\pythonw.exe')
    $lnk.Arguments = '-m app'
    $lnk.WorkingDirectory = $root
    $lnk.Description = 'Snorlu AI Culling'
    $lnk.Save()
    Write-Host "Đã tạo biểu tượng trên Desktop." -ForegroundColor Green
}
Write-Host ""
Write-Host "Mở ứng dụng: bấm đúp Snorlu.cmd trong thư mục dự án (hoặc biểu tượng trên Desktop)."
