<#
Build the Windows installer of KiraPick (DirectML GPU with CPU fallback, works offline).

    powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 [-Edition directml|cuda|openvino]

Normally GitHub Actions runs this (.github/workflows/build-windows.yml) and publishes the result on
the Releases page; running it by hand is only needed to build locally.
Editions: directml (official, any DirectX 12 card), cuda (beta "a": NVIDIA, CUDA/cuDNN DLLs
included), openvino (beta "b": Intel CPU). Steps: separate build venv per edition
(.venv-build-<edition>, Python 3.12) with the exact versions in
packaging\requirements-<edition>.txt -> verified model weights -> PyInstaller folder
-> offline self-test of the packaged exe (network blocked) -> Inno Setup installer
(if Inno Setup 6 is installed) -> zips with the Vietnamese install guide.
Changes nothing outside the project folder. Needs Internet only to download packages
and model weights (build time, never at app run time).
Output: dist\installer\
#>
param([switch]$NonInteractive, [ValidateSet("directml", "cuda", "openvino")][string]$Edition = "directml")
$ErrorActionPreference = "Stop"
# Python must print Vietnamese text even where the console code page is cp1252 (e.g. CI machines).
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
Set-Location (Split-Path -Parent $PSScriptRoot)
$Root = (Get-Location).Path

function Step([string]$text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }

# Native tools write progress to stderr; Windows PowerShell 5 would turn that into errors.
# Run them with errors not stopping the script and judge success by the exit code only.
function Invoke-Tool([string]$what, [string]$exe, [string[]]$arguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $exe @arguments 2>&1 | ForEach-Object { Write-Host "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { throw "$what thất bại (mã lỗi $code)" }
}

function Test-Python312([string]$exe, [string[]]$pre) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "3.12")
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $old
    }
}

Step "1/6 Python 3.12"
$pyExe = $null
$pyArgs = @()
if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-Python312 "py" @("-3.12"))) {
    $pyExe = "py"; $pyArgs = @("-3.12")
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-Python312 "python" @())) {
    $pyExe = "python"
}
if (-not $pyExe) { throw "Cần Python 3.12: winget install --id Python.Python.3.12 -e" }
Write-Host "Dùng: $pyExe $pyArgs"

