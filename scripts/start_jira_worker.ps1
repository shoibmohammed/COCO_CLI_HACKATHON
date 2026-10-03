# Start the Local Jira Worker
# Usage: .\scripts\start_jira_worker.ps1

param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$WorkerDir = Join-Path $ProjectRoot "local_jira_worker"
$VenvPython = Join-Path $WorkerDir ".venv\Scripts\python.exe"
$WorkerScript = Join-Path $WorkerDir "worker.py"
$PidFile = Join-Path $WorkerDir ".worker.pid"

# Check if already running
if (Test-Path $PidFile) {
    $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Worker already running (PID: $existingPid)" -ForegroundColor Yellow
            exit 0
        }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

# Determine Python executable
if (Test-Path $VenvPython) {
    $python = $VenvPython
} else {
    $python = "python"
    Write-Host "WARNING: Venv not found. Using system Python. Run bootstrap_judge.ps1 first." -ForegroundColor Yellow
}

# Load .env
$envFile = Join-Path $WorkerDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim().Replace("export ", "")
            $val = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

Write-Host "Starting Local Jira Worker..." -ForegroundColor Cyan
$process = Start-Process -FilePath $python -ArgumentList $WorkerScript -WorkingDirectory $WorkerDir -PassThru -WindowStyle Normal
$process.Id | Out-File $PidFile -Encoding ascii

Write-Host "Worker started (PID: $($process.Id))" -ForegroundColor Green
Write-Host "To stop: .\scripts\stop_jira_worker.ps1"
