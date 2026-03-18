#!/usr/bin/env pwsh
# ============================================================================
#  Open Recruiter — Start (Windows)
#  Run:  powershell -ExecutionPolicy Bypass -File start.ps1
# ============================================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  Starting Open Recruiter..." -ForegroundColor Cyan
Write-Host ""

# Start backend in a new window
$backendCmd = "cd '$ROOT\backend'; & '$ROOT\.venv\Scripts\python' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Wait for backend to load (embedding model takes a few seconds)
Write-Host "  Backend starting on http://localhost:8000 ..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start frontend in a new window
$frontendCmd = "cd '$ROOT\frontend'; npx vite --host 0.0.0.0"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Open Recruiter is running!"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Web UI:   http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API:      http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Two new terminal windows have been opened." -ForegroundColor Yellow
Write-Host "  Close them to stop the servers." -ForegroundColor Yellow
Write-Host ""

# Try to open browser
try {
    Start-Process "http://localhost:5173"
} catch {}
