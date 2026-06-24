<# :
@echo off
setlocal
cd /d "%~dp0"
title Automation Platform Installer
powershell -NoProfile -ExecutionPolicy Bypass -File "%~f0"
exit /b
#>

# ============================================================
#  Automation Platform - Setup & Installer
#  Fully self-contained PowerShell setup
# ============================================================

$ErrorActionPreference = 'Stop'
$BaseDir = $PSScriptRoot
if (-not $BaseDir) { $BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Automation Platform - Installer v2"      -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Helper: yes/no prompt ────────────────────────────────────────────────────
function Ask-YesNo ($Prompt, $DefaultYes = $false) {
    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $response = Read-Host "$Prompt $suffix"
        if ([string]::IsNullOrWhiteSpace($response)) { return $DefaultYes }
        if ($response -match '^[yY]') { return $true }
        if ($response -match '^[nN]') { return $false }
        Write-Host "Please enter 'y' or 'n'."
    }
}

# ── Step 1: Find or install Python ──────────────────────────────────────────
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow

# Check for latest stable version online
$LatestVersion = "3.12.4"   # safe fallback
try {
    $releases = Invoke-RestMethod -Uri "https://endoflife.date/api/python.json" -UseBasicParsing -TimeoutSec 10
    $Today = Get-Date
    foreach ($r in $releases) {
        try {
            $relDate = [datetime]$r.releaseDate
            if ($relDate -le $Today) { $LatestVersion = $r.latest; break }
        } catch { continue }
    }
    Write-Host "  Latest stable Python online: $LatestVersion"
} catch {
    Write-Host "  (Could not reach internet — using fallback version $LatestVersion)" -ForegroundColor DarkGray
}

$PythonExe   = $null
$InstalledVersion = $null
$UsingPortable = $false

# Prefer portable python bundled next to Setup.bat
$PortablePy = "$BaseDir\python\python.exe"
if (Test-Path $PortablePy) {
    try {
        $v = & $PortablePy --version 2>&1
        if ($v -match 'Python\s+([\d\.]+)') {
            $InstalledVersion = $Matches[1]
            $PythonExe = $PortablePy
            $UsingPortable = $true
            Write-Host "  Found portable Python $InstalledVersion at .\python\"
        }
    } catch { }
}

# Fall back to system Python
if (-not $PythonExe) {
    try {
        $sysPy = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1
        if ($sysPy) {
            $v = & $sysPy --version 2>&1
            if ($v -match 'Python\s+([\d\.]+)') {
                $InstalledVersion = $Matches[1]
                $PythonExe = $sysPy
                Write-Host "  Found system Python $InstalledVersion at $sysPy"
            }
        }
    } catch { }
}

$ShouldInstall = $false
if (-not $PythonExe) {
    Write-Host "  No Python found — will install portable Python $LatestVersion." -ForegroundColor Yellow
    $ShouldInstall = $true
} else {
    try {
        $currVer   = [version]$InstalledVersion
        $latestVer = [version]$LatestVersion
        if ($latestVer -gt $currVer) {
            Write-Host "  A newer Python ($LatestVersion) is available (you have $InstalledVersion)."
            $ShouldInstall = Ask-YesNo "  Update to Python $LatestVersion?" $true
        } else {
            Write-Host "  Python $InstalledVersion is up-to-date. OK" -ForegroundColor Green
        }
    } catch {
        Write-Host "  Could not compare versions — keeping existing Python."
    }
}

$PythonDir = "$BaseDir\python"

