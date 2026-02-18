#!/usr/bin/env bash
# ============================================================================
#  Open Recruiter — One-Line Installer for macOS / Linux
#  Usage: curl -fsSL https://raw.githubusercontent.com/miao4ai/open_recruiter/main/install.sh | bash
# ============================================================================

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'
DIM='\033[2m'
ACCENT='\033[38;2;99;102;241m'      # indigo-500
SUCCESS='\033[38;2;34;197;94m'      # green-500
WARN='\033[38;2;250;204;21m'        # yellow-400
ERROR='\033[38;2;239;68;68m'        # red-500
MUTED='\033[38;2;148;163;184m'      # slate-400
CYAN='\033[38;2;6;182;212m'         # cyan-500
NC='\033[0m'

# ── Globals ─────────────────────────────────────────────────────────────────
INSTALL_DIR="${OPEN_RECRUITER_DIR:-$HOME/open-recruiter}"
REPO_URL="${OPEN_RECRUITER_REPO:-https://github.com/miao4ai/open_recruiter.git}"
LLM_PROVIDER=""
LLM_API_KEY=""
LLM_MODEL=""

# ── UI helpers ──────────────────────────────────────────────────────────────
banner() {
    echo ""
    echo -e "${ACCENT}${BOLD}"
    cat << 'LOGO'
    ___                     ____                      _ __
   / _ \ ___  ___  ___    / __ \ ___  ______ __ __ (_) /_ ___  ____
  / // // _ \/ -_)/ _ \  / /_/ // -_)/ __/ // // // / __// -_)/ __/
 /____// .__/\__//_//_/ /_/  \_\\__/ \__/\_,_/ /_//_/\__/ \__//_/
      /_/
LOGO
    echo -e "${NC}"
    echo -e "  ${MUTED}AI-Powered Recruitment Platform — Self-Hosted${NC}"
    echo -e "  ${MUTED}https://github.com/miao4ai/open_recruiter${NC}"
    echo ""
}

info()    { echo -e "  ${MUTED}·${NC} $*"; }
success() { echo -e "  ${SUCCESS}✓${NC} $*"; }
warn()    { echo -e "  ${WARN}!${NC} $*"; }
error()   { echo -e "  ${ERROR}✗${NC} $*"; }

step() {
    local current="$1" total="$2" title="$3"
    echo ""
    echo -e "  ${ACCENT}${BOLD}[$current/$total]${NC} ${BOLD}$title${NC}"
}

separator() {
    echo -e "  ${MUTED}─────────────────────────────────────────────${NC}"
}

# ── OS detection ────────────────────────────────────────────────────────────
OS="unknown"
detect_os() {
    case "$(uname -s)" in
        Darwin) OS="macos" ;;
        Linux)  OS="linux" ;;
    esac

    if [[ "$OS" == "unknown" ]]; then
        error "Unsupported operating system: $(uname -s)"
        echo "  This installer supports macOS and Linux."
        exit 1
    fi
}

# ── Dependency checks ──────────────────────────────────────────────────────
command_exists() { command -v "$1" &>/dev/null; }

check_or_install_homebrew() {
    if command_exists brew; then
        return 0
    fi
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add brew to PATH for Apple Silicon and Intel
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if command_exists brew; then
        success "Homebrew installed"
    else
        error "Homebrew installation failed"
        exit 1
    fi
}

check_git() {
    if command_exists git; then
        success "git $(git --version | awk '{print $3}')"
        return 0
    fi

    warn "git not found. Installing..."
    case "$OS" in
        macos)
            check_or_install_homebrew
            brew install git
            ;;
        linux)
            if command_exists apt-get; then
                sudo apt-get update -qq && sudo apt-get install -y -qq git
            elif command_exists dnf; then
                sudo dnf install -y -q git
            elif command_exists pacman; then
                sudo pacman -S --noconfirm git
            else
                error "Cannot auto-install git. Please install it manually."
                exit 1
            fi
            ;;
    esac

    if command_exists git; then
        success "git installed"
    else
        error "git installation failed"
        exit 1
    fi
}

