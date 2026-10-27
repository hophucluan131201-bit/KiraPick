<#
Tạo (hoặc làm mới) biểu tượng KiraPick trên Desktop cho bản chạy từ mã nguồn (dùng GPU).

    powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcut.ps1

Xoá biểu tượng cũ "Snorlu AI Culling" trên Desktop, nhưng CHỈ khi nó trỏ tới chính thư mục
dự án này. Không đụng tới ảnh hay dữ liệu nào khác.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    Write-Host "Chưa cài môi trường. Hãy chạy trước: powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1" -ForegroundColor Yellow
    exit 1
}
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell

$old = Join-Path $desktop 'Snorlu AI Culling.lnk'
if (Test-Path $old) {
    $target = $shell.CreateShortcut($old).TargetPath
    if ($target -and ($target -like "$root*")) {
        Remove-Item $old
        Write-Host "Đã xoá biểu tượng cũ 'Snorlu AI Culling'."
    }
}

$lnk = $shell.CreateShortcut((Join-Path $desktop 'KiraPick.lnk'))
$lnk.TargetPath = $pythonw
$lnk.Arguments = '-m app'
$lnk.WorkingDirectory = $root
$lnk.Description = 'KiraPick - lọc ảnh bằng AI, chạy offline'
$lnk.IconLocation = (Join-Path $root 'packaging\kirapick.ico') + ',0'
$lnk.Save()
Write-Host "Đã tạo biểu tượng 'KiraPick' trên Desktop." -ForegroundColor Green
