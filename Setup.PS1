# ============================================================
# Automation Platform - Setup.ps1 (Global & Smart Skip Edition)
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

# --- Section 1: Python ---
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow

$PythonExe = $null

try {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}
catch {
}

if (-not $PythonExe) {
    Write-Host "Python not found globally." -ForegroundColor Yellow
    if (Ask-YesNo "Install Python automatically?" $true) {
        $Installer = Join-Path $env:TEMP "python-installer.exe"
        $Version = "3.12.4"
        $Url = "https://www.python.org/ftp/python/$Version/python-$Version-amd64.exe"

        Write-Host "Downloading Python..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $Url -OutFile $Installer
        
        # Installs for current user, adds to PATH, includes pip
        Start-Process -FilePath $Installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" -Wait
        Remove-Item $Installer -Force
        Start-Sleep 5

        try {
            $PythonExe = (Get-Command python -ErrorAction Stop).Source
        }
        catch {
            Fail "Python installation failed. Please install it manually and add it to PATH."
        }
    }
    else {
        Fail "Python is required to continue."
    }
}
else {
    Write-Host "Python is already installed. Skipping download." -ForegroundColor Green
}

$VersionInfo = & $PythonExe --version
Write-Host "Found $VersionInfo" -ForegroundColor Green


# --- Section 2: Pip ---
Write-Host ""
Write-Host "[2/5] Checking pip..." -ForegroundColor Yellow

try {
    & $PythonExe -m pip --version | Out-Null
    Write-Host "pip is already installed. Skipping download." -ForegroundColor Green
}
catch {
    Write-Host "Installing pip..." -ForegroundColor Yellow
    $GetPip = Join-Path $env:TEMP "get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
    & $PythonExe $GetPip
    Remove-Item $GetPip -Force
    Write-Host "pip installed successfully." -ForegroundColor Green
}


# --- Section 3: Libraries / Requirements ---
Write-Host ""
Write-Host "[3/5] Checking global libraries..." -ForegroundColor Yellow

$Requirements = Join-Path $BaseDir "requirements.txt"

if (-not (Test-Path $Requirements)) {
    Fail "requirements.txt not found in the root directory."
}

# Pip naturally checks existing global installations and skips downloading them again.
& $PythonExe -m pip install --upgrade pip | Out-Null
& $PythonExe -m pip install -r $Requirements

if ($LASTEXITCODE -ne 0) {
    Fail "Requirements installation failed."
}

Write-Host "Global dependencies validated (existing libraries were skipped)." -ForegroundColor Green


# --- Section 4: Playwright Browser (Smart Cache) ---
Write-Host ""
Write-Host "[4/5] Checking global Playwright Chromium..." -ForegroundColor Yellow

# CRITICAL FIX: Safely annihilate old custom Playwright paths without triggering Admin prompts
try { [Environment]::SetEnvironmentVariable("PLAYWRIGHT_BROWSERS_PATH", $null, "Process") } catch {}
try { [Environment]::SetEnvironmentVariable("PLAYWRIGHT_BROWSERS_PATH", $null, "User") } catch {}

Write-Host "Checking global system cache. If Chromium exists, the download will be skipped..." -ForegroundColor Cyan

# Playwright natively skips if the browser is found in %USERPROFILE%\AppData\Local\ms-playwright
& $PythonExe -m playwright install chromium

if ($LASTEXITCODE -ne 0) {
    Write-Host "Playwright installation returned a warning. It may still work." -ForegroundColor Yellow
}
else {
    Write-Host "Chromium validated globally." -ForegroundColor Green
}


# --- Section 5: Launcher ---
Write-Host ""
Write-Host "[5/5] Creating launcher..." -ForegroundColor Yellow

$RunBat = Join-Path $BaseDir "run.bat"

# Generate a clean batch file that just runs the app natively
@"
@echo off
cd /d "%~dp0"

python "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
"@ | Set-Content $RunBat -Encoding ASCII

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Automation Platform.lnk"

# Create Desktop Shortcut
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $RunBat
$Shortcut.WorkingDirectory = $BaseDir
$Shortcut.Description = "Automation Platform Launcher"
$Shortcut.Save()

Write-Host "Launcher generated and shortcut placed on Desktop." -ForegroundColor Green

# Final Launch Sequence
if (Test-Path (Join-Path $BaseDir "main.py")) {
    Write-Host ""
    Write-Host "Starting application..." -ForegroundColor Green
    Start-Process -FilePath $RunBat -WorkingDirectory $BaseDir
}
else {
    Write-Host ""
    Write-Host "main.py not found. Installation is complete, but there is no app to launch yet." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to close"