check_python() {
    local python_cmd=""
    for cmd in python3 python; do
        if command_exists "$cmd"; then
            local ver
            ver="$($cmd --version 2>&1)"
            local minor
            minor=$(echo "$ver" | sed -n 's/Python 3\.\([0-9]*\).*/\1/p')
            if [[ -n "$minor" ]] && [[ "$minor" -ge 11 ]]; then
                python_cmd="$cmd"
                success "$ver"
                return 0
            fi
        fi
    done

    warn "Python 3.11+ not found. Installing..."
    case "$OS" in
        macos)
            check_or_install_homebrew
            brew install python@3.12
            ;;
        linux)
            if command_exists apt-get; then
                sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-venv python3-dev
            elif command_exists dnf; then
                sudo dnf install -y -q python3 python3-devel
            elif command_exists pacman; then
                sudo pacman -S --noconfirm python
            else
                error "Cannot auto-install Python. Please install Python 3.11+ manually."
                exit 1
            fi
            ;;
    esac

    # Verify
    for cmd in python3 python; do
        if command_exists "$cmd"; then
            local ver minor
            ver="$($cmd --version 2>&1)"
            minor=$(echo "$ver" | sed -n 's/Python 3\.\([0-9]*\).*/\1/p')
            if [[ -n "$minor" ]] && [[ "$minor" -ge 11 ]]; then
                success "$ver installed"
                return 0
            fi
        fi
    done

    error "Python 3.11+ still not available. Please install manually."
    exit 1
}

check_uv() {
    if command_exists uv; then
        success "uv $(uv --version 2>&1 | awk '{print $2}')"
        return 0
    fi

    info "Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if command_exists uv; then
        success "uv installed"
    else
        error "uv installation failed. Visit https://docs.astral.sh/uv/"
        exit 1
    fi
}

check_node() {
    if command_exists node; then
        local node_major
        node_major=$(node --version | sed -n 's/v\([0-9]*\).*/\1/p')
        if [[ "$node_major" -ge 18 ]]; then
            success "Node.js $(node --version)"
            return 0
        fi
    fi

    warn "Node.js 18+ not found. Installing..."
    case "$OS" in
        macos)
            check_or_install_homebrew
            brew install node
            ;;
        linux)
            if command_exists apt-get; then
                curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
                sudo apt-get install -y -qq nodejs
            elif command_exists dnf; then
                sudo dnf install -y -q nodejs npm
            elif command_exists pacman; then
                sudo pacman -S --noconfirm nodejs npm
            else
                error "Cannot auto-install Node.js. Please install Node.js 18+ manually."
                exit 1
            fi
            ;;
    esac

    if command_exists node; then
        success "Node.js $(node --version) installed"
    else
        error "Node.js installation failed"
        exit 1
    fi
}

# ── Interactive prompts ─────────────────────────────────────────────────────
prompt_read() {
    local prompt_text="$1"
    local default_val="${2:-}"
    local result=""

    if [[ -n "$default_val" ]]; then
        echo -ne "  ${CYAN}?${NC} ${prompt_text} ${MUTED}($default_val)${NC}: " >&2
    else
        echo -ne "  ${CYAN}?${NC} ${prompt_text}: " >&2
    fi

    read -r result </dev/tty
    if [[ -z "$result" && -n "$default_val" ]]; then
        result="$default_val"
    fi
    echo "$result"
}

prompt_secret() {
    local prompt_text="$1"
    local result=""

    echo -ne "  ${CYAN}?${NC} ${prompt_text}: " >&2
    read -rs result </dev/tty
    echo "" >&2
    echo "$result"
}

