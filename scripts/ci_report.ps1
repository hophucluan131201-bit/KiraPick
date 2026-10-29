# CI helper (Windows perf job): report a pytest log in the job's notices and step summary, readable through the
# GitHub API even when the log and artifact storage cannot be reached (review CR-P2-FINAL-02).
#   . scripts/ci_report.ps1; Report-Pytest -Log suite.log -Title suite -Code $LASTEXITCODE
# Notices: one summary line (exit code + pytest's last line), EVERY FAILED / ERROR line, and any faulthandler or
# crash block (Fatal Python error / Windows fatal exception, with the stack lines after it).

function Report-Pytest {
    param([string]$Log, [string]$Title, [int]$Code)
    $lines = if (Test-Path $Log) { Get-Content $Log } else { @("(no log)") }
    $summary = ($lines | Where-Object { $_ -match "(passed|failed|error|no tests ran)" } | Select-Object -Last 1)
    Write-Host "::notice title=$Title::exit $Code; $summary"
    $failures = @($lines | Where-Object { $_ -match "^(FAILED|ERROR) " })
    if ($failures.Count -gt 0) {
        $text = ($failures | ForEach-Object { $_.Substring(0, [Math]::Min(400, $_.Length)) }) -join " | "
        Write-Host "::notice title=$Title failures ($($failures.Count))::$text"
    }
    $crash = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "(Fatal Python error|Windows fatal exception|Segmentation fault|access violation|Exceptions caught in Qt event loop)") {
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
