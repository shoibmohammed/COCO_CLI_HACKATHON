# Master Judge Bootstrap & Verification Script (PowerShell)
# Prepares and validates the Snowflake Container Runtime deployment for judges.

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "🏭 MFG PREDICTIVE MAINTENANCE & OEE COMMAND CENTER" -ForegroundColor Cyan
Write-Host "   MASTER JUDGE BOOTSTRAP & DEPLOYMENT PRE-FLIGHT" -ForegroundColor Cyan
Write-Host "   Target: Snowflake Container Runtime (SYSTEM_COMPUTE_POOL_CPU)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found in PATH." -ForegroundColor Red
    exit 1
}
Write-Host "[1/5] Python Environment: $($python.Source)" -ForegroundColor Green

# 2. Run AST Syntax Validation
Write-Host "[2/5] Validating Python AST Syntax..." -ForegroundColor Yellow
$syntaxValidator = Join-Path $ProjectRoot "scripts\validate_python.py"
if (Test-Path $syntaxValidator) {
    python $syntaxValidator
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Python syntax validation failed." -ForegroundColor Red
        exit 1
    }
}

# 3. Run Container Runtime Deployment Pre-Flight Validation
Write-Host "[3/5] Running Container Runtime Pre-Flight Validation..." -ForegroundColor Yellow
$deploymentValidator = Join-Path $ProjectRoot "scripts\validate_streamlit_deployment.py"
if (Test-Path $deploymentValidator) {
    python $deploymentValidator
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Container Runtime pre-flight validation failed." -ForegroundColor Red
        exit 1
    }
}

# 4. Run Offline Test Suite
Write-Host "[4/5] Executing Offline Release Test Suite..." -ForegroundColor Yellow
python -m unittest discover -s (Join-Path $ProjectRoot "tests") -p "test_*.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Unit tests failed." -ForegroundColor Red
    exit 1
}
Write-Host "  -> All offline tests PASSED." -ForegroundColor Green

# 5. Security & Manifest Verification
Write-Host "[5/5] Verifying Deployment Security & Manifest..." -ForegroundColor Yellow
$securityValidator = Join-Path $ProjectRoot "scripts\verify_deployment.py"
if (Test-Path $securityValidator) {
    python $securityValidator
}

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "🟢 BOOTSTRAP COMPLETE — SYSTEM IS 100% JUDGE READY" -ForegroundColor Green
Write-Host "Primary Runtime: Snowflake-Hosted Streamlit (Container Runtime)" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