if ($ShouldInstall) {
    Write-Host "  Downloading portable Python $LatestVersion..." -ForegroundColor Yellow
    $DownloadUrl = "https://www.python.org/ftp/python/$LatestVersion/python-$LatestVersion-embed-amd64.zip"
    try {
        Invoke-WebRequest -Uri $DownloadUrl -OutFile "$BaseDir\python.zip" -UseBasicParsing
    } catch {
        Write-Host "  ERROR: Download failed. Check your internet connection." -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }

    if (Test-Path $PythonDir) { Remove-Item $PythonDir -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
    Expand-Archive -Path "$BaseDir\python.zip" -DestinationPath $PythonDir -Force
    Remove-Item "$BaseDir\python.zip" -ErrorAction SilentlyContinue

    # Enable site-packages (required for pip to work in embed layout)
    $PthFile = Get-ChildItem -Path $PythonDir -Filter "*._pth" | Select-Object -First 1
    if ($PthFile) {
        (Get-Content $PthFile.FullName) -replace '#import site', 'import site' | Set-Content $PthFile.FullName
    }

    Write-Host "  Installing pip..."
    try {
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "$BaseDir\get-pip.py" -UseBasicParsing
        & "$PythonDir\python.exe" "$BaseDir\get-pip.py" --index-url https://pypi.org/simple/
        Remove-Item "$BaseDir\get-pip.py" -ErrorAction SilentlyContinue
    } catch {
        Write-Host "  WARNING: pip install failed: $_" -ForegroundColor Yellow
    }

    $PythonExe = "$PythonDir\python.exe"
    $UsingPortable = $true
    Write-Host "  Portable Python installed OK." -ForegroundColor Green
}

# Make sure pip is available
try {
    $null = & $PythonExe -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "pip not found" }
} catch {
    Write-Host "  pip not found — attempting bootstrap..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "$BaseDir\get-pip.py" -UseBasicParsing
        & $PythonExe "$BaseDir\get-pip.py" --index-url https://pypi.org/simple/
        Remove-Item "$BaseDir\get-pip.py" -ErrorAction SilentlyContinue
    } catch {
        Write-Host "  WARNING: Could not install pip automatically." -ForegroundColor Yellow
    }
}

# ── Step 2: Install Python dependencies ──────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Installing Python dependencies..." -ForegroundColor Yellow

$RequiredLibs = @("playwright", "fastapi", "uvicorn", "aiosqlite", "pydantic", "jinja2", "python-multipart")

# Get installed packages
$MissingLibs  = @()
$OutdatedLibs = @()
try {
    $InstalledJson = & $PythonExe -m pip list --format json 2>&1
    if ($LASTEXITCODE -eq 0) {
        $Installed      = ConvertFrom-Json ($InstalledJson -join "")
        $InstalledNames = $Installed | ForEach-Object { $_.name.ToLower() }
        foreach ($lib in $RequiredLibs) {
            if ($InstalledNames -notcontains $lib.ToLower()) { $MissingLibs += $lib }
        }
        if ($MissingLibs.Count -eq 0) {
            $OutJson = & $PythonExe -m pip list --outdated --format json 2>&1
            if ($LASTEXITCODE -eq 0 -and $OutJson) {
                $Outdated = ConvertFrom-Json ($OutJson -join "")
                foreach ($pkg in $Outdated) {
                    if ($RequiredLibs -contains $pkg.name.ToLower()) { $OutdatedLibs += $pkg }
                }
            }
        }
    } else { $MissingLibs = $RequiredLibs }
} catch { $MissingLibs = $RequiredLibs }

$ShouldInstallLibs = $false
if ($MissingLibs.Count -gt 0) {
    Write-Host "  Missing: $($MissingLibs -join ', ')" -ForegroundColor Yellow
    $ShouldInstallLibs = $true
} elseif ($OutdatedLibs.Count -gt 0) {
    Write-Host "  Outdated packages:" -ForegroundColor Yellow
    foreach ($lib in $OutdatedLibs) {
        Write-Host "    - $($lib.name) ($($lib.version) → $($lib.latest_version))"
    }
    $ShouldInstallLibs = Ask-YesNo "  Update them?" $true
} else {
    Write-Host "  All dependencies OK." -ForegroundColor Green
}

if ($ShouldInstallLibs) {
    Write-Host "  Running pip install..." -ForegroundColor Yellow
    & $PythonExe -m pip install -r "$BaseDir\requirements.txt" --index-url https://pypi.org/simple/
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: pip install failed." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    Write-Host "  Dependencies installed OK." -ForegroundColor Green
}

# ── Step 3: Playwright browsers ──────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] Checking Playwright browsers..." -ForegroundColor Yellow

