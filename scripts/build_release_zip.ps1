param(
  [string]$Version = "v0.1.0"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git was not found on PATH."
}

$OutputRoot = Join-Path $RepoRoot "output\releases"
$StageRoot = Join-Path $OutputRoot "stage-$Version"
$ArchivePath = Join-Path $OutputRoot "StableSteering-$Version.zip"

if (Test-Path $StageRoot) {
  Remove-Item -Recurse -Force $StageRoot
}

if (Test-Path $ArchivePath) {
  Remove-Item -Force $ArchivePath
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null

$Files = git ls-files
foreach ($RelativePath in $Files) {
  $SourcePath = Join-Path $RepoRoot $RelativePath
  if (-not (Test-Path $SourcePath)) {
    continue
  }

  $DestinationPath = Join-Path $StageRoot $RelativePath
  $DestinationDir = Split-Path -Parent $DestinationPath
  if ($DestinationDir -and -not (Test-Path $DestinationDir)) {
    New-Item -ItemType Directory -Force -Path $DestinationDir | Out-Null
  }
  Copy-Item -Path $SourcePath -Destination $DestinationPath -Force
}

Compress-Archive -Path (Join-Path $StageRoot "*") -DestinationPath $ArchivePath

Write-Host "Release archive created:"
Write-Host "  $ArchivePath"
