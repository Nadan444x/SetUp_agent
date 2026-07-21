# =============================================================================
#  SetUp Agent — Windows Layer 0 bootstrap
#
#  Run this ONE command in PowerShell on a bare Windows PC; it installs only
#  the prerequisites the smart agent needs (Winget, Python+pipx, Ollama + a model,
#  and this package), then hands off. Safe to re-run any time.
#
#    Powershell:
#      iwr -useb https://raw.githubusercontent.com/Nadan444x/Setup_Agent/main/bootstrap.ps1 | iex
#    Local:
#      powershell -ExecutionPolicy Bypass -File bootstrap.ps1
# =============================================================================
$ErrorActionPreference = "Stop"

$MODEL = if ($env:SETUP_AGENT_MODEL) { $env:SETUP_AGENT_MODEL } else { "qwen2.5:7b" }
$REPO_URL = if ($env:SETUP_AGENT_REPO) { $env:SETUP_AGENT_REPO } else { "https://github.com/Nadan444x/Setup_Agent" }
$REPO_DIR = "$HOME\Projects\Setup_Agent"

function Write-Say($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)  { Write-Host " ✓  $msg" -ForegroundColor Green }
function Write-Skip($msg){ Write-Host " ·  $msg (already present)" -ForegroundColor DarkGray }

# --- 0. Find or clone the repo ------------------------------------------------
if ((Test-Path ".\pyproject.toml") -and (Get-Content ".\pyproject.toml" -Raw) -match 'name = "setup-agent"') {
    $REPO_DIR = (Get-Item .).FullName
} else {
    if (-not (Test-Path $REPO_DIR)) {
        Write-Say "cloning SetUp Agent into $REPO_DIR"
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Say "installing git via winget..."
            winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        }
        git clone $REPO_URL $REPO_DIR
    }
}

# --- 1. Winget check ----------------------------------------------------------
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Skip "Winget (Windows Package Manager)"
} else {
    Write-Say "Winget is not found. Please update App Installer from Microsoft Store or install AppInstaller package."
    exit 1
}

# --- 2. Python 3.11+ & pipx ---------------------------------------------------
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd -and (python -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null)) {
    Write-Skip "Python 3.11+ ($(python --version 2>&1))"
} else {
    Write-Say "installing Python 3.12 via winget"
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Skip "pipx"
} else {
    Write-Say "installing pipx"
    python -m pip install --user pipx
    python -m pipx ensurepath
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# --- 3. Ollama installed + server running -------------------------------------
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Skip "Ollama"
} else {
    Write-Say "installing Ollama via winget"
    winget install --id Ollama.Ollama -e --source winget --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

try {
    $resp = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
    Write-Skip "Ollama server"
} catch {
    Write-Say "starting Ollama app / server..."
    Start-Process ollama -ArgumentList "app" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

# --- 4. Pull local model ------------------------------------------------------
$models = ollama list 2>$null
if ($models -match [regex]::Escape($MODEL)) {
    Write-Skip "model $MODEL"
} else {
    Write-Say "pulling model $MODEL (a few GB — one-time download)"
    ollama pull $MODEL
}

# --- 5. Install setup-agent package -------------------------------------------
if (Get-Command setup-agent -ErrorAction SilentlyContinue) {
    Write-Say "updating setup-agent from $REPO_DIR"
    pipx uninstall setup-agent 2>$null
    pipx install $REPO_DIR
} else {
    Write-Say "installing setup-agent from $REPO_DIR"
    pipx install $REPO_DIR
}

Write-Ok "setup-agent installed!"

# --- 6. Handoff ---------------------------------------------------------------
Write-Host "`n Prerequisites ready. Now let the smart agent take over:`n" -ForegroundColor Green
Write-Host "   setup-agent scan     # generate Setup.md from this Windows PC"
Write-Host "   setup-agent doctor   # verify everything is wired up"
Write-Host "   setup-agent setup    # provision the machine from Setup.md`n"
