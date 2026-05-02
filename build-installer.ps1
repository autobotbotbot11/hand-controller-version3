param(
    [string]$Version = "0.1.0-preview",
    [string]$Publisher = "Hand Controller Project"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

& (Join-Path $repoRoot "build-portable.ps1")

$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)

$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $isccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($isccCmd) {
        $iscc = $isccCmd.Source
    }
}

if (-not $iscc) {
    throw @"
Inno Setup 6 compiler was not found.
Install it with:
  winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
"@
}

$releaseDir = Join-Path $repoRoot "release\installer"
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

Write-Host "Building Hand Controller installer..."
& $iscc "/DMyAppVersion=$Version" "/DMyAppPublisher=$Publisher" (Join-Path $repoRoot "hand_controller_installer.iss")

Write-Host ""
Write-Host "Installer is ready:"
Write-Host "  $releaseDir"
