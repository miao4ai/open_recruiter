#!/usr/bin/env bash
# ============================================================================
#  Open Recruiter — Linux / macOS Fully Automated Setup
#  Run:  chmod +x setup.sh && ./setup.sh
# ============================================================================

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Open Recruiter — Automated Setup${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Detect OS
OS="unknown"
PKG_INSTALL=""
if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        debian|ubuntu|raspbian) OS="debian"; PKG_INSTALL="sudo apt-get install -y" ;;
        fedora)                 OS="fedora"; PKG_INSTALL="sudo dnf install -y" ;;
        arch|manjaro)           OS="arch";   PKG_INSTALL="sudo pacman -S --noconfirm" ;;
    esac
elif [[ "$(uname)" == "Darwin" ]]; then
    OS="macos"
fi
echo -e "  Detected OS: ${CYAN}${OS}${NC}"
echo ""

# ── Helper: ask to install ────────────────────────────────────────────────

try_install() {
    local name="$1"
    shift
    echo -ne "  ${CYAN}$name not found. Install automatically? (Y/n): ${NC}"
    read -r ans
    if [ "$ans" = "n" ] || [ "$ans" = "N" ]; then
        echo -e "  ${RED}Skipped. Please install $name manually and re-run.${NC}"
        exit 1
    fi
    echo -e "  ${CYAN}Installing $name...${NC}"
    "$@"
}

# ── 1. Python 3.11+ ──────────────────────────────────────────────────────

echo -e "${YELLOW}[1/6] Checking Python 3.11+...${NC}"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        minor=$(echo "$ver" | grep -oP 'Python 3\.\K\d+' || true)
        if [ -n "$minor" ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            echo -e "  ${GREEN}OK: $ver${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    case "$OS" in
        debian)
            try_install "Python 3" $PKG_INSTALL python3 python3-venv python3-dev
            ;;
        fedora)
            try_install "Python 3" $PKG_INSTALL python3 python3-devel
            ;;
        arch)
            try_install "Python 3" $PKG_INSTALL python
            ;;
        macos)
            if command -v brew &>/dev/null; then
                try_install "Python 3" brew install python@3.12
            else
                echo -e "  ${RED}Homebrew not found. Install Python from https://www.python.org/downloads/${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "  ${RED}Cannot auto-install Python on this OS.${NC}"
            echo "  Install Python 3.11+ from https://www.python.org/downloads/"
            exit 1
            ;;
    esac
    # Re-check
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" --version 2>&1)
            minor=$(echo "$ver" | grep -oP 'Python 3\.\K\d+' || true)
            if [ -n "$minor" ] && [ "$minor" -ge 11 ]; then
                PYTHON="$cmd"
                echo -e "  ${GREEN}Installed: $ver${NC}"
                break
            fi
        fi
    done
    if [ -z "$PYTHON" ]; then
        echo -e "  ${RED}Python 3.11+ still not available after install. Check your system.${NC}"
        exit 1
    fi
fi

# ── 2. uv ────────────────────────────────────────────────────────────────

echo -e "${YELLOW}[2/6] Checking uv...${NC}"
if command -v uv &>/dev/null; then
    echo -e "  ${GREEN}OK: $(uv --version)${NC}"
else
    echo -e "  ${CYAN}Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if command -v uv &>/dev/null; then
        echo -e "  ${GREEN}Installed: $(uv --version)${NC}"
    else
        echo -e "  ${RED}uv installation failed. See https://docs.astral.sh/uv/${NC}"
        exit 1
    fi
fi

# ── 3. Node.js 18+ ───────────────────────────────────────────────────────

echo -e "${YELLOW}[3/6] Checking Node.js 18+...${NC}"
NODE_OK=0
if command -v node &>/dev/null; then
    NODE_VER=$(node --version)
    NODE_MAJOR=$(echo "$NODE_VER" | grep -oP 'v\K\d+' || echo "0")
    if [ "$NODE_MAJOR" -ge 18 ]; then
        echo -e "  ${GREEN}OK: node $NODE_VER${NC}"
        NODE_OK=1
    fi
fi

