<#
Sao lưu (và khi cần, khôi phục) dữ liệu KiraPick trước khi thử bản nội bộ.

    Sao lưu:  powershell -ExecutionPolicy Bypass -File .\owner_backup.ps1 -Destination D:\KiraPick-SaoLuu
    Khôi phục: powershell -ExecutionPolicy Bypass -File .\owner_backup.ps1 -Restore D:\KiraPick-SaoLuu\20261031-153000

Sao lưu: %LOCALAPPDATA%\KiraPick (phiên làm việc của mọi thư mục ảnh, bộ nhớ học, nhật ký) và các cài đặt
(HKCU\Software\KiraPick) vào một thư mục MỚI <Destination>\<ngày-giờ> (thêm -2, -3… nếu tên đã có); so SHA-256 từng file sau khi chép; không bao
giờ ghi đè một bản sao lưu đã có. Ảnh gốc của bạn không nằm ở đây và không bị đụng tới.
Khôi phục: KHÔNG xoá gì — thư mục dữ liệu hiện tại được đổi tên thành KiraPick.truoc-khoi-phuc-<ngày-giờ>, rồi bản sao
lưu được chép trở lại và kiểm tra SHA-256; cài đặt được nhập lại từ file .reg của bản sao lưu.
Cả hai việc chỉ chạy khi không có KiraPick nào đang mở.
#>
param([string]$Destination = "", [string]$Restore = "")
$ErrorActionPreference = "Stop"
$data = Join-Path $env:LOCALAPPDATA "KiraPick"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (Get-Process -Name KiraPick -ErrorAction SilentlyContinue) {
    throw "KiraPick đang chạy. Đóng mọi cửa sổ KiraPick (cả bản 2.2.1 và bản thử) rồi chạy lại."
}

function Hashes([string]$root) {
    $map = @{}
    if (Test-Path $root) {
        Get-ChildItem -Recurse -File $root | ForEach-Object {
            $map[$_.FullName.Substring($root.Length).TrimStart("\")] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
        }
    }
    return $map
}

function Compare-Trees([string]$a, [string]$b) {
    $ha, $hb = (Hashes $a), (Hashes $b)
    $bad = @($ha.Keys | Where-Object { $hb[$_] -ne $ha[$_] })
    if ($bad.Count -or $ha.Count -ne $hb.Count) {
        throw "Bản chép KHÔNG khớp ($($bad.Count) file khác, $($ha.Count) / $($hb.Count) file). Đừng tiếp tục; giữ nguyên mọi thứ và báo lại."
    }
    return $ha.Count
}

if ($Restore) {
    $backup = Join-Path $Restore "KiraPick"
    if (-not (Test-Path $backup)) { throw "Không thấy $backup — hãy chỉ đúng thư mục <ngày-giờ> của bản sao lưu." }
    if (Test-Path $data) {
        $aside = "$data.truoc-khoi-phuc-$stamp"
        Rename-Item $data $aside
        Write-Host "Dữ liệu hiện tại được giữ lại ở: $aside (không xoá)"
    }
    Copy-Item $backup $data -Recurse
    $n = Compare-Trees $backup $data
    $reg = Join-Path $Restore "kirapick-settings.reg"
    if (Test-Path $reg) { reg import $reg | Out-Null; Write-Host "Đã nhập lại cài đặt từ $reg" }
    Write-Host "Đã khôi phục $n file vào $data và kiểm tra SHA-256: khớp." -ForegroundColor Green
    exit 0
}

if (-not $Destination) { throw "Cần -Destination, ví dụ D:\KiraPick-SaoLuu (một ổ/thư mục ngoài %LOCALAPPDATA%)." }
if ($Destination.StartsWith($env:LOCALAPPDATA, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Hãy chọn nơi sao lưu ngoài %LOCALAPPDATA% (ví dụ D:\KiraPick-SaoLuu)."
}
$target = Join-Path $Destination $stamp
for ($i = 2; Test-Path $target; $i++) { $target = Join-Path $Destination "$stamp-$i" }  # never overwrite a backup
New-Item -ItemType Directory -Path $target | Out-Null
if (Test-Path $data) {
    Copy-Item $data (Join-Path $target "KiraPick") -Recurse
    $n = Compare-Trees $data (Join-Path $target "KiraPick")
} else {
    $n = 0
    Write-Host "Chưa có $data (KiraPick chưa từng chạy trên máy này)."
}
$settings = "không có (KiraPick chưa lưu cài đặt nào)"
if (Test-Path "HKCU:\Software\KiraPick") {
    reg export "HKCU\Software\KiraPick" (Join-Path $target "kirapick-settings.reg") | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Không xuất được cài đặt HKCU\Software\KiraPick" }
    $settings = "kirapick-settings.reg"
}
$sessions = @(Get-ChildItem (Join-Path $target "KiraPick\sessions") -Directory -ErrorAction SilentlyContinue).Count
@(
    "Sao lưu KiraPick lúc $stamp",
    "Từ: $data",
    "Số file: $n (SHA-256 đã so khớp)",
    "Số phiên thư mục ảnh: $sessions",
    "Cài đặt: $settings"
) | Set-Content (Join-Path $target "DOC_TOI.txt") -Encoding UTF8
Write-Host ""
Write-Host "Đã sao lưu $n file ($sessions phiên thư mục ảnh) và kiểm tra SHA-256: khớp." -ForegroundColor Green
Write-Host "Bản sao lưu nằm ở: $target" -ForegroundColor Green
Write-Host "Ghi lại đường dẫn này. Khi cần khôi phục: .\owner_backup.ps1 -Restore `"$target`""
