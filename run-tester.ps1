$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path ".venv")) {
    throw "Missing .venv. Run .\setup-tester.ps1 first."
}

& ".\.venv\Scripts\python.exe" -m hand_controller --ui-live --tuning ".\tuning.testing.json"
