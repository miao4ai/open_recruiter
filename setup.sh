#!/usr/bin/env bash
# ============================================================================
#  Open Recruiter — Linux / macOS Automated Setup
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

# ── 1. Check Python ──────────────────────────────────────────────────────

echo -e "${YELLOW}[1/6] Checking Python...${NC}"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        minor=$(echo "$ver" | grep -oP 'Python 3\.\K\d+')
        if [ -n "$minor" ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            echo -e "  ${GREEN}OK: $ver${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}ERROR: Python 3.11+ is required.${NC}"
    echo "  Install: https://www.python.org/downloads/"
    echo "  Or: sudo apt install python3 (Debian/Ubuntu)"
    echo "      brew install python@3.12 (macOS)"
    exit 1
fi

# ── 2. Check / Install uv ────────────────────────────────────────────────

echo -e "${YELLOW}[2/6] Checking uv (Python package manager)...${NC}"
if command -v uv &>/dev/null; then
    echo -e "  ${GREEN}OK: $(uv --version)${NC}"
else
    echo -e "  ${CYAN}Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the env so uv is available
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if command -v uv &>/dev/null; then
        echo -e "  ${GREEN}Installed: $(uv --version)${NC}"
    else
        echo -e "  ${RED}ERROR: uv installation failed.${NC}"
        echo "  Install manually: https://docs.astral.sh/uv/"
        exit 1
    fi
fi

# ── 3. Check Node.js ─────────────────────────────────────────────────────

echo -e "${YELLOW}[3/6] Checking Node.js...${NC}"
if command -v node &>/dev/null; then
    NODE_VER=$(node --version)
    NODE_MAJOR=$(echo "$NODE_VER" | grep -oP 'v\K\d+')
    if [ "$NODE_MAJOR" -ge 18 ]; then
        echo -e "  ${GREEN}OK: node $NODE_VER${NC}"
    else
        echo -e "  ${RED}ERROR: Node.js 18+ required (found $NODE_VER).${NC}"
        exit 1
    fi
else
    echo -e "  ${RED}ERROR: Node.js 18+ is required.${NC}"
    echo "  Install: https://nodejs.org/"
    echo "  Or: sudo apt install nodejs npm (Debian/Ubuntu)"
    echo "      brew install node (macOS)"
    exit 1
fi

# ── 4. Install backend dependencies ──────────────────────────────────────

echo -e "${YELLOW}[4/6] Installing backend dependencies...${NC}"
cd "$ROOT/backend"
uv sync
echo -e "  ${GREEN}Backend OK${NC}"

# ── 5. Install frontend dependencies ─────────────────────────────────────

echo -e "${YELLOW}[5/6] Installing frontend dependencies...${NC}"
cd "$ROOT/frontend"
npm install --silent
echo -e "  ${GREEN}Frontend OK${NC}"

cd "$ROOT"

# ── 6. Configure .env ────────────────────────────────────────────────────

echo -e "${YELLOW}[6/6] Configuring environment...${NC}"
ENV_FILE="$ROOT/backend/.env"

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
