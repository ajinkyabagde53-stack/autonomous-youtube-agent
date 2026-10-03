Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Run scripts\setup_windows.ps1 first." -ForegroundColor Yellow
  exit 1
}
if (Test-Path ".env") {
  Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
      $parts = $line.Split("=", 2)
      $name = $parts[0].Trim()
      $value = $parts[1].Trim().Trim('"').Trim("'")
      if ($name) { Set-Item -Path "Env:$name" -Value $value }
    }
  }
}
Write-Host "Overseer local control center" -ForegroundColor Cyan
Write-Host "Open http://localhost:3000" -ForegroundColor Green
& ".venv\Scripts\python.exe" "overseer_server.py"
