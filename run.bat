@echo off
REM ====================================
REM Automation Browser Application Launcher
REM ====================================

title Automation Browser - Starting...

REM Change console icon (Windows 10+)
if exist "%~dp0app_icon.ico" (
    echo Setting application icon...
)

REM Set console colors (optional - blue background, white text)
color 0F

REM Display startup banner
echo.
echo ================================================
echo    Automation Browser Application
echo ================================================
echo.
echo Starting the application...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python first.
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist "%~dp0main.py" (
    echo [ERROR] main.py not found!
    pause
    exit /b 1
)

REM Run the main application
echo Running main.py...
echo.
python "%~dp0main.py"

REM Check if application crashed
if errorlevel 1 (
    echo.
    echo [ERROR] Application stopped with an error!
    pause
)

exit /b 0
