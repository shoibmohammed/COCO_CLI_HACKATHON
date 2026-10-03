# Stop the Local Jira Worker
# Usage: .\scripts\stop_jira_worker.ps1

param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$WorkerDir = Join-Path $ProjectRoot "local_jira_worker"
$PidFile = Join-Path $WorkerDir ".worker.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "No PID file found. Worker may not be running." -ForegroundColor Yellow
    exit 0
}

$pid = Get-Content $PidFile -ErrorAction SilentlyContinue
if (-not $pid) {
    Write-Host "PID file is empty." -ForegroundColor Yellow
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    exit 0
}

$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "Stopping worker (PID: $pid)..." -ForegroundColor Cyan
    Stop-Process -Id $pid -Force
    Start-Sleep -Seconds 2
    Write-Host "Worker stopped." -ForegroundColor Green
} else {
    Write-Host "Process $pid not found (already stopped)." -ForegroundColor Yellow
}

Remove-Item $PidFile -ErrorAction SilentlyContinue
