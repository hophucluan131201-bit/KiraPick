<#
KiraPick — phép thử trên máy chủ dự án (REG-3). Không cần bộ cài mới: ba bản chạy từ mã nguồn ở commit cố định.

    -Buoc chuan-bi  -Anh "<thư mục ảnh sự kiện thật, có RAW+JPEG>"   tải và kiểm mã nguồn, cài thư viện và mô hình được phép
    -Buoc do-nhanh                     đo nhanh: mỗi bản một lần (lần mở đầu + lần chạy lại)
    -Buoc do-lanh -Ban 3.0.0|beta      đo đầy đủ, ngay sau khi khởi động lại máy (chỉ khi cần xác minh chênh lệch)
    -Buoc do-am                        đo đầy đủ, cache ấm, hai vòng
    -Buoc do-phan-tich                 thời gian phân tích AI, đo riêng (chỉ Beta)
    -Buoc tong-hop                     bảng kết quả + KiraPick-do-nhap.zip trên Desktop
    -Buoc mo-beta                      mở Beta đã sửa trên PROFILE TEST RIÊNG (không đụng dữ liệu KiraPick thật)
    -Buoc dem-ab                       lấy số của phép thử A/B + KiraPick-thu-phan-loai.zip trên Desktop

Thư mục ảnh chỉ được ĐỌC (kiểm trước / sau: unchanged=True). Kết quả chỉ có con số, không có ảnh, tên ảnh hay đường dẫn.
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("chuan-bi", "do-nhanh", "do-lanh", "do-am", "do-phan-tich", "tong-hop", "mo-beta", "dem-ab")]
    [string]$Buoc,
    [string]$Anh = "",
    [ValidateSet("3.0.0", "beta", "da-thu")][string]$Ban = "beta",
    [string]$Work = (Join-Path $env:USERPROFILE "KiraPick-Do")
)
$ErrorActionPreference = "Stop"
$Repo = "hophucluan131201-bit/KiraPick"
# Mã nguồn của từng bản: commit cố định và SHA-256 của vài file trong đó (tải sai bản thì dừng).
$Refs = [ordered]@{
    "3.0.0"  = "e2fec9d769d8eb26f9772cd5f5bd0bf04adab4a2"   # tag v3.0.0
    "da-thu" = "d45548bb35b0dedd3e37fac5c55bf259ee9eb5a6"   # Beta bạn đã thử (3.0.1b1)
    "beta"   = "743b76a09fd5bfe60ba24233ef9b02a3ee423a5e"   # Beta đã sửa: cửa sổ 3.0.0, 🧪 gom ảnh gần trùng, bộ đếm, profile test, in UTF-8
}
$Expect = @{
    "3.0.0"  = @{ "app\main.py" = "29edb81f84e23991b449f7211cded83967e8d6c48d62102f67115f49200e86a0"
                  "app\ui\main_window.py" = "e53178f94e2fdfb6857998a712f375d7b53ac644df84b03f2da2bad241446b4f" }
    "da-thu" = @{ "app\main.py" = "5ed22dbcb3ba54db00bef01e3d1a1be500e58b1f7357d7d6916afa8ef38f22f3"
                  "app\ui\media_window.py" = "29983792007e521eef1a19208664c7f0af78cde42bf71abc51d5abbf90813519" }
    "beta"   = @{ "app\main.py" = "4d7db2755f2e9f68c1212d8e0c925bfe45a728d89f4b796f048afb7b81489cbb"
                  "app\ui\media_event_window.py" = "e160ee1335c73971eff78ce19733e165b0330d744e90b7b9bbc75647dee9a746"
                  "app\media\similar.py" = "8137146080ca966b20d5fdbc5bd495edc7cb4558f297290a6597e846f945ffd9"
                  "app\media\trial.py" = "8da0eaf9880699e50a6bbdb1b38542b1c466f4ff88f578d156bd84af61fb755f"
                  "app\branding.py" = "415798f79c091a15a90f93a09abe77bece0b1fede271ec6337cd21db1c7ab369"
                  "scripts\measure_import.py" = "9c06de2076797b0c4073d31a955c562781a0b49d9b3b9db46109624e7c2d5c36" }
}
$Src = Join-Path $Work "src"
$Out = Join-Path $Work "ket-qua"
$Py = Join-Path $Work "venv\Scripts\python.exe"
$Conf = Join-Path $Work "cau-hinh.json"
$TestProfile = Join-Path $Work "profile-thu"        # profile test riêng cho Beta chạy từ mã nguồn
$EventNames = @("RANH GIOI", "THU A", "THU B")   # tên sự kiện của phép thử A/B, gõ đúng như vậy

