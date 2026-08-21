#!/usr/bin/env bash
# build.sh — Build Open Recruiter desktop app (Linux/macOS)
# Run from anywhere: bash product/scripts/build.sh [mac|linux|auto]
# Default: auto-detects platform via uname
#
# Note: The final Windows .exe must be built on Windows with build.ps1.

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # product/

echo "=== Open Recruiter — Desktop Build ==="
echo ""

# ── Step 1: Build frontend ────────────────────────────────────────────────

echo "[1/4] Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm ci
npm run build
if [ ! -f "dist/index.html" ]; then
    echo "ERROR: Frontend build failed — dist/index.html not found" >&2
    exit 1
fi
echo "  Frontend built successfully."

# ── Step 2: Bundle backend with PyInstaller ───────────────────────────────
# Embeddings run in the Voyage cloud — no local model to pre-download.

echo "[2/4] Bundling backend with PyInstaller..."
cd "$PROJECT_ROOT/backend"
rm -rf dist build
pyinstaller open_recruiter.spec --noconfirm
if [ ! -f "dist/backend/backend" ] && [ ! -f "dist/backend/backend.exe" ]; then
    echo "ERROR: PyInstaller build failed" >&2
    exit 1
fi
echo "  Backend bundled successfully."

# ── Step 3: Compile Electron TypeScript ───────────────────────────────────

echo "[3/4] Compiling Electron TypeScript..."
cd "$PROJECT_ROOT"
npm ci
npm run build:electron
echo "  Electron compiled."

# ── Step 4: Package with electron-builder ─────────────────────────────────

echo "[4/4] Packaging with electron-builder..."
cd "$PROJECT_ROOT"

# Detect platform or accept override: build.sh [mac|linux|auto]
PLATFORM_FLAG=""
TARGET_PLATFORM="${1:-auto}"
case "$TARGET_PLATFORM" in
    mac|macos|darwin)
        PLATFORM_FLAG="--mac"
        ;;
    linux)
        PLATFORM_FLAG="--linux"
        ;;
    auto)
        case "$(uname -s)" in
            Darwin) PLATFORM_FLAG="--mac" ;;
            Linux)  PLATFORM_FLAG="--linux" ;;
        esac
        ;;
    *)
        echo "Unknown platform: $TARGET_PLATFORM (use: mac, linux, or auto)" >&2
        exit 1
        ;;
esac

npx electron-builder --config electron/electron-builder.json $PLATFORM_FLAG
echo "  Package created."

echo ""
echo "=== Build complete! ==="
echo "Output: $PROJECT_ROOT/release/"