$BrowsersDir = "$BaseDir\playwright_browsers"
if (-not (Test-Path $BrowsersDir)) { New-Item -ItemType Directory -Force -Path $BrowsersDir | Out-Null }

$HasChromium = (Get-ChildItem -Path $BrowsersDir -Filter "chromium-*" -Directory -ErrorAction SilentlyContinue).Count -gt 0

$ShouldInstallChromium = $true
if ($HasChromium) {
    Write-Host "  Playwright Chromium already installed." -ForegroundColor Green
    $ShouldInstallChromium = Ask-YesNo "  Re-check/update Playwright Chromium?" $false
}

if ($ShouldInstallChromium) {
    Write-Host "  Installing Playwright Chromium (may take a minute)..." -ForegroundColor Yellow
    # IMPORTANT: set env var so playwright knows where to put / find browsers
    $env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
    & $PythonExe -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: Playwright browser install returned non-zero. Check output above." -ForegroundColor Yellow
    } else {
        Write-Host "  Playwright Chromium installed OK." -ForegroundColor Green
    }
}

# Persist PLAYWRIGHT_BROWSERS_PATH to User environment so the shortcut finds browsers
# without needing it set in the shell session
[System.Environment]::SetEnvironmentVariable("PLAYWRIGHT_BROWSERS_PATH", $BrowsersDir, "User")
Write-Host "  PLAYWRIGHT_BROWSERS_PATH saved to user environment variables." -ForegroundColor Green

# ── Step 4: Desktop shortcut ─────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] Creating Desktop shortcut..." -ForegroundColor Yellow

$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = "$DesktopPath\Automation Platform.lnk"

# Decide launcher:
# - Portable python: use pythonw.exe if it exists, else python.exe via run.bat (shows errors)
# - System python: use run.bat so errors are visible; pythonw.exe may not exist
#
# We always use run.bat as the shortcut target — it checks python, shows errors clearly,
# and uses the plain python.exe so a console briefly appears then closes once the
# browser UI opens. This is far more reliable than hunting for pythonw.exe.

$RunBat = "$BaseDir\run.bat"

# Update run.bat to use the correct python executable (portable or system)
$PythonInvoke = if ($UsingPortable) { "`"$PythonDir\python.exe`"" } else { "python" }
$RunBatContent = @"
@echo off
REM ====================================
REM Automation Platform Launcher
REM (Auto-generated by Setup.bat)
REM ====================================
title Automation Platform - Starting...
color 0F

echo.
echo ================================================
echo    Automation Platform
echo ================================================
echo.

REM Set Playwright browser path so it works without env setup
set PLAYWRIGHT_BROWSERS_PATH=$BrowsersDir

REM Check main.py exists
if not exist "%~dp0main.py" (
    echo [ERROR] main.py not found!
    pause
    exit /b 1
)

echo Starting application...
$PythonInvoke "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Application stopped with an error. See above.
    pause
)
exit /b 0
"@
$RunBatContent | Set-Content -Path $RunBat -Encoding ASCII
Write-Host "  run.bat updated with correct Python path."

# Create the desktop shortcut pointing at run.bat
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath      = $RunBat
$Shortcut.WorkingDirectory = $BaseDir
if (Test-Path "$BaseDir\app_icon.ico") {
    $Shortcut.IconLocation = "$BaseDir\app_icon.ico"
}
$Shortcut.Description = "Automation Platform"
$Shortcut.Save()

if (Test-Path $ShortcutPath) {
    Write-Host "  Shortcut created: $ShortcutPath" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Shortcut file not found after save. Try running as Administrator." -ForegroundColor Yellow
}

# ── Step 5: Launch the application ───────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Launching the application..." -ForegroundColor Yellow

$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
Start-Process -FilePath $RunBat -WorkingDirectory $BaseDir

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Setup complete! App is starting..."      -ForegroundColor Green
Write-Host "  Your browser will open the dashboard."   -ForegroundColor Green
Write-Host "  Desktop shortcut: Automation Platform"   -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Start-Sleep -Seconds 2
