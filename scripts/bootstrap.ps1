param(
  [switch]$IncludeInference,
  [switch]$PrepareModel
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python was not found on PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm was not found on PATH."
}

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
  throw "Virtual environment Python was not found at $PythonExe."
}

& $PythonExe -m pip install --upgrade pip

$PythonSpec = ".[dev]"
if ($IncludeInference) {
  $PythonSpec = ".[dev,inference]"
}

& $PythonExe -m pip install -e $PythonSpec
npm install

if ($PrepareModel) {
  & $PythonExe scripts/setup_huggingface.py
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Activate the environment with:"
Write-Host "  .venv\Scripts\Activate.ps1"
Write-Host "Run the app with:"
Write-Host "  python scripts/run_dev.py"
