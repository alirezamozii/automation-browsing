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

# 1. Check for Python installation and dynamically determine latest version
function Ask-YesNo ($Prompt, $DefaultYes = $false) {
    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $response = Read-Host "$Prompt $suffix"
        if ([string]::IsNullOrWhiteSpace($response)) {
            return $DefaultYes
        }
        if ($response -match '^[yY]') {
            return $true
        }
        if ($response -match '^[nN]') {
            return $false
        }
        Write-Host "Please enter 'y' for Yes or 'n' for No."
    }
}

$InstalledPythonExe = $null
$InstalledVersion = $null

if (Test-Path "$BaseDir\python\python.exe") {
    try {
        $InstalledPythonExe = "$BaseDir\python\python.exe"
        $versionInfo = & $InstalledPythonExe --version 2>&1
        if ($versionInfo -match 'Python\s+([\d\.]+)') {
            $InstalledVersion = $Matches[1]
        }
    } catch {
        $InstalledPythonExe = $null
        $InstalledVersion = $null
    }
}

if (-not $InstalledPythonExe) {
    try {
        $SystemPython = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($SystemPython) {
            $InstalledPythonExe = $SystemPython.Source
            $versionInfo = & $InstalledPythonExe --version 2>&1
            if ($versionInfo -match 'Python\s+([\d\.]+)') {
                $InstalledVersion = $Matches[1]
            }
        }
    } catch {
        $InstalledPythonExe = $null
        $InstalledVersion = $null
    }
}

Write-Host "`nChecking for the latest stable Python version..."
$LatestVersion = $null
try {
    $releases = Invoke-RestMethod -Uri "https://endoflife.date/api/python.json" -UseBasicParsing -TimeoutSec 10
    $Today = Get-Date
    foreach ($r in $releases) {
        $relDate = [datetime]$r.releaseDate
        if ($relDate -le $Today) {
            $LatestVersion = $r.latest
            break
        }
    }
} catch {
    Write-Host "Warning: Could not fetch latest Python version online. Using fallback."
}

if (-not $LatestVersion) {
    $LatestVersion = "3.12.4"
}

Write-Host "Latest stable Python version online: $LatestVersion"

$ShouldInstall = $false

if ($InstalledPythonExe) {
    Write-Host "Found existing Python installation (version $InstalledVersion) at: $InstalledPythonExe"
    try {
        $currVer = [version]$InstalledVersion
        $latestVer = [version]$LatestVersion
        
        if ($latestVer -gt $currVer) {
            Write-Host "A newer stable version of Python ($LatestVersion) is available."
            if (Ask-YesNo "Do you want to update to the latest stable Python ($LatestVersion)?" -DefaultYes $true) {
                $ShouldInstall = $true
            } else {
                Write-Host "Keeping existing Python version."
            }
        } else {
            Write-Host "Python is up-to-date (version $InstalledVersion)."
        }
    } catch {
        Write-Host "Could not compare versions. Existing: $InstalledVersion, Latest: $LatestVersion"
        if (Ask-YesNo "Do you want to install/update Python to version $LatestVersion?" -DefaultYes $false) {
            $ShouldInstall = $true
        }
    }
} else {
    Write-Host "No Python installation detected on your system."
    $ShouldInstall = $true
}

$PythonDir = "$BaseDir\python"
$PythonExe = $null
$PythonWExe = $null

