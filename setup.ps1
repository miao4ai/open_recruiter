#!/usr/bin/env pwsh
# ============================================================================
#  Open Recruiter — Windows Fully Automated Setup
#  Run:  powershell -ExecutionPolicy Bypass -File setup.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Open Recruiter — Automated Setup"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if winget is available (Windows 10 1709+ / Windows 11)
$hasWinget = $false
try { $null = Get-Command winget -ErrorAction Stop; $hasWinget = $true } catch {}

# ── Helper: prompt to install ─────────────────────────────────────────────

function Ask-Install {
    param([string]$Name)
    Write-Host "  $Name not found. Install automatically? (Y/n): " -ForegroundColor Cyan -NoNewline
    $ans = Read-Host
    return ($ans -ne "n" -and $ans -ne "N")
}

# ── 1. Check / Install Python ────────────────────────────────────────────

Write-Host "[1/6] Checking Python 3.11+..." -ForegroundColor Yellow
$python = $null
foreach ($cmd in @("python3", "python", "py")) {
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
    if ($hasWinget -and (Ask-Install "Python 3.12")) {
        Write-Host "  Installing Python via winget..." -ForegroundColor Cyan
        winget install --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        # Re-check
        foreach ($cmd in @("python3", "python", "py")) {
            try {
                $ver = & $cmd --version 2>&1
                if ($ver -match "Python 3\.(\d+)") {
                    if ([int]$Matches[1] -ge 11) {
                        $python = $cmd
                        Write-Host "  Installed: $ver" -ForegroundColor Green
                        break
                    }
                }
            } catch {}
        }
    }
    if (-not $python) {
        Write-Host "  ERROR: Python 3.11+ is required." -ForegroundColor Red
        Write-Host "  Download: https://www.python.org/downloads/" -ForegroundColor Red
        Write-Host "  IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Red
        exit 1
    }
}

# ── 2. Check / Install uv ────────────────────────────────────────────────

Write-Host "[2/6] Checking uv..." -ForegroundColor Yellow
$hasUv = $false
try { $null = & uv --version 2>&1; $hasUv = $true; Write-Host "  OK: $(uv --version)" -ForegroundColor Green } catch {}

if (-not $hasUv) {
    Write-Host "  Installing uv..." -ForegroundColor Cyan
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    try {
        $null = & uv --version 2>&1
        Write-Host "  Installed: $(uv --version)" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: uv installation failed. See https://docs.astral.sh/uv/" -ForegroundColor Red
        exit 1
    }
}

# ── 3. Check / Install Node.js ───────────────────────────────────────────

Write-Host "[3/6] Checking Node.js 18+..." -ForegroundColor Yellow
$hasNode = $false
try {
    $nodeVer = & node --version 2>&1
    if ($nodeVer -match "v(\d+)") {
        if ([int]$Matches[1] -ge 18) {
            Write-Host "  OK: node $nodeVer" -ForegroundColor Green
            $hasNode = $true
        }
    }
} catch {}

if (-not $hasNode) {
    if ($hasWinget -and (Ask-Install "Node.js 22 LTS")) {
        Write-Host "  Installing Node.js via winget..." -ForegroundColor Cyan
        winget install --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        try {
            $nodeVer = & node --version 2>&1
            Write-Host "  Installed: node $nodeVer" -ForegroundColor Green
            $hasNode = $true
        } catch {}
    }
    if (-not $hasNode) {
        Write-Host "  ERROR: Node.js 18+ is required." -ForegroundColor Red
        Write-Host "  Download: https://nodejs.org/" -ForegroundColor Red
        exit 1
    }
}

# ── 4. Install backend dependencies ──────────────────────────────────────

Write-Host "[4/6] Installing backend dependencies (Python)..." -ForegroundColor Yellow
Push-Location "$ROOT\backend"
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Backend dependency installation failed." -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "  Backend OK" -ForegroundColor Green
Pop-Location

# ── 5. Install frontend dependencies ─────────────────────────────────────

Write-Host "[5/6] Installing frontend dependencies (Node)..." -ForegroundColor Yellow
Push-Location "$ROOT\frontend"
& npm install --silent 2>&1 | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Frontend dependency installation failed." -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "  Frontend OK" -ForegroundColor Green
Pop-Location

# ── 6. Configure .env ────────────────────────────────────────────────────

Write-Host "[6/6] Configuring environment..." -ForegroundColor Yellow
$envFile = "$ROOT\backend\.env"
$skipEnv = $false

if (Test-Path $envFile) {
    Write-Host "  .env already exists. Overwrite? (y/N): " -ForegroundColor Cyan -NoNewline
    $overwrite = Read-Host
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "  Keeping existing .env" -ForegroundColor Green
        $skipEnv = $true
    }
}

if (-not $skipEnv) {
    Write-Host ""
    Write-Host "  --- LLM Configuration ---" -ForegroundColor Cyan
    Write-Host "  Choose LLM provider:"
    Write-Host "    1) Anthropic (Claude)  [default]"
    Write-Host "    2) OpenAI (GPT)"
    $llmChoice = Read-Host "  Enter 1 or 2"
    if ($llmChoice -eq "2") {
        $llmProvider = "openai"
        Write-Host "  OpenAI API Key (sk-...): " -NoNewline
        $llmKey = Read-Host
        $keyLine = "OPENAI_API_KEY=$llmKey"
    } else {
        $llmProvider = "anthropic"
        Write-Host "  Anthropic API Key (sk-ant-...): " -NoNewline
        $llmKey = Read-Host
        $keyLine = "ANTHROPIC_API_KEY=$llmKey"
    }

    Write-Host ""
    Write-Host "  --- Slack Configuration (optional, press Enter to skip) ---" -ForegroundColor Cyan
    Write-Host "  Slack Bot Token (xoxb-...): " -NoNewline
    $slackBot = Read-Host
    Write-Host "  Slack Signing Secret: " -NoNewline
    $slackSecret = Read-Host
    Write-Host "  Slack Intake Channel ID (C...): " -NoNewline
    $slackChannel = Read-Host

    $envContent = @"
# === Open Recruiter Configuration ===

# LLM Provider
LLM_PROVIDER=$llmProvider
$keyLine

# Slack Integration (optional)
SLACK_BOT_TOKEN=$slackBot
SLACK_SIGNING_SECRET=$slackSecret
SLACK_INTAKE_CHANNEL=$slackChannel
"@

    Set-Content -Path $envFile -Value $envContent -Encoding UTF8
    Write-Host "  .env written to $envFile" -ForegroundColor Green
}

# Create uploads directory
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
