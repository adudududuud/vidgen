@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_windows.ps1"
if errorlevel 1 echo Startup failed. Please check the error above.
pause
