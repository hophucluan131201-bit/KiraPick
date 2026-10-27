<#
Build the Windows installer of Snorlu AI Culling (CPU build, works offline).

    powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1

Steps: separate build venv (.venv-build, Python 3.12) with the exact versions in
packaging\requirements-installer.txt -> verified model weights -> PyInstaller folder
-> offline self-test of the packaged exe (network blocked) -> Inno Setup installer
(if Inno Setup 6 is installed) and a portable .zip.
Changes nothing outside the project folder. Needs Internet only to download packages
and model weights (development time, never at app run time).
Output: dist\installer\
#>
param([switch]$NonInteractive)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$Root = Get-Location
function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }

Step "1/6 Python 3.12"
function Test-Python312([string]$exe, [string[]]$pre) {
    try {
        $out = & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -eq "3.12") { return $true }
    } catch { }
    return $false
}
$pyExe = $null; $pyArgs = @()
if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-Python312 'py' @('-3.12'))) { $pyExe = 'py'; $pyArgs = @('-3.12') }
elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-Python312 'python' @())) { $pyExe = 'python' }
if (-not $pyExe) { throw "Cần Python 3.12: winget install --id Python.Python.3.12 -e" }
Write-Host "Dùng: $pyExe $pyArgs"

Step "2/6 Môi trường build riêng (.venv-build)"
if (-not (Test-Path ".venv-build\Scripts\python.exe")) {
    & $pyExe @pyArgs -m venv .venv-build
}
$bpy = Join-Path $Root ".venv-build\Scripts\python.exe"
& $bpy -m pip install --disable-pip-version-check -q --upgrade pip
& $bpy -m pip install --disable-pip-version-check -q -r packaging\requirements-installer.txt
if ($LASTEXITCODE -ne 0) { throw "pip install thất bại" }

Step "3/6 Mô hình AI (kiểm tra SHA-256)"
$models = Join-Path $Root "build\models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
Get-ChildItem "models\weights\*.onnx" -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not (Test-Path (Join-Path $models $_.Name))) { Copy-Item $_.FullName $models }
}
& $bpy scripts\fetch_models.py --purpose identity,quality --dest $models
if ($LASTEXITCODE -ne 0) { throw "Thiếu mô hình AI" }
Remove-Item (Join-Path $models "yolox_m.onnx") -ErrorAction SilentlyContinue  # GPU-only model, not shipped

Step "4/6 PyInstaller"
$dist = Join-Path $Root "dist\Snorlu AI Culling"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
& $bpy -m PyInstaller --noconfirm --clean --workpath build\pyi --distpath dist packaging\snorlu.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller thất bại" }
New-Item -ItemType Directory -Force -Path (Join-Path $dist "models") | Out-Null
Copy-Item (Join-Path $models "*.onnx") (Join-Path $dist "models")

Step "5/6 Tự kiểm tra bản đóng gói (chặn mạng)"
$report = Join-Path $Root "dist\selftest.json"
Remove-Item $report -ErrorAction SilentlyContinue
$p = Start-Process -FilePath (Join-Path $dist "Snorlu.exe") -ArgumentList @("--self-test", "`"$report`"") -Wait -PassThru
Get-Content $report -Encoding UTF8 | Write-Host
if ($p.ExitCode -ne 0) { throw "Tự kiểm tra thất bại (xem dist\selftest.json)" }

Step "6/6 Bộ cài"
$version = (& $bpy -c "import sys; sys.path.insert(0, '.'); from app import __version__; print(__version__)").Trim()
$notes = Join-Path $Root "dist\installer-notes"
New-Item -ItemType Directory -Force -Path $notes, "dist\installer" | Out-Null
Copy-Item packaging\notes\* $notes
Copy-Item docs\model-licenses.md $notes
$zip = "dist\installer\Snorlu-AI-Culling-$version-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $dist -DestinationPath $zip
Write-Host "Bản portable (giải nén là chạy): $zip"
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Chưa có Inno Setup 6 nên chưa tạo được file Setup.exe." -ForegroundColor Yellow
    Write-Host "Cài một lần:  winget install --id JRSoftware.InnoSetup -e   rồi chạy lại script này."
} else {
    & $iscc "/DAppVersion=$version" packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup thất bại" }
    Write-Host "Bộ cài: dist\installer\Snorlu-AI-Culling-Setup-$version.exe" -ForegroundColor Green
}
Get-ChildItem dist\installer | Format-Table Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB) } }
