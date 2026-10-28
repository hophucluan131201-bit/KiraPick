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
$env:KIRAPICK_EDITION = $Edition
try {

Step "3/6 Mô hình AI (kiểm tra SHA-256)"
$models = Join-Path $Root "build\models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
Get-ChildItem "models\weights\*.onnx" -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not (Test-Path (Join-Path $models $_.Name))) { Copy-Item $_.FullName $models }
}
Invoke-Tool "Tải mô hình AI" $bpy @("scripts\fetch_models.py", "--purpose", "identity,identity_plus,quality,gpu", "--dest", $models)

# Converted from PyTorch checkpoints in a separate, build-only venv: TOPIQ (aesthetic, technical,
# face quality) and CLIP ViT-L/14 + LAION aesthetic + style prompts.
$converted = @("topiq_iaa_res50.onnx", "topiq_nr_koniq_res50.onnx", "topiq_nr_face_res50.onnx",
               "clip_l14_image.onnx", "laion_aesthetic.onnx", "clip_prompts_v1.npz")
$missing = @($converted | Where-Object { -not (Test-Path (Join-Path $models "$_.sha256")) })
if ($missing) {
    if (-not (Test-Path ".venv-convert\Scripts\python.exe")) {
        Invoke-Tool "Tạo .venv-convert" $pyExe ($pyArgs + @("-m", "venv", ".venv-convert"))
    }
    $cpy = Join-Path $Root ".venv-convert\Scripts\python.exe"
    Invoke-Tool "Cài công cụ chuyển đổi" $cpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "packaging\requirements-convert.txt")
    Invoke-Tool "Cài pyiqa" $cpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "--no-deps", "pyiqa==0.1.14.1")
    Invoke-Tool "Chuyển các mô hình TOPIQ" $cpy @("scripts\convert_topiq.py", "--out", $models, "--variant", "all")
    Invoke-Tool "Chuyển CLIP + LAION" $cpy @("scripts\convert_clip.py", "--out", $models)
    Get-ChildItem $models -Filter "*.pth" | Remove-Item  # checkpoints are not shipped
    Get-ChildItem $models -Filter "*.pt" | Remove-Item
}

# Large models: weights stored as float16 (half the size; checked against the originals).
Invoke-Tool "Cài onnx (chỉ để thu gọn mô hình)" $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "onnx==1.23.2")
Invoke-Tool "Thu gọn mô hình lớn" $bpy @("scripts\shrink_models.py", "--dest", $models)

Step "4/6 PyInstaller"
$dist = Join-Path $Root "dist\KiraPick"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
Invoke-Tool "PyInstaller" $bpy @("-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", "build\pyi", "--distpath", "dist", "packaging\kirapick.spec")
New-Item -ItemType Directory -Force -Path (Join-Path $dist "models") | Out-Null
Copy-Item (Join-Path $models "*.onnx") (Join-Path $dist "models")
Copy-Item (Join-Path $models "*.npz") (Join-Path $dist "models")
Copy-Item (Join-Path $models "*.sha256") (Join-Path $dist "models")

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
Copy-Item "LICENSE.md", "THIRD_PARTY_NOTICES.md", "docs\model-licenses.md" $notes
Copy-Item "packaging\notes\HUONG_DAN_CAI_DAT.txt", "LICENSE.md" $dist

$guide = Join-Path $Root "packaging\notes\HUONG_DAN_CAI_DAT.txt"
$portable = Join-Path $out "KiraPick-$version-portable.zip"
if ($Edition -eq "cuda") { $portable = $null }  # > 2 GB: GitHub cannot host it; the installer slices can
if ($portable) {
    Compress-Archive -Path $dist -DestinationPath $portable
    Write-Host "Bản giải nén là chạy: $portable"
}

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Chưa có Inno Setup 6 nên chưa tạo được file Setup.exe (winget install --id JRSoftware.InnoSetup -e)." -ForegroundColor Yellow
} else {
    $slice = if ($Edition -eq "cuda") { "/DSliceSize=1800000000" } else { "/DSliceSize=max" }
    Invoke-Tool "Inno Setup" $iscc @("/Q", "/DAppVersion=$version", "/DEdition=$Edition", $slice, "packaging\installer.iss")
    $setup = Join-Path $out "KiraPick-Setup-$version.exe"
    $bundle = Join-Path $out "KiraPick-$version-BoCai.zip"
    # Small Setup.exe + its data file(s) (.bin); they must stay together in one folder.
    $slices = @(Get-ChildItem $out -Filter "KiraPick-Setup-$version-*.bin" | ForEach-Object { $_.FullName })
    if (-not $slices) { throw "Không thấy file dữ liệu .bin của bộ cài" }
    if ($Edition -eq "cuda") {
        # Too big for one zip on GitHub (2 GB per file): publish Setup.exe + its .bin slices + the guide.
        Copy-Item $guide $out
        Write-Host "Bộ cài CUDA: tải Setup.exe và mọi file .bin vào cùng một thư mục" -ForegroundColor Green
    } else {
        Compress-Archive -Path (@($setup) + $slices + @($guide)) -DestinationPath $bundle
        Write-Host "Bộ cài (gửi file này cho bạn bè): $bundle" -ForegroundColor Green
    }
}
Get-ChildItem $out | Format-Table Name, @{ n = "MB"; e = { [math]::Round($_.Length / 1MB) } } | Out-String | Write-Host
} finally {
    [IO.File]::WriteAllText((Join-Path $Root $editionFile), $savedEdition)
    [IO.File]::WriteAllText((Join-Path $Root $initFile), $savedInit)
}
