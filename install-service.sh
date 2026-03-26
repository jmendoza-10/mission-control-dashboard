#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# install-service.sh — One-time setup for Mission Control as a service
#
# What this does:
#   1. Copies the launchd plist to ~/Library/LaunchAgents/
#   2. Symlinks the `mc` management script to /usr/local/bin/mc
#   3. Loads and starts the service
#   4. Opens the dashboard in your browser
#
# Usage:
#   cd ~/workspace/mission-control-dashboard
#   ./install-service.sh
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

MC_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.openclaw.mission-control"
PLIST_SRC="${MC_DIR}/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
MC_SCRIPT="${MC_DIR}/mc"
MC_LINK="/usr/local/bin/mc"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "  ${CYAN}━━━ Mission Control Service Installer ━━━${NC}"
echo ""

# Step 1: Ensure LaunchAgents directory exists
mkdir -p "$HOME/Library/LaunchAgents"

# Step 2: Stop existing service if running
if launchctl list "$LABEL" > /dev/null 2>&1; then
    echo -e "  ${YELLOW}!${NC} Stopping existing service..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Step 3: Install plist
cp "$PLIST_SRC" "$PLIST_DST"
echo -e "  ${GREEN}✓${NC} Plist installed to ~/Library/LaunchAgents/"

# Step 4: Symlink mc to PATH
if [ -L "$MC_LINK" ] || [ -f "$MC_LINK" ]; then
    echo -e "  ${YELLOW}!${NC} Replacing existing ${MC_LINK}"
    sudo rm -f "$MC_LINK"
fi
sudo ln -sf "$MC_SCRIPT" "$MC_LINK"
echo -e "  ${GREEN}✓${NC} 'mc' command linked to ${MC_LINK}"

# Step 5: Load and start
launchctl load "$PLIST_DST"
echo -e "  ${GREEN}✓${NC} Service loaded into launchd"

# Step 6: Wait for startup
sleep 2
if curl -sf "http://localhost:8080/health" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Server is running!"
else
    echo -e "  ${YELLOW}!${NC} Server may still be starting — try 'mc status' in a few seconds"
fi

echo ""
echo -e "  ${CYAN}━━━ Setup Complete ━━━${NC}"
echo ""
echo "  The dashboard is now a persistent service that:"
echo "    • Starts automatically at login"
echo "    • Restarts if it crashes (KeepAlive)"
echo "    • Serves the dashboard at http://localhost:8080"
echo ""
echo "  Manage it with the 'mc' command:"
echo "    mc status     — Check if it's running"
echo "    mc open       — Open dashboard in browser"
echo "    mc restart    — Restart the server"
echo "    mc logs       — Tail server logs"
echo "    mc stop       — Stop the service"
echo ""
echo -e "  ${CYAN}→${NC} http://localhost:8080/mission-control.html"
echo ""

# Step 7: Open in browser
open "http://localhost:8080/mission-control.html" 2>/dev/null || true
