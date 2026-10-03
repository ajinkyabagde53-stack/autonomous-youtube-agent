param(
    # Where to clone the repository when this script is run from outside a clone.
    [string]$Target = (Join-Path $HOME "autonomous-youtube-agent")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run from inside an existing clone if there is one; otherwise clone to $Target.
$repoRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path (Join-Path $repoRoot "main.py")) {
    Set-Location $repoRoot
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git was not found on PATH." }
    if (Test-Path $Target) {
        Set-Location $Target
        git pull
    } else {
        git clone "https://github.com/ajinkyabagde53-stack/autonomous-youtube-agent.git" $Target
        Set-Location $Target
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Python was not found on PATH. Install Python 3.10+ and rerun." }
$version = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]"3.10") { throw "Python $version found; 3.10 or newer is required." }

python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "Setup complete in $(Get-Location)." -ForegroundColor Green
Write-Host "Add your keys to .env, then run .\scripts\start_dashboard.ps1 and open http://localhost:3000"