prompt_choice() {
    local prompt_text="$1"
    shift
    local options=("$@")
    local count=${#options[@]}
    local selected=0

    echo -e "  ${CYAN}?${NC} ${prompt_text}" >&2
    echo -e "    ${MUTED}Use arrow keys to move, Enter to select${NC}" >&2

    # Hide cursor
    printf '\033[?25l' >/dev/tty

    # Draw options
    local i
    for ((i=0; i<count; i++)); do
        if [[ $i -eq $selected ]]; then
            echo -e "    ${ACCENT}${BOLD}> ${options[$i]}${NC}" >/dev/tty
        else
            echo -e "      ${MUTED}${options[$i]}${NC}" >/dev/tty
        fi
    done

    # Key loop
    while true; do
        # Read one char
        IFS= read -rsn1 key </dev/tty

        if [[ "$key" == $'\x1b' ]]; then
            # Read the rest of the escape sequence (e.g. [A, [B, OA, OB)
            IFS= read -rsn2 seq </dev/tty
            case "$seq" in
                "[A"|"OA")  ((selected > 0)) && ((selected--)) ;;
                "[B"|"OB")  ((selected < count - 1)) && ((selected++)) ;;
            esac
        elif [[ "$key" == "" ]]; then
            break
        elif [[ "$key" =~ ^[1-9]$ ]] && [[ "$key" -le "$count" ]]; then
            selected=$((key - 1))
            break
        else
            continue
        fi

        # Move cursor up and redraw
        printf "\033[${count}A\r" >/dev/tty
        for ((i=0; i<count; i++)); do
            printf "\033[2K" >/dev/tty
            if [[ $i -eq $selected ]]; then
                echo -e "    ${ACCENT}${BOLD}> ${options[$i]}${NC}" >/dev/tty
            else
                echo -e "      ${MUTED}${options[$i]}${NC}" >/dev/tty
            fi
        done
    done

    # Final redraw: highlight the chosen option in green
    printf "\033[${count}A\r" >/dev/tty
    for ((i=0; i<count; i++)); do
        printf "\033[2K" >/dev/tty
        if [[ $i -eq $selected ]]; then
            echo -e "    ${SUCCESS}${BOLD}> ${options[$i]}${NC}" >/dev/tty
        else
            echo -e "      ${MUTED}${options[$i]}${NC}" >/dev/tty
        fi
    done

    # Show cursor
    printf '\033[?25h' >/dev/tty

    echo $((selected + 1))
}

prompt_yn() {
    local prompt_text="$1"
    local default_val="${2:-y}"

    if [[ "$default_val" == "y" ]]; then
        echo -ne "  ${CYAN}?${NC} ${prompt_text} ${MUTED}(Y/n)${NC}: "
    else
        echo -ne "  ${CYAN}?${NC} ${prompt_text} ${MUTED}(y/N)${NC}: "
    fi

    local answer
    read -r answer </dev/tty
    answer="${answer:-$default_val}"

    case "$answer" in
        [Yy]*) return 0 ;;
        *) return 1 ;;
    esac
}

