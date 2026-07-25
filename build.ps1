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

# Optional: build the Windows installer if Inno Setup (iscc) is available.
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches.Groups[1].Value
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if ($iscc) {
    Write-Host "==> Building Windows installer (Inno Setup) for v$version"
    & iscc "/DAppVersion=$version" packaging\windows\cetus.iss
    Write-Host "Installer: packaging\windows\Output\CETUS-Setup-$version.exe"
} else {
    Write-Host "(Inno Setup 'iscc' not found; skipping installer. See packaging\README.md.)"
}

Write-Host ""
Write-Host "Done. dist\CETUS.exe is the portable build; the installer targets Program Files."
