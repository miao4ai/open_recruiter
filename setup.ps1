#!/usr/bin/env pwsh
# ============================================================================
#  Open Recruiter — Windows Automated Setup
#  Run:  powershell -ExecutionPolicy Bypass -File setup.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Open Recruiter — Automated Setup"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Python ──────────────────────────────────────────────────────

Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
$python = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 11) {
                $python = $cmd
                Write-Host "  OK: $ver" -ForegroundColor Green
                break
            }
        }
    } catch {}
}
if (-not $python) {
    Write-Host "  ERROR: Python 3.11+ is required." -ForegroundColor Red
    Write-Host "  Download from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "  Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Red
    exit 1
}

# ── 2. Check / Install uv ────────────────────────────────────────────────

Write-Host "[2/6] Checking uv (Python package manager)..." -ForegroundColor Yellow
$hasUv = $false
try {
    $uvVer = & uv --version 2>&1
    Write-Host "  OK: $uvVer" -ForegroundColor Green
    $hasUv = $true
} catch {}

if (-not $hasUv) {
    Write-Host "  Installing uv..." -ForegroundColor Cyan
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    try {
        $uvVer = & uv --version 2>&1
        Write-Host "  Installed: $uvVer" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: uv installation failed. Install manually: https://docs.astral.sh/uv/" -ForegroundColor Red
        exit 1
    }
}

# ── 3. Check Node.js ─────────────────────────────────────────────────────

Write-Host "[3/6] Checking Node.js..." -ForegroundColor Yellow
$hasNode = $false
try {
    $nodeVer = & node --version 2>&1
    if ($nodeVer -match "v(\d+)") {
        $major = [int]$Matches[1]
        if ($major -ge 18) {
            Write-Host "  OK: node $nodeVer" -ForegroundColor Green
            $hasNode = $true
        }
    }
} catch {}

if (-not $hasNode) {
    Write-Host "  ERROR: Node.js 18+ is required." -ForegroundColor Red
    Write-Host "  Download from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# ── 4. Install dependencies ──────────────────────────────────────────────

Write-Host "[4/6] Installing backend dependencies..." -ForegroundColor Yellow
Push-Location "$ROOT\backend"
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Backend dependency installation failed." -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  Backend OK" -ForegroundColor Green
Pop-Location

Write-Host "[5/6] Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location "$ROOT\frontend"
& npm install --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Frontend dependency installation failed." -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  Frontend OK" -ForegroundColor Green
Pop-Location

# ── 5. Configure .env ────────────────────────────────────────────────────

Write-Host "[6/6] Configuring environment..." -ForegroundColor Yellow
$envFile = "$ROOT\backend\.env"

if (Test-Path $envFile) {
    Write-Host "  .env already exists. Overwrite? (y/N): " -ForegroundColor Cyan -NoNewline
    $overwrite = Read-Host
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "  Keeping existing .env" -ForegroundColor Green
        goto done
    }
}

Write-Host ""
Write-Host "  --- LLM Configuration ---" -ForegroundColor Cyan
Write-Host "  Choose LLM provider:"
Write-Host "    1) Anthropic (Claude)  [default]"
Write-Host "    2) OpenAI (GPT)"
$llmChoice = Read-Host "  Enter 1 or 2"
if ($llmChoice -eq "2") {
    $llmProvider = "openai"
    $keyPrompt = "  OpenAI API Key (sk-...): "
    $keyName = "OPENAI_API_KEY"
} else {
    $llmProvider = "anthropic"
    $keyPrompt = "  Anthropic API Key (sk-ant-...): "
    $keyName = "ANTHROPIC_API_KEY"
}
Write-Host $keyPrompt -NoNewline
$llmKey = Read-Host

Write-Host ""
Write-Host "  --- Slack Configuration (optional, press Enter to skip) ---" -ForegroundColor Cyan
Write-Host "  Slack Bot Token (xoxb-...): " -NoNewline
$slackBot = Read-Host
Write-Host "  Slack Signing Secret: " -NoNewline
$slackSecret = Read-Host
Write-Host "  Slack Intake Channel ID (C...): " -NoNewline
$slackChannel = Read-Host

# Write .env
$envContent = @"
# === Open Recruiter Configuration ===

# LLM Provider
LLM_PROVIDER=$llmProvider
$keyName=$llmKey

# Slack Integration (optional)
SLACK_BOT_TOKEN=$slackBot
SLACK_SIGNING_SECRET=$slackSecret
SLACK_INTAKE_CHANNEL=$slackChannel
"@

Set-Content -Path $envFile -Value $envContent -Encoding UTF8
Write-Host "  .env written to $envFile" -ForegroundColor Green

:done

# ── Create uploads directory ─────────────────────────────────────────────
$uploadsDir = "$ROOT\backend\uploads"
if (-not (Test-Path $uploadsDir)) {
    New-Item -ItemType Directory -Path $uploadsDir -Force | Out-Null
}

# ── Done ─────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup complete!"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To start Open Recruiter:" -ForegroundColor Cyan
Write-Host "    .\start.ps1" -ForegroundColor White
Write-Host ""
Write-Host "  Or manually:" -ForegroundColor Cyan
Write-Host "    Terminal 1:  cd backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000 --reload"
Write-Host "    Terminal 2:  cd frontend && npx vite"
Write-Host "    Open:        http://localhost:5173"
Write-Host ""

Write-Host "  Start now? (Y/n): " -ForegroundColor Cyan -NoNewline
$startNow = Read-Host
if ($startNow -ne "n" -and $startNow -ne "N") {
    & "$ROOT\start.ps1"
}