# ── LLM Configuration (interactive) ────────────────────────────────────────
configure_llm() {
    echo ""
    separator
    echo -e "  ${BOLD}LLM Provider Configuration${NC}"
    separator
    echo ""
    echo -e "  ${MUTED}Open Recruiter uses an LLM for resume parsing, candidate matching,${NC}"
    echo -e "  ${MUTED}email composition, and the AI chat assistant.${NC}"
    echo ""

    local choice
    choice=$(prompt_choice "Select your LLM provider" \
        "Anthropic (Claude) — recommended" \
        "OpenAI (GPT)" \
        "Skip — I'll configure later")

    case "$choice" in
        1)
            LLM_PROVIDER="anthropic"
            echo ""
            echo -e "  ${MUTED}Get your API key at: https://console.anthropic.com/settings/keys${NC}"
            LLM_API_KEY=$(prompt_secret "Anthropic API Key (sk-ant-...)")

            if [[ -z "$LLM_API_KEY" ]]; then
                warn "No API key provided. You can set it later in Settings."
                LLM_PROVIDER=""
            else
                # Validate key format
                if [[ "$LLM_API_KEY" != sk-ant-* ]]; then
                    warn "Key doesn't start with 'sk-ant-'. Saving anyway — verify in Settings if needed."
                fi

                echo ""
                local model_choice
                model_choice=$(prompt_choice "Select Claude model" \
                    "Claude Sonnet 4 (balanced)" \
                    "Claude Opus 4.6 (most capable)" \
                    "Claude Haiku 3.5 (fastest)")

                case "$model_choice" in
                    1) LLM_MODEL="claude-sonnet-4-20250514" ;;
                    2) LLM_MODEL="claude-opus-4-6" ;;
                    3) LLM_MODEL="claude-haiku-4-5-20251001" ;;
                    *) LLM_MODEL="claude-sonnet-4-20250514" ;;
                esac
                success "Provider: Anthropic, Model: $LLM_MODEL"
            fi
            ;;
        2)
            LLM_PROVIDER="openai"
            echo ""
            echo -e "  ${MUTED}Get your API key at: https://platform.openai.com/api-keys${NC}"
            LLM_API_KEY=$(prompt_secret "OpenAI API Key (sk-...)")

            if [[ -z "$LLM_API_KEY" ]]; then
                warn "No API key provided. You can set it later in Settings."
                LLM_PROVIDER=""
            else
                echo ""
                local model_choice
                model_choice=$(prompt_choice "Select OpenAI model" \
                    "GPT-5.1 (latest)" \
                    "GPT-4o (balanced)" \
                    "GPT-4o mini (fastest)")

                case "$model_choice" in
                    1) LLM_MODEL="gpt-5.1" ;;
                    2) LLM_MODEL="gpt-4o" ;;
                    3) LLM_MODEL="gpt-4o-mini" ;;
                    *) LLM_MODEL="gpt-5.1" ;;
                esac
                success "Provider: OpenAI, Model: $LLM_MODEL"
            fi
            ;;
        3|*)
            info "Skipping LLM configuration. You can configure it in the Settings page after launch."
            ;;
    esac
}

# ── Write .env file ────────────────────────────────────────────────────────
write_env_file() {
    local env_file="$INSTALL_DIR/backend/.env"

    # Don't overwrite existing .env
    if [[ -f "$env_file" ]]; then
        if ! prompt_yn "Existing .env found. Overwrite?" "n"; then
            info "Keeping existing .env"
            return 0
        fi
    fi

    local provider="${LLM_PROVIDER:-anthropic}"
    local anthropic_key=""
    local openai_key=""

    if [[ "$provider" == "anthropic" ]]; then
        anthropic_key="$LLM_API_KEY"
    elif [[ "$provider" == "openai" ]]; then
        openai_key="$LLM_API_KEY"
    fi

    cat > "$env_file" << EOF
# === Open Recruiter Configuration ===
# Generated by install.sh on $(date +%Y-%m-%d)

# LLM Provider: "anthropic" or "openai"
LLM_PROVIDER=$provider
LLM_MODEL=${LLM_MODEL:-}

# API Keys
ANTHROPIC_API_KEY=${anthropic_key:-}
OPENAI_API_KEY=${openai_key:-}

# Email: "console" (dev/no-op), "gmail", or custom SMTP
EMAIL_BACKEND=console
# EMAIL_FROM=recruiter@yourcompany.com

# SMTP Configuration (optional)
# SMTP_HOST=
# SMTP_PORT=587
# SMTP_USERNAME=
# SMTP_PASSWORD=

# IMAP for reply detection (optional)
# IMAP_HOST=imap.gmail.com
# IMAP_PORT=993
# IMAP_USERNAME=
# IMAP_PASSWORD=

# Slack Integration (optional)
# SLACK_BOT_TOKEN=xoxb-...
# SLACK_APP_TOKEN=
# SLACK_SIGNING_SECRET=
# SLACK_INTAKE_CHANNEL=
EOF

    success ".env written"
}

# ── Clone / update repo ────────────────────────────────────────────────────
setup_repo() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Existing installation found at $INSTALL_DIR"
        info "Pulling latest changes..."
        cd "$INSTALL_DIR"
        git pull --ff-only 2>/dev/null || {
            warn "git pull failed (you may have local changes). Continuing with existing code."
        }
    else
        info "Cloning Open Recruiter to $INSTALL_DIR..."
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
}

