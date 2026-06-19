# Build CETUS on Windows: venv -> deps -> tests -> PyInstaller .exe.
# PyInstaller cannot cross-compile; run this on Windows to produce the .exe.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Creating virtual environment (.venv)"
if (-not (Test-Path .venv)) { python -m venv .venv }

$py = ".\.venv\Scripts\python.exe"

Write-Host "==> Installing dependencies"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements-dev.txt

Write-Host "==> Running tests"
$env:QT_QPA_PLATFORM = "offscreen"
& $py -m pytest -q

Write-Host "==> Building one-file .exe with PyInstaller"
& ".\.venv\Scripts\pyinstaller.exe" --noconfirm cravingcrave.spec

Write-Host ""
Write-Host "Done. dist\CETUS.exe is ready (ship it alongside the media\ folder)."
