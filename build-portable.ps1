$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing .venv. Run .\setup-tester.ps1 first."
}

$pyinstallerExe = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstallerExe)) {
    Write-Host "PyInstaller not found in .venv. Installing PyInstaller 6.16.0..."
    & $python -m pip install pyinstaller==6.16.0
}

Write-Host "Building portable HandController app..."
& $python -m PyInstaller --noconfirm --clean ".\hand_controller_portable.spec"

$distDir = Join-Path $repoRoot "dist\HandController"
if (-not (Test-Path $distDir)) {
    throw "Build finished but dist\HandController was not created."
}

$defaultTuning = Join-Path $repoRoot "tuning.testing.json"
$portableTuning = Join-Path $distDir "tuning.local.json"
$portableLog = Join-Path $distDir "HandController.log"
$portableMarker = Join-Path $distDir "HandController.diagnostics"
if (Test-Path $defaultTuning) {
    Copy-Item $defaultTuning $portableTuning -Force
    Write-Host "Copied tuning.testing.json to dist\HandController\tuning.local.json"
}
if (Test-Path $portableLog) {
    Remove-Item $portableLog -Force
}
if (Test-Path $portableMarker) {
    Remove-Item $portableMarker -Force
}

Write-Host ""
Write-Host "Portable app is ready:"
Write-Host "  $distDir"
Write-Host ""
Write-Host "Main executable:"
Write-Host "  $distDir\HandController.exe"
