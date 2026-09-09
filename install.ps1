# Windows PowerShell One-Line Installer
$ErrorActionPreference = "Stop"

$AppDir = "$env:LOCALAPPDATA\speedtest-abb"
$VenvDir = "$AppDir\venv"
$TargetScript = "$AppDir\speedtest_abb.py"
$WindowsApps = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
$UserBin = "$env:USERPROFILE\bin"
$RawUrl = "https://raw.githubusercontent.com/chr0m/speedtest-abb/main/speedtest_abb.py"

New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

Write-Host "==> Installing Aussie Broadband Speed Test CLI..." -ForegroundColor Cyan

# 1. Download or copy script
if ($PSScriptRoot -and (Test-Path "$PSScriptRoot\speedtest_abb.py")) {
    Copy-Item "$PSScriptRoot\speedtest_abb.py" $TargetScript -Force
} else {
    Write-Host "==> Downloading speedtest_abb.py from GitHub..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $RawUrl -OutFile $TargetScript
}

# 2. Setup venv & rich
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "==> Setting up isolated environment in $VenvDir..." -ForegroundColor Cyan
    python -m venv $VenvDir
} else {
    Write-Host "==> Found existing environment in $VenvDir." -ForegroundColor Cyan
}

Write-Host "==> Ensuring Rich is installed in user environment..." -ForegroundColor Cyan
& $PipExe install --quiet --upgrade rich

# 3. Create cmd launcher in WindowsApps (always in user PATH)
$TargetBinDir = if (Test-Path $WindowsApps) { $WindowsApps } else { $UserBin }
New-Item -ItemType Directory -Force -Path $TargetBinDir | Out-Null
$CmdWrapper = Join-Path $TargetBinDir "speedtest-abb.cmd"

$WrapperContent = @"
@echo off
"$PythonExe" "$TargetScript" %*
"@
Set-Content -Path $CmdWrapper -Value $WrapperContent

Write-Host "`n✓ Installed successfully: $CmdWrapper" -ForegroundColor Green
Write-Host "All set! Run: speedtest-abb`n" -ForegroundColor Green
