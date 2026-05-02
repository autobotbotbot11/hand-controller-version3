$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -U pip
& ".\.venv\Scripts\python.exe" -m pip install -r ".\requirements.txt"
& ".\.venv\Scripts\python.exe" -m pip install mediapipe==0.10.21 --no-deps

Write-Host ""
Write-Host "Tester environment is ready."
Write-Host "Run .\run-tester.ps1 to start the app."
