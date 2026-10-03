# Bootstrap script for Optional Local Jira Worker environment (Developer Fallback)
# Run once before first use of the local worker.

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$WorkerDir = Join-Path $ProjectRoot "local_jira_worker"
$VenvDir = Join-Path $WorkerDir ".venv"
$RequirementsFile = Join-Path $WorkerDir "requirements.txt"

Write-Host "=== Optional Local Jira Worker Bootstrap (Developer Fallback) ===" -ForegroundColor Cyan
Write-Host "Worker directory: $WorkerDir"

# 1. Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found in PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $($python.Source)"

# 2. Create venv if missing
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create venv." -ForegroundColor Red
        exit 1
    }
    Write-Host "Venv created at $VenvDir" -ForegroundColor Green
} else {
    Write-Host "Venv already exists." -ForegroundColor Green
}

# 3. Install dependencies
$pip = Join-Path $VenvDir "Scripts\pip.exe"
if (Test-Path $RequirementsFile) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & $pip install -r $RequirementsFile --quiet
    Write-Host "Dependencies installed." -ForegroundColor Green
} else {
    Write-Host "Installing snowflake-connector-python and requests..." -ForegroundColor Yellow
    & $pip install snowflake-connector-python requests --quiet
    Write-Host "Core dependencies installed." -ForegroundColor Green
}

# 4. Check .env
$envFile = Join-Path $WorkerDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ""
    Write-Host "NOTE: No .env file found at $envFile (using demo/mock mode)." -ForegroundColor Yellow
    Write-Host "For live Jira synchronization, configure credentials from .env.example."
} else {
    Write-Host ".env file found." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Local Worker Bootstrap complete ===" -ForegroundColor Cyan
Write-Host "To run the worker: & '$VenvDir\Scripts\python.exe' '$WorkerDir\worker.py'"
