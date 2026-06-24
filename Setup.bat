<# :
@echo off
setlocal
cd /d "%~dp0"
title Automation Platform Installer
powershell -NoProfile -ExecutionPolicy Bypass -Command "$_=(Get-Content '%~f0' -Raw); Invoke-Expression $_"
exit /b
#>

$ErrorActionPreference = 'Stop'
$BaseDir = $PSScriptRoot

Write-Host "=========================================="
Write-Host " Automation Platform - Web Installer"
Write-Host "=========================================="

# 1. Download Python if missing
$PythonDir = "$BaseDir\python"
if (-Not (Test-Path "$PythonDir\pythonw.exe")) {
    Write-Host "`n[1/5] Downloading Portable Python 3.11..."
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" -OutFile "python.zip"
    
    Write-Host "Extracting Python..."
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
    Expand-Archive -Path "python.zip" -DestinationPath $PythonDir -Force
    Remove-Item "python.zip"

    Write-Host "Configuring Python environment..."
    $PthFile = "$PythonDir\python311._pth"
    (Get-Content $PthFile) -replace '#import site', 'import site' | Set-Content $PthFile

    Write-Host "Installing pip..."
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "get-pip.py"
    & "$PythonDir\python.exe" get-pip.py --index-url https://pypi.org/simple/
    Remove-Item "get-pip.py"
} else {
    Write-Host "`n[1/5] Python is already installed."
}

# 2. Install Python Dependencies
Write-Host "`n[2/5] Installing Required Libraries..."
& "$PythonDir\python.exe" -m pip install -r "$BaseDir\requirements.txt" --index-url https://pypi.org/simple/

# 3. Install Playwright Browsers
Write-Host "`n[3/5] Installing Playwright Browsers (This may take a minute)..."
$BrowsersDir = "$BaseDir\playwright_browsers"
if (-Not (Test-Path $BrowsersDir)) {
    New-Item -ItemType Directory -Force -Path $BrowsersDir | Out-Null
}
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
& "$PythonDir\python.exe" -m playwright install chromium

# 4. Create Desktop Shortcut
Write-Host "`n[4/5] Creating Desktop Shortcut..."
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\Automation Platform.lnk")
$Shortcut.TargetPath = "$PythonDir\pythonw.exe"
$Shortcut.Arguments = "`"$BaseDir\main.py`""
$Shortcut.WorkingDirectory = $BaseDir
if (Test-Path "$BaseDir\app_icon.ico") {
    $Shortcut.IconLocation = "$BaseDir\app_icon.ico"
}
$Shortcut.Description = "Automation Platform Web App"
$Shortcut.Save()

# 5. Launch Application
Write-Host "`n[5/5] Launching the Application..."
Start-Process -FilePath "$PythonDir\pythonw.exe" -ArgumentList "`"$BaseDir\main.py`"" -WorkingDirectory $BaseDir

Write-Host "`nInstallation Complete! The app is starting in the background."
Write-Host "Your browser will automatically open the dashboard shortly."
Start-Sleep -Seconds 3
