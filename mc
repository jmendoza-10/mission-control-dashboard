#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# mc — Mission Control service manager
#
# Usage:
#   mc start       Load and start the launchd service
#   mc stop        Stop the service (unload from launchd)
#   mc restart     Stop then start
#   mc status      Show service status + health check
#   mc logs        Tail the server logs (Ctrl-C to stop)
#   mc errors      Tail the error logs
#   mc open        Open the dashboard in your default browser
#   mc health      Quick health-check (JSON response)
#   mc install     First-time setup: copy plist → ~/Library/LaunchAgents
#   mc uninstall   Remove the plist and stop the service
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

LABEL="com.openclaw.mission-control"
PLIST_NAME="${LABEL}.plist"
MC_DIR="$HOME/workspace/mission-control-dashboard"
PLIST_SRC="${MC_DIR}/${PLIST_NAME}"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}"
PORT=8080
URL="http://localhost:${PORT}/mission-control.html"
HEALTH_URL="http://localhost:${PORT}/health"
LOG_FILE="/tmp/mission-control.log"
ERR_FILE="/tmp/mission-control-error.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_status() { echo -e "  ${CYAN}⚙${NC} $1"; }
print_ok()     { echo -e "  ${GREEN}✓${NC} $1"; }
print_err()    { echo -e "  ${RED}✗${NC} $1"; }
print_warn()   { echo -e "  ${YELLOW}!${NC} $1"; }

# ── Commands ────────────────────────────────────────────────────────

cmd_install() {
    echo ""
    print_status "Installing Mission Control service..."

    if [ ! -f "$PLIST_SRC" ]; then
        print_err "Plist not found at ${PLIST_SRC}"
        exit 1
    fi

    # Copy plist to LaunchAgents
    cp "$PLIST_SRC" "$PLIST_DST"
    print_ok "Plist installed to ${PLIST_DST}"

    # Load it
    launchctl load "$PLIST_DST" 2>/dev/null || true
    print_ok "Service loaded into launchd"

    # Wait a moment for it to start
    sleep 2

    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        print_ok "Server is running at ${URL}"
    else
        print_warn "Server may still be starting — try 'mc status' in a few seconds"
    fi
    echo ""
}

cmd_uninstall() {
    echo ""
    print_status "Uninstalling Mission Control service..."

    if [ -f "$PLIST_DST" ]; then
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm -f "$PLIST_DST"
        print_ok "Service unloaded and plist removed"
    else
        print_warn "Plist not found at ${PLIST_DST} — nothing to remove"
    fi
    echo ""
}

cmd_start() {
    echo ""
    if [ ! -f "$PLIST_DST" ]; then
        print_warn "Service not installed yet — running 'mc install' first..."
        cmd_install
        return
    fi

    print_status "Starting Mission Control..."
    launchctl load "$PLIST_DST" 2>/dev/null || true
    sleep 2

    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        print_ok "Server is running at ${URL}"
    else
        print_warn "Server may still be starting — try 'mc status' in a few seconds"
    fi
    echo ""
}

cmd_stop() {
    echo ""
    print_status "Stopping Mission Control..."

    if [ -f "$PLIST_DST" ]; then
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        print_ok "Service stopped"
    else
        # Try killing by port as fallback
        local pid
        pid=$(lsof -ti :"$PORT" 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
            print_ok "Killed process ${pid} on port ${PORT}"
        else
            print_warn "Service doesn't appear to be running"
        fi
    fi
    echo ""
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    echo ""
    echo -e "  ${CYAN}━━━ Mission Control Status ━━━${NC}"
    echo ""

    # Check if plist is installed
    if [ -f "$PLIST_DST" ]; then
        print_ok "Plist installed"
    else
        print_err "Plist not installed (run 'mc install')"
    fi

    # Check if process is running
    local pid
    pid=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [ -n "$pid" ]; then
        print_ok "Server running (PID ${pid}, port ${PORT})"
    else
        print_err "Server not running"
        echo ""
        return
    fi

    # Health check
    local health
    health=$(curl -sf "$HEALTH_URL" 2>/dev/null || true)
    if [ -n "$health" ]; then
        local uptime
        uptime=$(echo "$health" | python3 -c "import sys,json; d=json.load(sys.stdin); s=d['uptime_seconds']; print(f'{s//3600}h {(s%3600)//60}m {s%60}s')" 2>/dev/null || echo "unknown")
        print_ok "Health check passed — uptime: ${uptime}"
    else
        print_warn "Health check failed (server may be starting)"
    fi

    # Dashboard URL
    echo ""
    echo -e "  ${CYAN}→${NC} ${URL}"
    echo ""
}

cmd_logs() {
    echo ""
    print_status "Tailing Mission Control logs (Ctrl-C to stop)..."
    echo ""
    tail -f "$LOG_FILE" 2>/dev/null || print_err "No log file found at ${LOG_FILE}"
}

cmd_errors() {
    echo ""
    print_status "Tailing Mission Control error logs (Ctrl-C to stop)..."
    echo ""
    tail -f "$ERR_FILE" 2>/dev/null || print_err "No error log found at ${ERR_FILE}"
}

cmd_open() {
    local pid
    pid=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [ -z "$pid" ]; then
        print_warn "Server not running — starting it first..."
        cmd_start
    fi
    open "$URL"
    print_ok "Opened Mission Control in browser"
}

cmd_health() {
    curl -sf "$HEALTH_URL" 2>/dev/null | python3 -m json.tool 2>/dev/null || print_err "Health check failed — server may not be running"
}

# ── Main ────────────────────────────────────────────────────────────

case "${1:-help}" in
    install)   cmd_install   ;;
    uninstall) cmd_uninstall ;;
    start)     cmd_start     ;;
    stop)      cmd_stop      ;;
    restart)   cmd_restart   ;;
    status)    cmd_status    ;;
    logs)      cmd_logs      ;;
    errors)    cmd_errors    ;;
    open)      cmd_open      ;;
    health)    cmd_health    ;;
    *)
        echo ""
        echo -e "  ${CYAN}⚙ Mission Control — Service Manager${NC}"
        echo ""
        echo "  Usage: mc <command>"
        echo ""
        echo "  Commands:"
        echo "    install     First-time setup (copy plist, load service)"
        echo "    uninstall   Remove service and plist"
        echo "    start       Start the server"
        echo "    stop        Stop the server"
        echo "    restart     Stop + start"
        echo "    status      Show service status and health"
        echo "    logs        Tail server output logs"
        echo "    errors      Tail server error logs"
        echo "    open        Open dashboard in browser"
        echo "    health      Quick JSON health check"
        echo ""
        ;;
esac
