# CI helper (Windows perf job): run pytest with a hard time limit and report its log in the job's notices and step
# summary, readable through the GitHub API even when the log and artifact storage cannot be reached
# (review CR-P2-FINAL-02).
#   . scripts/ci_report.ps1
#   $code = Invoke-Pytest -Log gui.log -Title gui-windows -TimeoutSec 900 -PytestArgs @("tests/gui/test_x.py")
# Notices: one summary line (exit code + pytest's last line), EVERY FAILED / ERROR line, any faulthandler / crash /
# Qt event-loop exception block, and — when the process had to be killed — the last lines it printed (with -v these
# name the test it was in).

function Invoke-Pytest {
    param([string]$Log, [string]$Title, [int]$TimeoutSec, [string[]]$PytestArgs)
    $ErrorActionPreference = "Continue"  # a reporting hiccup must never end the step before its notices
    $err = "$Log.err"
    $all = @("-X", "faulthandler", "-m", "pytest", "-v", "-p", "no:cacheprovider", "-o", "faulthandler_timeout=180",
             "-o", "faulthandler_exit_on_timeout=true") + $PytestArgs
    $start = Get-Date
    $p = Start-Process -FilePath python -ArgumentList $all -RedirectStandardOutput $Log -RedirectStandardError $err `
        -NoNewWindow -PassThru
    $killed = -not $p.WaitForExit($TimeoutSec * 1000)
    if ($killed) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        $code = 124
    } else {
        $p.WaitForExit()
        $code = $p.ExitCode
    }
    if (Test-Path $err) { Get-Content $err | Add-Content $Log }
    Get-Content $Log | Select-Object -Last 60 | ForEach-Object { Write-Host $_ }
    $secs = [int]((Get-Date) - $start).TotalSeconds
    Report-Pytest -Log $Log -Title "$Title (${secs}s)" -Code $code
    if ($killed) {
        $tail = (Get-Content $Log | Select-Object -Last 40) -join " | "
        Write-Host "::notice title=$Title KILLED after ${TimeoutSec}s::$tail"
    }
    return $code
}

function Report-Pytest {
    param([string]$Log, [string]$Title, [int]$Code)
    $ErrorActionPreference = "Continue"
    $lines = @(if (Test-Path $Log) { Get-Content $Log } else { "(no log)" })
    $summary = ($lines | Where-Object { $_ -match "(passed|failed|error|no tests ran)" } | Select-Object -Last 1)
    Write-Host "::notice title=$Title::exit $Code; $summary"
    $failures = @($lines | Where-Object { $_ -match "^(FAILED|ERROR) " })
    if ($failures.Count -gt 0) {
        $text = ($failures | ForEach-Object { $_.Substring(0, [Math]::Min(1500, $_.Length)) }) -join " | "
        Write-Host "::notice title=$Title failures ($($failures.Count))::$text"
    }
    $crash = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "Fatal Python error|Windows fatal exception|Segmentation fault|access violation|Exceptions caught in Qt event loop|^Timeout \(") {
            $crash += $lines[$i..([Math]::Min($i + 40, $lines.Count - 1))]
        }
    }
    if ($crash.Count -gt 0) {
        Write-Host "::notice title=$Title crash::$(($crash | Select-Object -First 120) -join ' | ')"
    }
    if ($env:GITHUB_STEP_SUMMARY) {
        Add-Content $env:GITHUB_STEP_SUMMARY "### $Title — exit $Code`n``````n$summary`n$($failures -join "`n")`n$($crash -join "`n")`n``````"
    }
}
