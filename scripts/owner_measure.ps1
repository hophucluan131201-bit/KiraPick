<#
Đo thời gian nhập ảnh của KiraPick 3.0.0, Beta đã thử (d45548b) và Beta đã sửa trên CHÍNH máy và thư mục ảnh của bạn,
và chuẩn bị bản Beta chạy từ mã nguồn cho buổi thử phân loại Media (REG-2). Không cần bộ cài mới.

    powershell -ExecutionPolicy Bypass -File owner_measure.ps1 -Buoc chuan-bi  -Anh "D:\Ảnh\Sự kiện bị chậm"
    powershell -ExecutionPolicy Bypass -File owner_measure.ps1 -Buoc do-lanh   -Ban 3.0.0   (ngay sau khi khởi động lại máy)
    powershell -ExecutionPolicy Bypass -File owner_measure.ps1 -Buoc do-lanh   -Ban beta    (ngay sau khi khởi động lại máy)
    powershell -ExecutionPolicy Bypass -File owner_measure.ps1 -Buoc do-am
    powershell -ExecutionPolicy Bypass -File owner_measure.ps1 -Buoc do-phan-tich
    powershell -ExecutionPolicy Bypass -File owner_measure.ps1 -Buoc tong-hop

Thư mục ảnh chỉ được ĐỌC. Mỗi lần đo dùng một thư mục tạm riêng cho phiên làm việc, cài đặt, dữ liệu học và nhật ký:
dữ liệu KiraPick thật của bạn (%LOCALAPPDATA%\KiraPick) không bị đọc hay ghi. Kết quả chỉ có con số (số ảnh theo đuôi
file, số cặp, giây), không có tên ảnh hay đường dẫn. Mọi thứ nằm trong thư mục -Work (mặc định %USERPROFILE%\KiraPick-Do).
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet("chuan-bi", "do-lanh", "do-am", "do-phan-tich", "tong-hop")][string]$Buoc,
    [string]$Anh = "",
    [ValidateSet("3.0.0", "beta", "da-thu")][string]$Ban = "beta",
    [string]$Work = (Join-Path $env:USERPROFILE "KiraPick-Do")
)
$ErrorActionPreference = "Stop"
$Repo = "hophucluan131201-bit/KiraPick"
$Refs = [ordered]@{
    "3.0.0"  = "e2fec9d769d8eb26f9772cd5f5bd0bf04adab4a2"   # tag v3.0.0
    "da-thu" = "d45548bb35b0dedd3e37fac5c55bf259ee9eb5a6"   # Beta đã thử (3.0.1b1)
    "beta"   = "56278d585f65d890b75cca0d762b82ae0cda2126"   # Beta đã sửa (REG-2)
}
$Src = Join-Path $Work "src"
$Out = Join-Path $Work "ket-qua"
$Py = Join-Path $Work "venv\Scripts\python.exe"
$Conf = Join-Path $Work "cau-hinh.json"

function Say([string]$text) { Write-Host $text -ForegroundColor Cyan }
function Root([string]$ban) { return (Join-Path $Src $ban) }

