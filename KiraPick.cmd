@echo off
rem Snorlu AI Culling launcher - double-click to start the app.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Snorlu chua duoc cai dat. Hay chay lenh sau trong PowerShell:
  echo   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app