function Say([string]$text) { Write-Host $text -ForegroundColor Cyan }
function Stop-Here([string]$text) { Write-Host $text -ForegroundColor Red; exit 1 }
function Root([string]$ban) { return (Join-Path $Src $ban) }

function Source-Ok([string]$ban) {
    foreach ($f in $Expect[$ban].Keys) {
        $p = Join-Path (Root $ban) $f
        if (-not (Test-Path $p)) { return $false }
        if ((Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne $Expect[$ban][$f]) { return $false }
    }
    return $true
}

function Require-Source([string]$ban) {
    if (-not (Source-Ok $ban)) { Stop-Here "SAI MÃ NGUỒN bản $ban (không khớp SHA-256 mong đợi). Dừng lại, chụp màn hình gửi lại." }
}

function Load-Conf {
    if (-not (Test-Path $Conf)) { Stop-Here "Chưa chạy bước chuan-bi (không thấy $Conf)." }
    return Get-Content $Conf -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Folder-Snapshot([string]$path) {
    $files = Get-ChildItem -LiteralPath $path -Recurse -File -Force
    $newest = ($files | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
    return [ordered]@{ files = $files.Count; bytes = ($files | Measure-Object -Property Length -Sum).Sum
                       newest_write_utc = if ($newest) { $newest.ToString("o") } else { "" } }
}

function Uptime-Minutes { return [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes) }

function Measure-One([string]$ban, [string]$mode, [string]$cache, [string[]]$extra, [string]$kind) {
    $c = Load-Conf
    Require-Source $ban
    Require-Source "beta"   # the measuring tool comes from the Beta source
    if (Get-Process -Name KiraPick -ErrorAction SilentlyContinue) { Stop-Here "Hãy đóng KiraPick trước khi đo." }
    New-Item -ItemType Directory -Force -Path $Out | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $file = Join-Path $Out "$kind-$cache-$ban-$mode-$stamp.json"
    $tool = Join-Path (Root "beta") "scripts\measure_import.py"
    Say "Đo: bản $ban, $mode, cache $cache … (cửa sổ KiraPick tự mở rồi tự đóng; đừng bấm vào nó)"
    $callArgs = @($tool, "run", (Root $ban), $c.anh, $mode, $file, "--reopen") + $extra
    & $Py @callArgs | Out-Null
    if (-not (Test-Path $file)) { Stop-Here "Lần đo không ra kết quả: $ban $mode" }
    $j = Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($kv in @(@("cache", $cache), @("version_label", $ban), @("kind", $kind), @("uptime_min", (Uptime-Minutes)),
                      @("commit", $Refs[$ban]))) {
        $j | Add-Member -NotePropertyName $kv[0] -NotePropertyValue $kv[1] -Force
    }
    ($j | ConvertTo-Json -Depth 6) | Set-Content -Path $file -Encoding UTF8
    Write-Host ("  ảnh đầu {0} s | mở/đánh dấu được {1} s | nhập xong {2} s | {3} thẻ ảnh sau ghép, {4} cặp RAW+JPEG | chạy lại: xong {5} s" -f `
        $j.grid_first_s, $j.usable_s, $j.import_done_s, $j.rows, $j.pairs, $j.reopen_import_done_s)
}

function Run-Python-App([string[]]$appArgs) {
    Require-Source "beta"
    $env:KIRAPICK_PROFILE_DIR = $TestProfile
    Push-Location (Root "beta")
    try { & $Py -m app @appArgs } finally { Pop-Location }
}

switch ($Buoc) {
    "chuan-bi" {
        if (-not $Anh) { Stop-Here "Thiếu -Anh ""<thư mục ảnh sự kiện thật có RAW+JPEG>""" }
        $Anh = $Anh.Trim().Trim('"')
        if (-not (Test-Path -LiteralPath $Anh -PathType Container)) { Stop-Here "Không thấy thư mục ảnh: $Anh" }
        if (Get-Process -Name KiraPick -ErrorAction SilentlyContinue) { Stop-Here "Hãy đóng KiraPick trước." }
        New-Item -ItemType Directory -Force -Path $Src, $Out | Out-Null
        # 1. Python 3.12 (py launcher, thư mục cài thường gặp, hoặc winget)
        $py312 = $null
        try { $py312 = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null) } catch { }
        $usual = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (-not $py312 -and (Test-Path $usual)) { $py312 = $usual }
        if (-not $py312) {
            Say "Cài Python 3.12 (winget)…"
            winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements
            if (Test-Path $usual) { $py312 = $usual } else { Stop-Here "Chưa cài được Python 3.12. Cài từ python.org rồi chạy lại bước này." }
        }
        $py312 = "$py312".Trim()
        Say "Python: $py312"
        # 2. Mã nguồn ba bản: tải đúng commit, kiểm SHA-256; bản cũ sai mã thì đổi tên (không xoá) rồi tải lại
        foreach ($ban in $Refs.Keys) {
            $dest = Root $ban
            if (Test-Path $dest) {
                if (Source-Ok $ban) { Say "Mã nguồn bản $($ban): đúng ($($Refs[$ban].Substring(0, 7)))"; continue }
                $old = "$dest.cu-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
                Move-Item $dest $old
                Say "Mã nguồn bản $ban cũ không khớp: đã đổi tên thành $old, tải lại."
            }
            Say "Tải mã nguồn bản $ban ($($Refs[$ban].Substring(0, 7)))…"
            $zip = Join-Path $Work "$ban.zip"
            Invoke-WebRequest -Uri "https://codeload.github.com/$Repo/zip/$($Refs[$ban])" -OutFile $zip -UseBasicParsing
            $tmp = Join-Path $Work "giai-nen-$ban"
            Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
            Move-Item (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName $dest
            Remove-Item $tmp, $zip -Recurse -Force
            Require-Source $ban
            Say "  SHA-256 khớp."
        }
        # 3. Thư viện (cùng danh sách cho ba bản: không đổi từ 3.0.0) và mô hình được phép cho bản Beta
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
        Say "Xong bước chuẩn bị. Thư mục ảnh: $($cfg.folder_before.files) file. Ba bản mã nguồn đều khớp SHA-256."
    }
    "do-nhanh" {
        # Mỗi bản một lần, nối tiếp. Lần đo đầu tiên sau khi khởi động lại máy (< 20 phút) là cache lạnh, các lần sau ấm.
        $first = $true
        foreach ($x in @(@("3.0.0", "personal"), @("da-thu", "personal"), @("beta", "personal"), @("da-thu", "media"), @("beta", "media"))) {
            $cache = if ($first -and (Uptime-Minutes) -lt 20) { "lanh" } else { "am" }
            Measure-One $x[0] $x[1] $cache @() "nhanh"
            $first = $false
        }
        Say "Xong đo nhanh. Bước tiếp: -Buoc tong-hop"
    }
    "do-lanh" {
        if ((Uptime-Minutes) -gt 20) {
            Write-Host "Máy đã bật $(Uptime-Minutes) phút: kết quả được ghi là 'am' (ấm), không phải 'lanh'." -ForegroundColor Yellow
            Measure-One $Ban "personal" "am" @() "day-du"
        } else {
            Measure-One $Ban "personal" "lanh" @() "day-du"
        }
    }
    "do-am" {
        $order = @(@("3.0.0", "personal"), @("da-thu", "personal"), @("da-thu", "media"), @("beta", "personal"), @("beta", "media"))
        foreach ($round in 1..2) {
            $list = if ($round -eq 1) { $order } else { $order[($order.Count - 1)..0] }  # đảo thứ tự ở vòng 2
            foreach ($x in $list) { Measure-One $x[0] $x[1] "am" @() "day-du" }
        }
    }
    "do-phan-tich" {
        # Chỉ bản Beta: bản cũ mở những mô hình không được dùng, kể cả để đo (configs\model-policy.json)
        Measure-One "beta" "personal" "am" @("--analysis", "--gpu") "phan-tich"
        Measure-One "beta" "media" "am" @("--analysis", "--gpu") "phan-tich"
    }
    "tong-hop" {
        $c = Load-Conf
        $after = Folder-Snapshot $c.anh
        $unchanged = ($after.files -eq $c.folder_before.files) -and ($after.bytes -eq $c.folder_before.bytes) -and `
                     ($after.newest_write_utc -eq $c.folder_before.newest_write_utc)
        $rows = Get-ChildItem $Out -Filter *.json | Sort-Object Name | ForEach-Object { Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json }
        $lines = @("KiraPick — đo nhập ảnh trên máy chủ dự án ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))",
                   "Commit: 3.0.0 $($Refs['3.0.0'].Substring(0,7)) | đã thử $($Refs['da-thu'].Substring(0,7)) | Beta $($Refs['beta'].Substring(0,7))",
                   "Máy: $($c.machine.cpu) | $($c.machine.ram_gb) GB | $($c.machine.windows) | Defender realtime: $($c.machine.defender_realtime)",
                   "Ổ chứa ảnh: $($c.machine.photo_disk | ConvertTo-Json -Compress)",
                   "Thư mục ảnh: $($c.folder_before.files) file, $([math]::Round($c.folder_before.bytes / 1MB)) MB",
                   "unchanged=$unchanged   (True = số file, tổng dung lượng và giờ sửa mới nhất trong thư mục ảnh giống hệt trước khi đo; phải là True)",
                   "", "phép đo | bản | chế độ | cache | lần | file | thẻ ảnh sau ghép | cặp RAW+JPEG | ảnh đầu (s) | mở/đánh dấu được (s) | nhập xong (s) | phân tích (s)")
        foreach ($j in $rows) {
            $an = @($j.analysis_people_s, $j.analysis_quality_s, $j.analysis_media_s) | Where-Object { $_ }
            $lines += "$($j.kind) | $($j.version_label) | $($j.mode) | $($j.cache) | mở đầu | $($j.files) | $($j.rows) | $($j.pairs) | $($j.grid_first_s) | $($j.usable_s) | $($j.import_done_s) | $($an -join ' + ')"
            $lines += "$($j.kind) | $($j.version_label) | $($j.mode) | $($j.cache) | chạy lại | $($j.files) | $($j.reopen_rows) | $($j.pairs) | $($j.reopen_grid_first_s) | $($j.reopen_usable_s) | $($j.reopen_import_done_s) |"
        }
        if ($rows.Count) { $lines += "", "Loại file: $($rows[0].file_types | ConvertTo-Json -Compress)" }
        $txt = Join-Path $Out "ket-qua.txt"
        $lines | Set-Content -Path $txt -Encoding UTF8
        $lines | ForEach-Object { Write-Host $_ }
        $zip = Join-Path ([Environment]::GetFolderPath("Desktop")) "KiraPick-do-nhap.zip"
        Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $zip -Force
        if (-not $unchanged) { Stop-Here "unchanged=False: thư mục ảnh đã đổi trong lúc đo. Đừng dùng thư mục đó nữa, báo lại ngay." }
        Say "Gửi file này: $zip (chỉ có con số, không có ảnh hay tên ảnh)."
    }
    "mo-beta" {
        Say "Mở Beta đã sửa ($($Refs['beta'].Substring(0,7))) trên profile test: $TestProfile"
        Say "Dữ liệu KiraPick thật của bạn không bị đọc hay ghi. Đóng cửa sổ KiraPick là xong."
        Run-Python-App @()
    }
    "dem-ab" {
        $ab = Join-Path $Work "thu-ab"
        New-Item -ItemType Directory -Force -Path $ab | Out-Null
        Run-Python-App @("--media-counts", "THU A", "--ranh-gioi", "RANH GIOI", "--out", (Join-Path $ab "dem-A.json")) | Out-Null
        Run-Python-App @("--media-counts", "THU B", "--ranh-gioi", "RANH GIOI", "--out", (Join-Path $ab "dem-B.json")) | Out-Null
        foreach ($f in "dem-A.json", "dem-B.json") { if (-not (Test-Path (Join-Path $ab $f))) { Stop-Here "Thiếu $($f): kiểm tên ba sự kiện $($EventNames -join ', ')" } }
        $zip = Join-Path ([Environment]::GetFolderPath("Desktop")) "KiraPick-thu-phan-loai.zip"
        Compress-Archive -Path (Join-Path $ab "*") -DestinationPath $zip -Force
        Say "Gửi file này cùng bảng ghi tay: $zip (chỉ có con số)."
    }
}
