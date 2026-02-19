# build.ps1 - Build Open Recruiter as a standalone Windows desktop app
# Run from the project root: .\build.ps1
#
# Prerequisites:
#   - Node.js / npm
#   - uv (Python package manager)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "=== Open Recruiter - Windows Build ===" -ForegroundColor Cyan
Write-Host ""

# -- Step 1: Build frontend ------------------------------------------------

Write-Host "[1/5] Building frontend..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\frontend"
npm ci
npm run build
if (-not (Test-Path "dist\index.html")) {
    Write-Error "Frontend build failed - dist/index.html not found"
    exit 1
}
Pop-Location
Write-Host "  Frontend built successfully." -ForegroundColor Green

# -- Step 2: Pre-download embedding model ----------------------------------

Write-Host "[2/5] Pre-downloading embedding model..." -ForegroundColor Yellow
$ModelsDir = "$ProjectRoot\backend\models"
if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}

Push-Location "$ProjectRoot\backend"
uv run python -c "import os; os.environ['SENTENCE_TRANSFORMERS_HOME']='models'; from sentence_transformers import SentenceTransformer; print('Downloading BAAI/bge-small-en-v1.5...'); SentenceTransformer('BAAI/bge-small-en-v1.5'); print('Model ready.')"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Model download failed"
    exit 1
}
Pop-Location
Write-Host "  Embedding model ready." -ForegroundColor Green

# -- Step 3: Bundle backend with PyInstaller --------------------------------

Write-Host "[3/5] Bundling backend with PyInstaller..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"

if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

uv run pyinstaller open_recruiter.spec --noconfirm
if (-not (Test-Path "dist\backend\backend.exe")) {
    Write-Error "PyInstaller build failed - dist/backend/backend.exe not found"
    exit 1
}
Pop-Location
Write-Host "  Backend bundled successfully." -ForegroundColor Green

# -- Step 4: Compile Electron TypeScript ------------------------------------

Write-Host "[4/5] Compiling Electron TypeScript..." -ForegroundColor Yellow
Push-Location "$ProjectRoot"
npm ci
npm run build:electron
Pop-Location
Write-Host "  Electron compiled." -ForegroundColor Green

# -- Step 5: Package with electron-builder ----------------------------------

Write-Host "[5/5] Packaging with electron-builder..." -ForegroundColor Yellow
Push-Location "$ProjectRoot"
npx electron-builder --config electron/electron-builder.json --win
Pop-Location
Write-Host "  Package created." -ForegroundColor Green

# -- Done -------------------------------------------------------------------

Write-Host ""
Write-Host "=== Build complete! ===" -ForegroundColor Cyan
Write-Host "Output: $ProjectRoot\release\" -ForegroundColor White
Write-Host ""
Write-Host "Look for the installer in the release/ directory." -ForegroundColor White
