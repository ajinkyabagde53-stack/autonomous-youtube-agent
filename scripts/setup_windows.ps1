Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$target = "D:\AI\autonomous-youtube-agent"
if (-not (Test-Path "D:\AI")) { New-Item -ItemType Directory -Path "D:\AI" | Out-Null }
if (-not (Test-Path $target)) { git clone "https://github.com/ajinkyabagde53-stack/autonomous-youtube-agent.git" $target } else { Set-Location $target; git pull }
Set-Location $target
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python was not found on PATH. Install Python 3.11+ and rerun." }
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
New-Item -ItemType Directory -Force -Path "data\assets" | Out-Null
New-Item -ItemType Directory -Force -Path "data\research" | Out-Null
New-Item -ItemType Directory -Force -Path "data\outputs" | Out-Null
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run .\scripts\start_dashboard.ps1 then open http://localhost:3000"
