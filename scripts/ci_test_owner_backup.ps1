# CI test of scripts/owner_backup.ps1 with Windows PowerShell 5 on a throwaway runner (never on a user's PC: it writes
# test data into %LOCALAPPDATA%\KiraPick). One line per check, a summary notice at the end, exit 1 on any failure.
# Continue: in Windows PowerShell 5 a native command's stderr would otherwise stop this script (the tool reports its
# refusals on stderr on purpose); every outcome is checked explicitly instead.
$ErrorActionPreference = "Continue"
trap { Write-Host "::notice title=owner_backup.ps1 tests ABORTED::$($_.Exception.Message) at line $($_.InvocationInfo.ScriptLineNumber)"; exit 2 }
$tool = Join-Path $PSScriptRoot "owner_backup.ps1"
$data = Join-Path $env:LOCALAPPDATA "KiraPick"
$bk = Join-Path $env:RUNNER_TEMP "SaoLuu"
$lines = @(); $failed = 0
function Check($ok, [string]$what) {
    $tag = if ($ok) { "PASS" } else { "FAIL" }
    $script:lines += "$tag $what"; if (-not $ok) { $script:failed++ }
    Write-Host "$tag $what"
}
function State([string]$root) {
    if (-not (Test-Path $root)) { return "" }
    (Get-ChildItem -Recurse -File $root | Sort-Object FullName | ForEach-Object {
        "$($_.FullName.Substring($root.Length))=$((Get-FileHash $_.FullName).Hash)" }) -join ";"
}
function Run-Tool([string[]]$toolArgs) {
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $tool @toolArgs 2>&1 | Out-String
    return @{ code = $LASTEXITCODE; out = $out }
}

# Existing user data and settings
New-Item -ItemType Directory -Force (Join-Path $data "sessions\a"), (Join-Path $data "learning") | Out-Null
Set-Content (Join-Path $data "sessions\a\project.snorlu.db") "v5 database"
Set-Content (Join-Path $data "learning\taste.json") "{}"
reg add "HKCU\Software\KiraPick\KiraPick" /v "export/include_pairs" /d "false" /f | Out-Null
$original = State $data

# 1. Backup
$r = Run-Tool @("-Destination", $bk)
$first = @(Get-ChildItem $bk -Directory)
Check ($r.code -eq 0 -and $first.Count -eq 1 -and (State (Join-Path $first[0].FullName "KiraPick")) -eq $original -and
       (Test-Path (Join-Path $first[0].FullName "kirapick-settings.reg")) -and (Test-Path (Join-Path $first[0].FullName "DOC_TOI.txt"))) "backup: new dated folder, data byte-identical, settings .reg, DOC_TOI.txt"
$firstState = State $first[0].FullName
# 2. A second backup in the same second
$r = Run-Tool @("-Destination", $bk)
Check ($r.code -eq 0 -and @(Get-ChildItem $bk -Directory).Count -eq 2 -and (State $first[0].FullName) -eq $firstState) "backup twice: second folder ($((Get-ChildItem $bk -Directory | ForEach-Object Name) -join ', ')), first unchanged"
# 3. Destination inside %LOCALAPPDATA% refused, nothing created
$r = Run-Tool @("-Destination", (Join-Path $env:LOCALAPPDATA "SaoLuuSai"))
Check ($r.code -ne 0 -and -not (Test-Path (Join-Path $env:LOCALAPPDATA "SaoLuuSai"))) "backup into %LOCALAPPDATA% refused"
# 4. Refused while KiraPick runs (a stand-in process named KiraPick.exe)
$fake = Join-Path $env:RUNNER_TEMP "KiraPick.exe"
Copy-Item "$env:WINDIR\System32\ping.exe" $fake
$p = Start-Process $fake -ArgumentList "-n", "30", "127.0.0.1" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 1
$r = Run-Tool @("-Restore", $first[0].FullName)
Stop-Process -Id $p.Id -Force; Start-Sleep -Seconds 1
Check ($r.code -ne 0 -and (State $data) -eq $original -and @(Get-ChildItem $env:LOCALAPPDATA -Directory -Filter "KiraPick.*").Count -eq 0) "restore refused while KiraPick.exe runs, nothing changed"

# 5. Restore when names for this second (and the next ones) are taken
Add-Content (Join-Path $data "sessions\a\project.snorlu.db") "upgraded to v7 by the test build"
$changed = State $data
$now = Get-Date
$taken = @()
for ($s = 0; $s -lt 15; $s++) {
    $dir = "$data.truoc-khoi-phuc-$($now.AddSeconds($s).ToString('yyyyMMdd-HHmmss'))"
    New-Item -ItemType Directory -Force $dir | Out-Null
    Set-Content (Join-Path $dir "marker.txt") "pre-existing $s"
    $taken += $dir
}
$takenState = ($taken | ForEach-Object { State $_ }) -join "|"
$r = Run-Tool @("-Restore", $first[0].FullName)
$asides = @(Get-ChildItem $env:LOCALAPPDATA -Directory -Filter "KiraPick.truoc-khoi-phuc-*" | Where-Object { $taken -notcontains $_.FullName })
Check ($r.code -eq 0 -and (State $data) -eq $original -and $asides.Count -eq 1 -and $asides[0].Name -match "-\d+$" -and
       (State $asides[0].FullName) -eq $changed -and (($taken | ForEach-Object { State $_ }) -join "|") -eq $takenState) "restore with taken names: data restored, previous data kept as $($asides[0].Name), the 15 existing folders untouched"
Check ((reg query "HKCU\Software\KiraPick\KiraPick" /v "export/include_pairs" 2>$null | Out-String) -match "false") "restore: settings re-imported"

# 6. Restore that fails half-way (a backup file locked by another program): nothing deleted or overwritten
Add-Content (Join-Path $data "sessions\a\project.snorlu.db") "changed again"
$before = State $data
$asidesBefore = @(Get-ChildItem $env:LOCALAPPDATA -Directory -Filter "KiraPick.*" | ForEach-Object { "$($_.Name)=$(State $_.FullName)" }) -join "|"
$locked = Join-Path $first[0].FullName "KiraPick\sessions\a\project.snorlu.db"
$lock = [IO.File]::Open($locked, "Open", "Read", "None")
try { $r = Run-Tool @("-Restore", $first[0].FullName) } finally { $lock.Close() }
$failedCopies = @(Get-ChildItem $env:LOCALAPPDATA -Directory -Filter "KiraPick.khoi-phuc-loi-*")
$asidesAfter = @(Get-ChildItem $env:LOCALAPPDATA -Directory -Filter "KiraPick.*" | Where-Object { $_.Name -notlike "KiraPick.khoi-phuc-loi-*" } | ForEach-Object { "$($_.Name)=$(State $_.FullName)" }) -join "|"
Check ($r.code -ne 0 -and $r.out -match "KHÔNG thành công") "failed restore reported: $((($r.out -split "`n") | Where-Object { $_ -match 'KHÔNG' } | Select-Object -First 1).Trim())"
Check ((State $data) -eq $before) "failed restore: the data from before is back in place, byte-identical"
Check ($failedCopies.Count -le 1 -and $asidesAfter -eq $asidesBefore) "failed restore: half copy kept aside ($($failedCopies.Name)), earlier folders untouched"
Check ((State $first[0].FullName) -eq $firstState) "failed restore: the backup itself untouched"

Write-Host "::notice title=owner_backup.ps1 tests ($failed failed)::$($lines -join '%0A')"
Write-Host ("::notice title=owner_backup.ps1 sha256::" + (Get-FileHash $tool).Hash.ToLower())
if ($failed) { exit 1 }
