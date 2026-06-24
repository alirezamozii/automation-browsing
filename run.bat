@echo off
cd /d "%~dp0"

set PLAYWRIGHT_BROWSERS_PATH=D:\coding project\automation browsing\playwright_browsers

python "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