Step "2/6 Môi trường build riêng (.venv-build-$Edition)"
$venv = ".venv-build-$Edition"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Invoke-Tool "Tạo $venv" $pyExe ($pyArgs + @("-m", "venv", $venv))
}
$bpy = Join-Path $Root "$venv\Scripts\python.exe"
Invoke-Tool "Cập nhật pip" $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip")
Invoke-Tool "Cài thư viện" $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "packaging\requirements-$Edition.txt")
# The edition and its version ("2.2.0" -> "2.2.0a" CUDA / "2.2.0b" OpenVINO) are written into the app;
# the original files are restored at the end of the build.
$editionFile = "app\edition.py"
$initFile = "app\__init__.py"
$savedEdition = Get-Content $editionFile -Raw -Encoding UTF8
$savedInit = Get-Content $initFile -Raw -Encoding UTF8
$suffix = @{ directml = ""; cuda = "a"; openvino = "b" }[$Edition]
[IO.File]::WriteAllText((Join-Path $Root $editionFile), ($savedEdition -replace 'EDITION = "directml"', "EDITION = `"$Edition`""))
[IO.File]::WriteAllText((Join-Path $Root $initFile), ($savedInit -replace '__version__ = "([^"]+)"', "__version__ = `"`$1$suffix`""))
# An internal test build carries the edition suffix in the exe's version strings too (KiraPick.exe properties).
$versionInfoFile = "packaging\version_info.txt"
$savedVersionInfo = Get-Content $versionInfoFile -Raw -Encoding UTF8
$srcVersion = ([regex]::Match($savedInit, '__version__ = "([^"]+)"')).Groups[1].Value
# internal: a development version (3.0.0b1.dev5); beta: a pre-release (3.0.0b1, 3.0.0rc1); official: the rest.
$channel = if ($srcVersion -like "*.dev*") { "internal" } elseif ($srcVersion -match '^\d+(\.\d+)*(a|b|rc)\d+$') { "beta" } else { "official" }
Write-Host "Kênh: $channel (phiên bản gốc $srcVersion)"
if ($suffix) {  # every channel: KiraPick.exe properties show the edition version (3.0.0a)
    [IO.File]::WriteAllText((Join-Path $Root $versionInfoFile), ($savedVersionInfo -replace "(StringStruct\('(FileVersion|ProductVersion)', '[^']+)'", "`${1}$suffix'"))
}
$env:KIRAPICK_EDITION = $Edition
try {

Step "3/6 Mô hình AI (kiểm tra SHA-256)"
$models = Join-Path $Root "build\models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
# LIC-1 S8: only the weights configs/model-policy.json verifies are fetched (fetch_models.py skips pending / never
# ones); nothing else is copied in from the build machine, and nothing is converted from PyTorch checkpoints any more
# (TOPIQ never, CLIP / LAION pending).
Invoke-Tool "Tải mô hình AI (chỉ file trong danh sách cho phép)" $bpy @("scripts\fetch_models.py", "--purpose", "identity,quality,gpu", "--dest", $models)

# Large models: weights stored as float16 (half the size; checked against the originals).
Invoke-Tool "Cài onnx (chỉ để thu gọn mô hình)" $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "onnx==1.23.2")
Invoke-Tool "Thu gọn mô hình lớn" $bpy @("scripts\shrink_models.py", "--dest", $models)

Step "4/6 PyInstaller"
$dist = Join-Path $Root "dist\KiraPick"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
Invoke-Tool "PyInstaller" $bpy @("-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", "build\pyi", "--distpath", "dist", "packaging\kirapick.spec")
New-Item -ItemType Directory -Force -Path (Join-Path $dist "models") | Out-Null
# The weights only: their SHA-256 is pinned in the allow-list, side files (*.sha256) are not shipped any more
Copy-Item (Join-Path $models "*.onnx") (Join-Path $dist "models")

Step "5/6 Tự kiểm tra bản đóng gói (chặn mạng)"
$report = Join-Path $Root "dist\selftest.json"
Remove-Item $report -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath (Join-Path $dist "KiraPick.exe") -ArgumentList @("--self-test", "`"$report`"") -Wait -PassThru
if (Test-Path $report) { Get-Content $report -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
if ($proc.ExitCode -ne 0 -or -not (Test-Path $report)) {
    $crash = Join-Path $Root "dist\selftest.crash.txt"
    if (Test-Path $crash) { Get-Content $crash -Encoding UTF8 | Select-Object -Last 30 | ForEach-Object { Write-Host $_ } }
    $startup = Join-Path $dist "startup-error.txt"  # Python error before the self-test could start
    if (Test-Path $startup) { Get-Content $startup -Encoding UTF8 | Select-Object -Last 20 | ForEach-Object { Write-Host $_ } }
    $fallback = Join-Path $env:LOCALAPPDATA "KiraPick\logs\selftest.json"  # where the app writes if dist\ fails
    if (Test-Path $fallback) {
        $r = Get-Content $fallback -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Host ("error: " + $r.error)
        Write-Host ("steps: " + ($r.steps -join " | "))
        if ($r.traceback) { ($r.traceback -split "`n") | Select-Object -Last 12 | ForEach-Object { Write-Host $_ } }
    }
    if (Test-Path $report) {
        $w = Get-Content $report -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Host ("windowed report: ok=" + $w.ok + " error=" + $w.error + " steps=" + ($w.steps -join " | "))
        Write-Host ("models: " + ($w.models | ConvertTo-Json -Compress) + " dir=" + $w.models_dir)
        Get-ChildItem (Join-Path $dist "models") | Select-Object -First 8 | ForEach-Object { Write-Host ("  " + $_.Name + " " + $_.Length) }
        if ($w.traceback) { ($w.traceback -split "`n") | Select-Object -Last 8 | ForEach-Object { Write-Host $_ } }
    }
    # Diagnose: the same app built as a console program shows Python's own error output.
    $env:KIRAPICK_CONSOLE = "1"
    Invoke-Tool "PyInstaller (console, chẩn đoán)" $bpy @("-m", "PyInstaller", "--noconfirm", "--workpath", "build\pyi-console", "--distpath", "dist-console", "packaging\kirapick.spec")
    $env:KIRAPICK_CONSOLE = $null
    Copy-Item (Join-Path $dist "models") (Join-Path $Root "dist-console\KiraPick\models") -Recurse -Force
    $errFile = Join-Path $Root "dist-console\stderr.txt"
    $outFile = Join-Path $Root "dist-console\stdout.txt"
    $diag = Start-Process -FilePath (Join-Path $Root "dist-console\KiraPick\KiraPick.exe") -ArgumentList @("--self-test", "`"$(Join-Path $Root 'dist-console\st.json')`"") -Wait -PassThru -RedirectStandardError $errFile -RedirectStandardOutput $outFile
    Write-Host ("console exit {0:X8}" -f $diag.ExitCode)
    $st = Join-Path $Root "dist-console\st.json"
    if (Test-Path $st) { $r = Get-Content $st -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Host ("partial report: ok=" + $r.ok + " error=" + $r.error + " steps=" + ($r.steps -join " | ")) }
    foreach ($f in @($outFile, $errFile)) { if (Test-Path $f) { Get-Content $f -Encoding UTF8 | Select-Object -Last 25 | ForEach-Object { Write-Host $_ } } }
    throw ("Tự kiểm tra thất bại, mã thoát {0:X8} (xem dist\selftest.json)" -f $proc.ExitCode)
}

Step "6/6 Bộ cài và file zip"
$version = (& $bpy -c "import sys; sys.path.insert(0, '.'); from app import __version__; print(__version__)" | Out-String).Trim()
$out = Join-Path $Root "dist\installer"
$notes = Join-Path $Root "dist\installer-notes"
foreach ($d in @($out, $notes)) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Copy-Item "packaging\notes\*" $notes
if ($Edition -ne "cuda") { Remove-Item (Join-Path $notes "HUONG_DAN_CUDNN.txt") }  # cuDNN guide: CUDA edition only
Copy-Item "LICENSE.md", "THIRD_PARTY_NOTICES.md" $notes  # model-licenses.md is development history (LIC-1)
Copy-Item "packaging\notes\HUONG_DAN_CAI_DAT.txt", "LICENSE.md" $dist
# LIC-1 S10: the full licence texts, collected from the repository and from the packages of this build
Invoke-Tool "Giấy phép (toàn văn)" $bpy @("scripts\collect_licenses.py", "--dest", (Join-Path $notes "licenses"), "--edition", $Edition)
# The same documents inside the program folder, so the portable zip carries them too
Copy-Item $notes (Join-Path $dist "docs") -Recurse -Force
# LIC-1 S8 gate: weights = the allow-list, no weight elsewhere, no FFmpeg / TensorRT / duplicate NVIDIA DLL, licences
$gate = Join-Path $Root "dist\package-check-$Edition.json"
& $bpy "scripts\check_package.py" $dist "--edition" $Edition "--json" $gate
if ($LASTEXITCODE -ne 0) { throw "Kiểm tra gói thất bại (xem $gate)" }

$guide = Join-Path $Root "packaging\notes\HUONG_DAN_CAI_DAT.txt"
# An internal test (".dev") or a beta (pre-release) build: its own installer identity (packaging\installer.iss),
# its own file names, the Setup.exe only (no portable zip).
$internal = $channel -ne "official"
$internalName = @{ "internal-cuda" = "KiraPick-InternalTest-CUDA"; "internal-directml" = "KiraPick-InternalTest";
                   "beta-cuda" = "KiraPick-Beta-CUDA"; "beta-directml" = "KiraPick-Beta" }["$channel-$Edition"]
if ($internal -and -not $internalName) { throw "Chưa có tên bộ cài cho kênh $channel, bản $Edition" }
$setupBase = if ($internal) { "$internalName-$version-Setup" } else { "KiraPick-Setup-$version" }
$bundleName = if ($internal) { "$internalName-$version-BoCai.zip" } else { "KiraPick-$version-BoCai.zip" }
$numeric = ((([regex]::Matches($version, "\d+") | Select-Object -First 3 | ForEach-Object { $_.Value }) + @("0", "0", "0")) | Select-Object -First 3) -join "."
$portable = Join-Path $out "KiraPick-$version-portable.zip"
if ($Edition -eq "cuda" -or $internal) { $portable = $null }  # > 2 GB: GitHub cannot host it; the installer slices can
if ($portable) {
    Compress-Archive -Path $dist -DestinationPath $portable
    Write-Host "Bản giải nén là chạy: $portable"
}

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc -and $internal) { throw "Bản thử nội bộ / beta cần Inno Setup 6 (Setup.exe)" }
if (-not $iscc) {
    Write-Host "Chưa có Inno Setup 6 nên chưa tạo được file Setup.exe (winget install --id JRSoftware.InnoSetup -e)." -ForegroundColor Yellow
} else {
    $slice = if ($Edition -eq "cuda") { "/DSliceSize=1800000000" } else { "/DSliceSize=max" }
    Invoke-Tool "Inno Setup" $iscc @("/Q", "/DAppVersion=$version", "/DNumericVersion=$numeric.0", "/DEdition=$Edition", "/DChannel=$channel", $slice, "packaging\installer.iss")
    $setup = Join-Path $out "$setupBase.exe"
    if (-not (Test-Path $setup)) { throw "Không thấy $setupBase.exe" }
    $bundle = Join-Path $out $bundleName
    # Small Setup.exe + its data file(s) (.bin); they must stay together in one folder.
    $slices = @(Get-ChildItem $out -Filter "$setupBase-*.bin" | ForEach-Object { $_.FullName })
    if (-not $slices) { throw "Không thấy file dữ liệu .bin của bộ cài" }
    # A beta goes with the backup script its guide asks for first (step 1: back up %LOCALAPPDATA%\KiraPick).
    $extras = @($guide)
    $extras += Join-Path $Root "scripts\owner_backup.ps1"  # every package: the guide asks for a backup first
    if ($Edition -eq "cuda") {
        # Too big for one zip on GitHub (2 GB per file): publish Setup.exe + its .bin slices + the guide.
        Copy-Item $extras $out
        Write-Host "Bộ cài CUDA: tải Setup.exe và mọi file .bin vào cùng một thư mục" -ForegroundColor Green
    } else {
        Compress-Archive -Path (@($setup) + $slices + $extras) -DestinationPath $bundle
        Write-Host "Bộ cài (gửi file này cho bạn bè): $bundle" -ForegroundColor Green
    }
}
Get-ChildItem $out | Format-Table Name, @{ n = "MB"; e = { [math]::Round($_.Length / 1MB) } } | Out-String | Write-Host
if ($env:GITHUB_ACTIONS -eq "true") {  # provenance, readable through the API (artifacts are not)
    foreach ($f in Get-ChildItem $out -File) {
        Write-Host ("::notice title=artifact {0}::{1} bytes sha256 {2}" -f $f.Name, $f.Length, (Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower())
    }
    $identity = Join-Path $out "installer-identity.iss"
    if (Test-Path $identity) {
        $keys = Get-Content $identity | Where-Object { $_ -match "^(AppId|AppName|AppVersion|AppVerName|DefaultDirName|OutputBaseFilename|UninstallDisplayName|VersionInfoVersion|VersionInfoTextVersion)=" }
        Write-Host ("::notice title=installer identity (as compiled)::" + ($keys -join " | "))
        $run = @(Get-Content $identity | Where-Object { $_ -match "^\[Run\]" }).Count
        Write-Host "::notice title=installer [Run] sections::$run (0 = the app is not started after installing)"
    }
}
} finally {
    [IO.File]::WriteAllText((Join-Path $Root $editionFile), $savedEdition)
    [IO.File]::WriteAllText((Join-Path $Root $initFile), $savedInit)
    [IO.File]::WriteAllText((Join-Path $Root $versionInfoFile), $savedVersionInfo)
}
