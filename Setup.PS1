# ============================================================
# Automation Platform - Setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Automation Platform Installer" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Fail($msg) {
    Write-Host ""
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

function Ask-YesNo($Prompt, $DefaultYes = $false) {
    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }

    while ($true) {
        $r = Read-Host "$Prompt $suffix"

        if ([string]::IsNullOrWhiteSpace($r)) {
            return $DefaultYes
        }

        if ($r -match '^[Yy]') { return $true }
        if ($r -match '^[Nn]') { return $false }
    }
}

Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow

$PythonExe = $null

try {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}
catch {
}

if (-not $PythonExe) {

    Write-Host "Python not found." -ForegroundColor Yellow

    if (Ask-YesNo "Install Python automatically?" $true) {

        $Installer = Join-Path $env:TEMP "python-installer.exe"

        $Version = "3.12.4"

        $Url = "https://www.python.org/ftp/python/$Version/python-$Version-amd64.exe"

        Write-Host "Downloading Python..." -ForegroundColor Yellow

        Invoke-WebRequest `
            -Uri $Url `
            -OutFile $Installer

        Start-Process `
            -FilePath $Installer `
            -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" `
            -Wait

        Remove-Item $Installer -Force

        Start-Sleep 5

        try {
            $PythonExe = (Get-Command python -ErrorAction Stop).Source
        }
        catch {
            Fail "Python installation failed."
        }
    }
    else {
        Fail "Python is required."
    }
}

$VersionInfo = & $PythonExe --version

Write-Host "Found $VersionInfo" -ForegroundColor Green

Write-Host ""
Write-Host "[2/5] Checking pip..." -ForegroundColor Yellow

try {
    & $PythonExe -m pip --version | Out-Null
}
catch {

    Write-Host "Installing pip..." -ForegroundColor Yellow

    $GetPip = Join-Path $env:TEMP "get-pip.py"

    Invoke-WebRequest `
        -Uri "https://bootstrap.pypa.io/get-pip.py" `
        -OutFile $GetPip

    & $PythonExe $GetPip

    Remove-Item $GetPip -Force
}

Write-Host "pip OK" -ForegroundColor Green

Write-Host ""
Write-Host "[3/5] Installing requirements..." -ForegroundColor Yellow

$Requirements = Join-Path $BaseDir "requirements.txt"

if (-not (Test-Path $Requirements)) {
    Fail "requirements.txt not found."
}

& $PythonExe -m pip install --upgrade pip

& $PythonExe -m pip install -r $Requirements

if ($LASTEXITCODE -ne 0) {
    Fail "requirements installation failed."
}

Write-Host "Dependencies installed." -ForegroundColor Green

Write-Host ""
Write-Host "[4/5] Installing Playwright Chromium..." -ForegroundColor Yellow

$BrowserDir = Join-Path $BaseDir "playwright_browsers"

if (-not (Test-Path $BrowserDir)) {
    New-Item `
        -ItemType Directory `
        -Path $BrowserDir `
        -Force | Out-Null
}

$env:PLAYWRIGHT_BROWSERS_PATH = $BrowserDir

& $PythonExe -m playwright install chromium

if ($LASTEXITCODE -ne 0) {
    Write-Host "Playwright install returned a warning." -ForegroundColor Yellow
}
else {
    Write-Host "Chromium installed." -ForegroundColor Green
}

[Environment]::SetEnvironmentVariable(
    "PLAYWRIGHT_BROWSERS_PATH",
    $BrowserDir,
    "User"
)

Write-Host ""
Write-Host "[5/5] Creating launcher..." -ForegroundColor Yellow

$RunBat = Join-Path $BaseDir "run.bat"

@"
@echo off
cd /d "%~dp0"

set PLAYWRIGHT_BROWSERS_PATH=$BrowserDir

python "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
"@ | Set-Content $RunBat -Encoding ASCII

$Desktop = [Environment]::GetFolderPath("Desktop")

$ShortcutPath = Join-Path $Desktop "Automation Platform.lnk"

$Shell = New-Object -ComObject WScript.Shell

$Shortcut = $Shell.CreateShortcut($ShortcutPath)

$Shortcut.TargetPath = $RunBat
$Shortcut.WorkingDirectory = $BaseDir
$Shortcut.Description = "Automation Platform"

$Shortcut.Save()

Write-Host "Launcher created." -ForegroundColor Green

if (Test-Path (Join-Path $BaseDir "main.py")) {

    Write-Host ""
    Write-Host "Starting application..." -ForegroundColor Green

    Start-Process `
        -FilePath $RunBat `
        -WorkingDirectory $BaseDir
}
else {
    Write-Host ""
    Write-Host "main.py not found. Installation complete but nothing to launch." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Setup Complete" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to close"