# ── Install dependencies ───────────────────────────────────────────────────
install_backend() {
    info "Installing Python dependencies..."
    cd "$INSTALL_DIR/backend"
    uv sync 2>&1 | tail -3
    success "Backend dependencies installed"
}

install_frontend() {
    info "Installing Node.js dependencies..."
    cd "$INSTALL_DIR/frontend"
    npm install --silent 2>&1 | tail -1
    success "Frontend dependencies installed"
}

# ── Create start command ────────────────────────────────────────────────────
create_start_alias() {
    echo ""
    separator
    echo -e "  ${BOLD}Quick Launch Setup${NC}"
    separator
    echo ""

    local shell_rc=""
    local shell_name=""

    if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == */zsh ]]; then
        shell_rc="$HOME/.zshrc"
        shell_name="zsh"
    elif [[ -n "${BASH_VERSION:-}" ]] || [[ "$SHELL" == */bash ]]; then
        shell_rc="$HOME/.bashrc"
        shell_name="bash"
    fi

    if [[ -n "$shell_rc" ]]; then
        if prompt_yn "Add 'open-recruiter' command to your shell?" "y"; then
            local alias_line="alias open-recruiter='$INSTALL_DIR/start.sh'"

            if [[ -f "$shell_rc" ]] && grep -q "alias open-recruiter=" "$shell_rc" 2>/dev/null; then
                # Update existing alias
                sed -i.bak "s|alias open-recruiter=.*|$alias_line|" "$shell_rc"
                rm -f "${shell_rc}.bak"
                success "Updated 'open-recruiter' alias in $shell_rc"
            else
                echo "" >> "$shell_rc"
                echo "# Open Recruiter" >> "$shell_rc"
                echo "$alias_line" >> "$shell_rc"
                success "Added 'open-recruiter' command to $shell_rc"
            fi
            info "Run 'source $shell_rc' or open a new terminal to use it."
        fi
    fi
}

# ── Summary & launch ───────────────────────────────────────────────────────
print_success() {
    echo ""
    echo -e "  ${SUCCESS}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${SUCCESS}${BOLD}  Installation complete!${NC}"
    echo -e "  ${SUCCESS}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BOLD}Installed to:${NC}  $INSTALL_DIR"
    echo ""
    echo -e "  ${BOLD}To start:${NC}"
    echo -e "    ${CYAN}cd $INSTALL_DIR && ./start.sh${NC}"
    echo ""
    echo -e "  ${BOLD}URLs:${NC}"
    echo -e "    Web UI:    ${CYAN}http://localhost:5173${NC}"
    echo -e "    API:       ${CYAN}http://localhost:8000${NC}"
    echo -e "    API Docs:  ${CYAN}http://localhost:8000/docs${NC}"
    echo ""

    if [[ -z "$LLM_API_KEY" ]]; then
        echo -e "  ${WARN}${BOLD}Note:${NC} No LLM API key configured."
        echo -e "  ${MUTED}Go to Settings in the web UI to add your API key.${NC}"
        echo ""
    fi
}

# ── Main ────────────────────────────────────────────────────────────────────
main() {
    banner
    detect_os

    # Step 1: Check dependencies
    step 1 4 "Checking dependencies"
    echo ""
    check_git
    check_python
    check_uv
    check_node

    # Step 2: Configure LLM
    step 2 4 "Configuration"
    configure_llm

    # Step 3: Install
    step 3 4 "Installing Open Recruiter"
    echo ""
    setup_repo
    write_env_file
    mkdir -p "$INSTALL_DIR/backend/uploads"
    install_backend
    install_frontend

    # Step 4: Finishing up
    step 4 4 "Finishing up"
    create_start_alias
    print_success

    # Offer to launch
    if prompt_yn "Start Open Recruiter now?" "y"; then
        echo ""
        exec "$INSTALL_DIR/start.sh"
    fi
}

# Allow sourcing without executing
if [[ "${OPEN_RECRUITER_INSTALL_SH_NO_RUN:-}" != "1" ]]; then
    main "$@"
fi
