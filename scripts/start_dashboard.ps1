Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Host "Run scripts\setup_windows.ps1 first." -ForegroundColor Yellow; exit 1 }
Write-Host "Autonomous YouTube Agent dashboard" -ForegroundColor Cyan
Write-Host "Open http://localhost:3000" -ForegroundColor Green
& ".venv\Scripts\python.exe" -m http.server 3000 --directory web
