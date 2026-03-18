#!/bin/bash
# ============================================================================
#  Open Recruiter — macOS Install Helper
#  Double-click this file to install, or run in Terminal:
#    bash macos-install.command
#
#  This script bypasses the "damaged and can't be opened" Gatekeeper error
#  that occurs on macOS when opening unsigned apps downloaded from the internet.
# ============================================================================

set -e

APP_NAME="Open Recruiter"
APP_FILE="Open Recruiter.app"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Open Recruiter — macOS Installer${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Find the .app — check common locations
APP_PATH=""

# 1. Same directory as this script (inside DMG or extracted folder)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/$APP_FILE" ]; then
    APP_PATH="$SCRIPT_DIR/$APP_FILE"
fi

# 2. Already in /Applications
if [ -z "$APP_PATH" ] && [ -d "/Applications/$APP_FILE" ]; then
    APP_PATH="/Applications/$APP_FILE"
fi

# 3. Downloads folder
if [ -z "$APP_PATH" ] && [ -d "$HOME/Downloads/$APP_FILE" ]; then
    APP_PATH="$HOME/Downloads/$APP_FILE"
fi

if [ -z "$APP_PATH" ]; then
    echo -e "${RED}Could not find '$APP_FILE'.${NC}"
    echo "Please place this script next to the .app, or drag the .app to /Applications first."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo -e "  Found: ${CYAN}$APP_PATH${NC}"
echo ""

# Copy to /Applications if not already there
if [[ "$APP_PATH" != "/Applications/$APP_FILE" ]]; then
    echo -e "${YELLOW}[1/3] Copying to /Applications...${NC}"
    cp -R "$APP_PATH" "/Applications/$APP_FILE" 2>/dev/null || {
        echo -e "  ${CYAN}Requires admin permission...${NC}"
        sudo cp -R "$APP_PATH" "/Applications/$APP_FILE"
    }
    APP_PATH="/Applications/$APP_FILE"
    echo -e "  ${GREEN}Done${NC}"
else
    echo -e "${YELLOW}[1/3] Already in /Applications${NC}"
fi

# Remove quarantine flag (this fixes the "damaged" error)
echo -e "${YELLOW}[2/3] Removing quarantine flag...${NC}"
xattr -cr "$APP_PATH" 2>/dev/null || sudo xattr -cr "$APP_PATH"
echo -e "  ${GREEN}Done${NC}"

# Launch the app
echo -e "${YELLOW}[3/3] Launching $APP_NAME...${NC}"
open "$APP_PATH"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${APP_NAME} has been installed to /Applications."
echo -e "  You can delete the DMG file now."
echo ""
read -p "Press Enter to close..."
