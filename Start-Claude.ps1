# Claude Code launcher for Snorlu AI Culling.
# Run within this extracted folder: & '.\Start-Claude.ps1'
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host 'Claude Code not found. Install via: winget install Anthropic.ClaudeCode' -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path -LiteralPath '.\CLAUDE.md') -or -not (Test-Path -LiteralPath '.\BUILD_TASK.md')) {
    Write-Host 'Please extract the entire starter ZIP first.' -ForegroundColor Red
    exit 1
}
$Task = 'Read CLAUDE.md, BUILD_TASK.md, docs/TECHNICAL_SPEC_v1.1.md and configs/rtx2080_maxq_8gb.yaml fully. Implement Snorlu AI Culling as an actual offline Windows-native desktop app in milestones. Do not stop at a plan: write, test and run M0+M1 now, then continue subsequent milestones when feasible. Keep docs/IMPLEMENTATION_STATUS.md accurate. Never fabricate AI inferences or claim untested features completed. Ask before destructive/system-wide changes or restricted model downloads.'
& claude $Task
