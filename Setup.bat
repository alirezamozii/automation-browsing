@echo off
setlocal
cd /d "%~dp0"
title Automation Platform Installer

echo.
echo ==========================================
echo   Automation Platform - Installer
echo ==========================================
echo.

REM Launch the PowerShell installer script
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup.ps1"

if errorlevel 1 (
    echo.
    echo [ERROR] Setup encountered an error. See above for details.
    pause
    exit /b 1
)

exit /b 0