if ($ShouldInstall) {
    Write-Host "`n[1/5] Downloading Portable Python $LatestVersion..."
    $DownloadUrl = "https://www.python.org/ftp/python/$LatestVersion/python-$LatestVersion-embed-amd64.zip"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile "python.zip"
    
    Write-Host "Extracting Python..."
    if (Test-Path $PythonDir) {
        Write-Host "Cleaning up old Python directory..."
        Remove-Item -Path $PythonDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
    Expand-Archive -Path "python.zip" -DestinationPath $PythonDir -Force
    Remove-Item "python.zip"

    Write-Host "Configuring Python environment..."
    $PthFile = Get-ChildItem -Path $PythonDir -Filter "*._pth" | Select-Object -First 1
    if ($PthFile) {
        (Get-Content $PthFile.FullName) -replace '#import site', 'import site' | Set-Content $PthFile.FullName
    }

    Write-Host "Installing pip..."
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "get-pip.py"
    & "$PythonDir\python.exe" get-pip.py --index-url https://pypi.org/simple/
    Remove-Item "get-pip.py"
    
    $PythonExe = "$PythonDir\python.exe"
    $PythonWExe = "$PythonDir\pythonw.exe"
} else {
    Write-Host "`n[1/5] Using existing Python installation."
    $PythonExe = $InstalledPythonExe
    $SelectedPythonDir = Split-Path $PythonExe
    $PythonWExe = Join-Path $SelectedPythonDir "pythonw.exe"
    if (-not (Test-Path $PythonWExe)) {
        $PythonWExe = $PythonExe
    }
}

# Ensure pip is installed for the selected Python
try {
    & $PythonExe -m pip --version >$null 2>&1
    $HasPip = ($LastExitCode -eq 0)
} catch {
    $HasPip = $false
}

if (-not $HasPip) {
    Write-Host "pip is not installed for this Python. Attempting to install pip..."
    try {
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "get-pip.py"
        & $PythonExe get-pip.py --index-url https://pypi.org/simple/
        Remove-Item "get-pip.py"
    } catch {
        Write-Host "Warning: Failed to install pip automatically. You may need to install it manually."
    }
}

# 2. Install Python Dependencies
Write-Host "`n[2/5] Checking Required Libraries..."
$MissingLibs = @()
$OutdatedLibs = @()
$RequiredLibs = @("playwright", "fastapi", "uvicorn", "aiosqlite", "pydantic", "jinja2", "python-multipart")

try {
    # Get list of installed packages
    $InstalledJson = & $PythonExe -m pip list --format json 2>&1
    if ($LastExitCode -eq 0 -and -not [string]::IsNullOrEmpty($InstalledJson)) {
        $Installed = @(ConvertFrom-Json $InstalledJson)
        $InstalledNames = @()
        if ($Installed) {
            $InstalledNames = $Installed | ForEach-Object { $_.name.ToLower() }
        }
        
        foreach ($lib in $RequiredLibs) {
            # Map libraries to their import names if different, but here we check pip package names
            if ($InstalledNames -notcontains $lib.ToLower()) {
                $MissingLibs += $lib
            }
        }
        
        # If nothing is missing, check if any are outdated
        if ($MissingLibs.Count -eq 0) {
            $OutdatedJson = & $PythonExe -m pip list --outdated --format json 2>&1
            if ($LastExitCode -eq 0 -and -not [string]::IsNullOrEmpty($OutdatedJson)) {
                $Outdated = @(ConvertFrom-Json $OutdatedJson)
                if ($Outdated) {
                    foreach ($pkg in $Outdated) {
                        if ($RequiredLibs -contains $pkg.name.ToLower() -or $RequiredLibs -contains $pkg.name) {
                            $OutdatedLibs += $pkg
                        }
                    }
                }
            }
        }
    } else {
        $MissingLibs = $RequiredLibs
    }
} catch {
    $MissingLibs = $RequiredLibs
}

$ShouldInstallLibs = $false

if ($MissingLibs.Count -gt 0) {
    Write-Host "Missing required libraries: $($MissingLibs -join ', ')"
    Write-Host "Automatically installing missing libraries..."
    $ShouldInstallLibs = $true
} elseif ($OutdatedLibs.Count -gt 0) {
    Write-Host "The following required libraries have newer versions available:"
    foreach ($lib in $OutdatedLibs) {
        Write-Host " - $($lib.name) (installed: $($lib.version), latest: $($lib.latest_version))"
    }
    if (Ask-YesNo "Do you want to update all of these libraries?" -DefaultYes $true) {
        $ShouldInstallLibs = $true
    } else {
        Write-Host "Continuing with current versions."
    }
} else {
    Write-Host "All library dependencies are installed and up-to-date."
}

if ($ShouldInstallLibs) {
    Write-Host "Installing/Updating Required Libraries..."
    & $PythonExe -m pip install -r "$BaseDir\requirements.txt" --index-url https://pypi.org/simple/
}

# 3. Install Playwright Browsers
Write-Host "`n[3/5] Checking Playwright Browsers..."
$BrowsersDir = "$BaseDir\playwright_browsers"
if (-Not (Test-Path $BrowsersDir)) {
    New-Item -ItemType Directory -Force -Path $BrowsersDir | Out-Null
}

$HasChromium = $false
$ChromiumFolders = Get-ChildItem -Path $BrowsersDir -Filter "chromium-*" -Directory
if ($ChromiumFolders) {
    $HasChromium = $true
}

$ShouldInstallChromium = $true
if ($HasChromium) {
    Write-Host "Playwright Chromium browser is already installed."
    # If we just updated libraries, we should probably check if Chromium needs update,
    # but we can ask the user if they want to check for updates or reinstall Playwright Chromium.
    if (-not (Ask-YesNo "Do you want to check for updates or reinstall Playwright Chromium browser?" -DefaultYes $false)) {
        $ShouldInstallChromium = $false
        Write-Host "Skipping Playwright Chromium browser installation/update."
    }
}

if ($ShouldInstallChromium) {
    Write-Host "Installing/Updating Playwright Browsers (This may take a minute)..."
    $env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
    & $PythonExe -m playwright install chromium
}

# 4. Create Desktop Shortcut
Write-Host "`n[4/5] Creating Desktop Shortcut..."
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\Automation Platform.lnk")
$Shortcut.TargetPath = $PythonWExe
$Shortcut.Arguments = "`"$BaseDir\main.py`""
$Shortcut.WorkingDirectory = $BaseDir
if (Test-Path "$BaseDir\app_icon.ico") {
    $Shortcut.IconLocation = "$BaseDir\app_icon.ico"
}
$Shortcut.Description = "Automation Platform Web App"
$Shortcut.Save()

# 5. Launch Application
Write-Host "`n[5/5] Launching the Application..."
Start-Process -FilePath $PythonWExe -ArgumentList "`"$BaseDir\main.py`"" -WorkingDirectory $BaseDir

Write-Host "`nInstallation Complete! The app is starting in the background."
Write-Host "Your browser will automatically open the dashboard shortly."
Start-Sleep -Seconds 3
