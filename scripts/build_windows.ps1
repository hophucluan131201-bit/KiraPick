<#
Build the Windows installer of Snorlu AI Culling (CPU build, works offline).

    powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1

Normally GitHub Actions runs this (.github/workflows/build-windows.yml) and publishes the result on
the Releases page; running it by hand is only needed to build locally.
Steps: separate build venv (.venv-build, Python 3.12) with the exact versions in
packaging\requirements-installer.txt -> verified model weights -> PyInstaller folder
-> offline self-test of the packaged exe (network blocked) -> Inno Setup installer
(if Inno Setup 6 is installed) -> zips with the Vietnamese install guide.
Changes nothing outside the project folder. Needs Internet only to download packages
and model weights (build time, never at app run time).
Output: dist\installer\
#>
param([switch]$NonInteractive)
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

Step "2/6 Môi trường build riêng (.venv-build)"
if (-not (Test-Path ".venv-build\Scripts\python.exe")) {
    Invoke-Tool "Tạo .venv-build" $pyExe ($pyArgs + @("-m", "venv", ".venv-build"))
}
$bpy = Join-Path $Root ".venv-build\Scripts\python.exe"
Invoke-Tool "Cập nhật pip" $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip")
Invoke-Tool "Cài thư viện" $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "packaging\requirements-installer.txt")

Step "3/6 Mô hình AI (kiểm tra SHA-256)"
$models = Join-Path $Root "build\models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
Get-ChildItem "models\weights\*.onnx" -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not (Test-Path (Join-Path $models $_.Name))) { Copy-Item $_.FullName $models }
}
Invoke-Tool "Tải mô hình AI" $bpy @("scripts\fetch_models.py", "--purpose", "identity,quality", "--dest", $models)
Remove-Item (Join-Path $models "yolox_m.onnx") -ErrorAction SilentlyContinue  # GPU-only model, not shipped

Step "4/6 PyInstaller"
$dist = Join-Path $Root "dist\Snorlu AI Culling"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
Invoke-Tool "PyInstaller" $bpy @("-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", "build\pyi", "--distpath", "dist", "packaging\snorlu.spec")
New-Item -ItemType Directory -Force -Path (Join-Path $dist "models") | Out-Null
Copy-Item (Join-Path $models "*.onnx") (Join-Path $dist "models")

Step "5/6 Tự kiểm tra bản đóng gói (chặn mạng)"
$report = Join-Path $Root "dist\selftest.json"
Remove-Item $report -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath (Join-Path $dist "Snorlu.exe") -ArgumentList @("--self-test", "`"$report`"") -Wait -PassThru
if (Test-Path $report) { Get-Content $report -Encoding UTF8 | ForEach-Object { Write-Host $_ } }
if ($proc.ExitCode -ne 0 -or -not (Test-Path $report)) { throw "Tự kiểm tra thất bại (xem dist\selftest.json)" }

Step "6/6 Bộ cài và file zip"
$version = (& $bpy -c "import sys; sys.path.insert(0, '.'); from app import __version__; print(__version__)" | Out-String).Trim()
$out = Join-Path $Root "dist\installer"
$notes = Join-Path $Root "dist\installer-notes"
foreach ($d in @($out, $notes)) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Copy-Item "packaging\notes\*" $notes
Copy-Item "LICENSE.md", "THIRD_PARTY_NOTICES.md", "docs\model-licenses.md" $notes
Copy-Item "packaging\notes\HUONG_DAN_CAI_DAT.txt", "LICENSE.md" $dist

$guide = Join-Path $Root "packaging\notes\HUONG_DAN_CAI_DAT.txt"
$portable = Join-Path $out "Snorlu-AI-Culling-$version-portable.zip"
Compress-Archive -Path $dist -DestinationPath $portable
Write-Host "Bản giải nén là chạy: $portable"

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Chưa có Inno Setup 6 nên chưa tạo được file Setup.exe (winget install --id JRSoftware.InnoSetup -e)." -ForegroundColor Yellow
} else {
    Invoke-Tool "Inno Setup" $iscc @("/Q", "/DAppVersion=$version", "packaging\installer.iss")
    $setup = Join-Path $out "Snorlu-AI-Culling-Setup-$version.exe"
    $bundle = Join-Path $out "Snorlu-AI-Culling-$version-BoCai.zip"
    Compress-Archive -Path $setup, $guide -DestinationPath $bundle
    Write-Host "Bộ cài (gửi file này cho bạn bè): $bundle" -ForegroundColor Green
}
Get-ChildItem $out | Format-Table Name, @{ n = "MB"; e = { [math]::Round($_.Length / 1MB) } } | Out-String | Write-Host