function Load-Conf {
    if (-not (Test-Path $Conf)) { throw "Chưa chạy bước chuan-bi (không thấy $Conf)." }
    return Get-Content $Conf -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Folder-Snapshot([string]$path) {
    $files = Get-ChildItem -LiteralPath $path -Recurse -File -Force
    $newest = ($files | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
    return [ordered]@{ files = $files.Count; bytes = ($files | Measure-Object -Property Length -Sum).Sum
                       newest_write_utc = if ($newest) { $newest.ToString("o") } else { "" } }
}

function Measure-One([string]$ban, [string]$mode, [string]$cache, [string[]]$extra) {
    $c = Load-Conf
    if (Get-Process -Name KiraPick -ErrorAction SilentlyContinue) { throw "Hãy đóng KiraPick trước khi đo." }
    New-Item -ItemType Directory -Force -Path $Out | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $file = Join-Path $Out "$cache-$ban-$mode-$stamp.json"
    $tool = Join-Path (Root "beta") "scripts\measure_import.py"
    Say "Đo: bản $ban, $mode, cache $cache … (cửa sổ KiraPick tự mở rồi tự đóng; đừng bấm vào nó)"
    $callArgs = @($tool, "run", (Root $ban), $c.anh, $mode, $file, "--reopen") + $extra
    & $Py @callArgs | Out-Null
    if (-not (Test-Path $file)) { throw "Lần đo không ra kết quả: $ban $mode" }
    $j = Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json
    $j | Add-Member -NotePropertyName cache -NotePropertyValue $cache -Force
    $j | Add-Member -NotePropertyName version_label -NotePropertyValue $ban -Force
    ($j | ConvertTo-Json -Depth 6) | Set-Content -Path $file -Encoding UTF8
    Write-Host ("  lưới có ảnh đầu {0} s | đủ ảnh trong lưới {1} s | nhập xong {2} s | mở lại {3} s | {4} cặp RAW+JPEG" -f `
        $j.grid_first_s, $j.grid_all_s, $j.import_done_s, $j.reopen_import_done_s, $j.pairs)
    if ($j.analysis_people_s) { Write-Host ("  phân tích: nhận diện {0} s, chấm ảnh {1} s" -f $j.analysis_people_s, $j.analysis_quality_s) }
    if ($j.analysis_media_s) { Write-Host ("  phân tích sự kiện {0} s" -f $j.analysis_media_s) }
}

switch ($Buoc) {
    "chuan-bi" {
        if (-not $Anh) { throw "Thiếu -Anh ""<thư mục ảnh từng bị chậm>""" }
        $Anh = $Anh.Trim().Trim('"')
        if (-not (Test-Path -LiteralPath $Anh -PathType Container)) { throw "Không thấy thư mục ảnh: $Anh" }
        if (Get-Process -Name KiraPick -ErrorAction SilentlyContinue) { throw "Hãy đóng KiraPick trước." }
        New-Item -ItemType Directory -Force -Path $Src, $Out | Out-Null
        # 1. Python 3.12 (py launcher, the usual install folder, or winget)
        $py312 = $null
        try { $py312 = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null) } catch { }
        $usual = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (-not $py312 -and (Test-Path $usual)) { $py312 = $usual }
        if (-not $py312) {
            Say "Cài Python 3.12 (winget)…"
            winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements
            if (Test-Path $usual) { $py312 = $usual } else { throw "Chưa cài được Python 3.12. Cài từ python.org rồi chạy lại bước này." }
        }
        $py312 = "$py312".Trim()
        Say "Python: $py312"
        # 2. Mã nguồn ba bản (zip từ GitHub, đúng commit)
        foreach ($ban in $Refs.Keys) {
            $dest = Root $ban
            if (Test-Path (Join-Path $dest "app\__init__.py")) { Say "Đã có mã nguồn bản $ban"; continue }
            Say "Tải mã nguồn bản $ban…"
            $zip = Join-Path $Work "$ban.zip"
            Invoke-WebRequest -Uri "https://codeload.github.com/$Repo/zip/$($Refs[$ban])" -OutFile $zip -UseBasicParsing
            $tmp = Join-Path $Work "giai-nen-$ban"
            Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
            Move-Item (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName $dest
            Remove-Item $tmp, $zip -Recurse -Force
        }
        # 3. Thư viện (cùng danh sách cho ba bản: không đổi từ 3.0.0) và mô hình được phép cho bản beta
        if (-not (Test-Path $Py)) { & $py312 -m venv (Join-Path $Work "venv") }
        Say "Cài thư viện (vài phút)…"
        & $Py -m pip install --disable-pip-version-check -q -r (Join-Path (Root "beta") "packaging\requirements-directml.txt") onnx==1.23.2
        Say "Tải các mô hình được phép (chỉ những file danh sách cho phép đã xác minh)…"
        Push-Location (Root "beta")
        & $Py scripts\fetch_models.py --purpose identity,quality,gpu
        & $Py scripts\shrink_models.py --dest models\weights
        Pop-Location
        # 4. Máy, ổ đĩa, thư mục ảnh (chỉ con số)
        $letter = (Get-Item -LiteralPath $Anh).PSDrive.Name
        $disk = [ordered]@{ drive = $letter }
        try {
            $d = Get-Partition -DriveLetter $letter | Get-Disk
            $pd = Get-PhysicalDisk | Where-Object { $_.DeviceId -eq "$($d.Number)" } | Select-Object -First 1
            $disk.bus = "$($d.BusType)"; $disk.media = "$($pd.MediaType)"; $disk.size_gb = [math]::Round($d.Size / 1GB)
        } catch { $disk.bus = "không đọc được (ổ mạng?)" }
        $vol = Get-Volume -DriveLetter $letter -ErrorAction SilentlyContinue
        if ($vol) { $disk.free_gb = [math]::Round($vol.SizeRemaining / 1GB) }
        $defender = $null
        try { $defender = (Get-MpComputerStatus).RealTimeProtectionEnabled } catch { }
        $cfg = [ordered]@{
            anh = $Anh
            refs = $Refs
            machine = [ordered]@{
                cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
                ram_gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
                windows = (Get-CimInstance Win32_OperatingSystem).Caption
                defender_realtime = $defender
                photo_disk = $disk
            }
            folder_before = Folder-Snapshot $Anh
        }
        ($cfg | ConvertTo-Json -Depth 6) | Set-Content -Path $Conf -Encoding UTF8
        Say "Xong bước chuẩn bị. Thư mục ảnh: $($cfg.folder_before.files) file."
        Say "Bước tiếp: KHỞI ĐỘNG LẠI MÁY, rồi chạy: -Buoc do-lanh -Ban 3.0.0"
    }
    "do-lanh" {
        $up = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
        if ($up.TotalMinutes -gt 20) {
            Write-Host "Máy đã bật $([math]::Round($up.TotalMinutes)) phút: ảnh có thể đã nằm trong bộ nhớ đệm. Kết quả được ghi là 'am' (ấm), không phải 'lanh'." -ForegroundColor Yellow
            Measure-One $Ban "personal" "am" @()
        } else {
            Measure-One $Ban "personal" "lanh" @()
        }
        if ($Ban -eq "3.0.0") { Say "Bước tiếp: KHỞI ĐỘNG LẠI MÁY, rồi chạy: -Buoc do-lanh -Ban beta" }
        else { Say "Bước tiếp: -Buoc do-am" }
    }
    "do-am" {
        $order = @(@("3.0.0", "personal"), @("da-thu", "personal"), @("da-thu", "media"), @("beta", "personal"), @("beta", "media"))
        foreach ($round in 1..2) {
            $list = if ($round -eq 1) { $order } else { $order[($order.Count - 1)..0] }  # đảo thứ tự ở vòng 2
            foreach ($x in $list) { Measure-One $x[0] $x[1] "am" @() }
        }
        Say "Bước tiếp: -Buoc do-phan-tich"
    }
    "do-phan-tich" {
        # Chỉ bản beta: bản cũ mở những mô hình không được dùng, kể cả để đo (configs\model-policy.json)
        Measure-One "beta" "personal" "am" @("--analysis", "--gpu")
        Measure-One "beta" "media" "am" @("--analysis", "--gpu")
        Say "Bước tiếp: -Buoc tong-hop"
    }
    "tong-hop" {
        $c = Load-Conf
        $after = Folder-Snapshot $c.anh
        $same = ($after.files -eq $c.folder_before.files) -and ($after.bytes -eq $c.folder_before.bytes) -and `
                ($after.newest_write_utc -eq $c.folder_before.newest_write_utc)
        $rows = Get-ChildItem $Out -Filter *.json | Sort-Object Name | ForEach-Object { Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json }
        $lines = @("KiraPick — đo nhập ảnh trên máy chủ dự án ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))",
                   "Máy: $($c.machine.cpu) | $($c.machine.ram_gb) GB | $($c.machine.windows) | Defender realtime: $($c.machine.defender_realtime)",
                   "Ổ chứa ảnh: $($c.machine.photo_disk | ConvertTo-Json -Compress)",
                   "Thư mục ảnh: $($c.folder_before.files) file, $([math]::Round($c.folder_before.bytes / 1MB)) MB; không đổi sau khi đo: $same",
                   "", "bản | chế độ | cache | file | cặp RAW+JPEG | lưới có ảnh đầu (s) | dùng được khi đang nhập | đủ ảnh (s) | nhập xong (s) | mở lại (s) | phân tích (s)")
        foreach ($j in $rows) {
            $an = @($j.analysis_people_s, $j.analysis_quality_s, $j.analysis_media_s) | Where-Object { $_ }
            $lines += "$($j.version_label) | $($j.mode) | $($j.cache) | $($j.files) | $($j.pairs) | $($j.grid_first_s) | $($j.usable_during_import) | $($j.grid_all_s) | $($j.import_done_s) | $($j.reopen_import_done_s) | $($an -join ' + ')"
        }
        if ($rows.Count) { $lines += "", "Loại file: $($rows[0].file_types | ConvertTo-Json -Compress)" }
        $txt = Join-Path $Out "ket-qua.txt"
        $lines | Set-Content -Path $txt -Encoding UTF8
        $lines | ForEach-Object { Write-Host $_ }
        $zip = Join-Path ([Environment]::GetFolderPath("Desktop")) "KiraPick-do-nhap.zip"
        Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $zip -Force
        Say "Gửi file này: $zip (chỉ có con số, không có ảnh hay tên ảnh)."
    }
}
