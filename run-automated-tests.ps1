$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$venvPython = ".\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython ".\automated_tests\run_all_tests.py"
} else {
    python ".\automated_tests\run_all_tests.py"
}