if [ "$NODE_OK" -eq 0 ]; then
    case "$OS" in
        debian)
            # Use NodeSource for up-to-date Node
            try_install "Node.js 20.x" bash -c "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
            ;;
        fedora)
            try_install "Node.js" $PKG_INSTALL nodejs npm
            ;;
        arch)
            try_install "Node.js" $PKG_INSTALL nodejs npm
            ;;
        macos)
            if command -v brew &>/dev/null; then
                try_install "Node.js" brew install node
            else
                echo -e "  ${RED}Homebrew not found. Install Node.js from https://nodejs.org/${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "  ${RED}Cannot auto-install Node.js on this OS.${NC}"
            echo "  Install Node.js 18+ from https://nodejs.org/"
            exit 1
            ;;
    esac
    # Re-check
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version)
        echo -e "  ${GREEN}Installed: node $NODE_VER${NC}"
    else
        echo -e "  ${RED}Node.js still not available after install.${NC}"
        exit 1
    fi
fi

# ── 4. Backend dependencies ──────────────────────────────────────────────

echo -e "${YELLOW}[4/6] Installing backend dependencies (Python)...${NC}"
cd "$ROOT/backend"
uv sync
echo -e "  ${GREEN}Backend OK${NC}"

# ── 5. Frontend dependencies ─────────────────────────────────────────────

echo -e "${YELLOW}[5/6] Installing frontend dependencies (Node)...${NC}"
cd "$ROOT/frontend"
npm install --silent 2>&1 | tail -1
echo -e "  ${GREEN}Frontend OK${NC}"

cd "$ROOT"

# ── 6. Configure .env ────────────────────────────────────────────────────

echo -e "${YELLOW}[6/6] Configuring environment...${NC}"
ENV_FILE="$ROOT/backend/.env"
SKIP_ENV=""

if [ -f "$ENV_FILE" ]; then
    echo -ne "  ${CYAN}.env already exists. Overwrite? (y/N): ${NC}"
    read -r OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo -e "  ${GREEN}Keeping existing .env${NC}"
        SKIP_ENV=1
    fi
fi

if [ -z "$SKIP_ENV" ]; then
    echo ""
    echo -e "  ${CYAN}--- LLM Configuration ---${NC}"
    echo "  Choose LLM provider:"
    echo "    1) Anthropic (Claude)  [default]"
    echo "    2) OpenAI (GPT)"
    echo -n "  Enter 1 or 2: "
    read -r LLM_CHOICE

    if [ "$LLM_CHOICE" = "2" ]; then
        LLM_PROVIDER="openai"
        echo -n "  OpenAI API Key (sk-...): "
        read -r LLM_KEY
        KEY_LINE="OPENAI_API_KEY=$LLM_KEY"
    else
        LLM_PROVIDER="anthropic"
        echo -n "  Anthropic API Key (sk-ant-...): "
        read -r LLM_KEY
        KEY_LINE="ANTHROPIC_API_KEY=$LLM_KEY"
    fi

    echo ""
    echo -e "  ${CYAN}--- Slack Configuration (optional, press Enter to skip) ---${NC}"
    echo -n "  Slack Bot Token (xoxb-...): "
    read -r SLACK_BOT
    echo -n "  Slack Signing Secret: "
    read -r SLACK_SECRET
    echo -n "  Slack Intake Channel ID (C...): "
    read -r SLACK_CHANNEL

    cat > "$ENV_FILE" << EOF
# === Open Recruiter Configuration ===

# LLM Provider
LLM_PROVIDER=$LLM_PROVIDER
$KEY_LINE

# Slack Integration (optional)
SLACK_BOT_TOKEN=$SLACK_BOT
SLACK_SIGNING_SECRET=$SLACK_SECRET
SLACK_INTAKE_CHANNEL=$SLACK_CHANNEL
EOF

    echo -e "  ${GREEN}.env written to $ENV_FILE${NC}"
fi

# Create uploads directory
mkdir -p "$ROOT/backend/uploads"

# ── Done ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${CYAN}To start Open Recruiter:${NC}"
echo "    ./start.sh"
echo ""
echo -e "  ${CYAN}Or manually:${NC}"
echo "    Terminal 1:  cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000 --reload"
echo "    Terminal 2:  cd frontend && npx vite"
echo "    Open:        http://localhost:5173"
echo ""

echo -ne "  ${CYAN}Start now? (Y/n): ${NC}"
read -r START_NOW
if [ "$START_NOW" != "n" ] && [ "$START_NOW" != "N" ]; then
    exec "$ROOT/start.sh"
fi
