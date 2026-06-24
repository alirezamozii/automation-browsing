@echo off
cd /d "%~dp0"

python "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
