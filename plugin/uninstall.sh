#!/bin/bash
#
# Claude Code Stream Deck XL Plugin Uninstaller
#
# Removes the daemon, hook script, and service configuration.
#
# Usage: ./uninstall.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_DIR="${HOME}/.local/share/claude-streamdeck"
HOOK_DIR="${HOME}/.claude/hooks"
HOOK_FILE="${HOOK_DIR}/streamdeck-notify.sh"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"
SOCKET_PATH="${HOME}/.claude/streamdeck.sock"
LOG_FILE="${HOME}/.claude/streamdeck.log"
ERROR_LOG="${HOME}/.claude/streamdeck.error.log"

# Logging functions
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect operating system
detect_os() {
    case "$(uname -s)" in
        Darwin*)
            OS="macos"
            ;;
        Linux*)
            OS="linux"
            ;;
        *)
            OS="unknown"
            ;;
    esac
}

# Stop and remove service
remove_service() {
    info "Stopping and removing service..."

    if [ "$OS" = "macos" ]; then
        PLIST_FILE="${HOME}/Library/LaunchAgents/com.claude.streamdeck.plist"
        if [ -f "$PLIST_FILE" ]; then
            launchctl unload "$PLIST_FILE" 2>/dev/null || true
            rm -f "$PLIST_FILE"
            success "LaunchAgent service removed"
        else
            info "LaunchAgent service not found"
        fi
    elif [ "$OS" = "linux" ]; then
        SERVICE_FILE="${HOME}/.config/systemd/user/claude-streamdeck.service"
        if [ -f "$SERVICE_FILE" ]; then
            systemctl --user stop claude-streamdeck.service 2>/dev/null || true
            systemctl --user disable claude-streamdeck.service 2>/dev/null || true
            rm -f "$SERVICE_FILE"
            systemctl --user daemon-reload
            success "systemd service removed"
        else
            info "systemd service not found"
        fi
    fi
}

# Remove hook script
remove_hook() {
    info "Removing hook script..."

    if [ -f "$HOOK_FILE" ]; then
        rm -f "$HOOK_FILE"
        success "Hook script removed"
    else
        info "Hook script not found"
    fi
}

# Remove Claude Code hooks configuration
remove_hook_config() {
    info "Removing hook configuration from Claude settings..."

    if [ -f "$CLAUDE_SETTINGS" ] && command -v jq &> /dev/null; then
        # Check if file has our hooks
        if jq -e '.hooks' "$CLAUDE_SETTINGS" > /dev/null 2>&1; then
            # Create backup
            cp "$CLAUDE_SETTINGS" "${CLAUDE_SETTINGS}.uninstall.bak"

            # Remove hooks that point to our script
            TEMP_FILE=$(mktemp)
            jq --arg hook "$HOOK_FILE" '
                if .hooks then
                    .hooks |= with_entries(
                        .value |= map(select(. != $hook))
                    ) |
                    .hooks |= with_entries(select(.value | length > 0))
                else
                    .
                end |
                if .hooks == {} then del(.hooks) else . end
            ' "$CLAUDE_SETTINGS" > "$TEMP_FILE"
            mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
            success "Hook configuration removed"
        else
            info "No hooks configuration found"
        fi
    else
        warn "Could not update Claude settings (jq not available or file not found)"
    fi
}

# Remove installation directory
remove_install_dir() {
    info "Removing installation directory..."

    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        success "Installation directory removed"
    else
        info "Installation directory not found"
    fi
}

# Remove socket and log files
remove_runtime_files() {
    info "Removing runtime files..."

    [ -S "$SOCKET_PATH" ] && rm -f "$SOCKET_PATH"
    [ -f "$LOG_FILE" ] && rm -f "$LOG_FILE"
    [ -f "$ERROR_LOG" ] && rm -f "$ERROR_LOG"

    success "Runtime files removed"
}

# Main uninstallation flow
main() {
    echo ""
    echo "=========================================="
    echo "  Claude Code Stream Deck XL Uninstaller"
    echo "=========================================="
    echo ""

    # Confirm uninstallation
    read -p "This will remove the Claude Stream Deck plugin. Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi

    detect_os
    remove_service
    remove_hook
    remove_hook_config
    remove_install_dir
    remove_runtime_files

    echo ""
    echo "=========================================="
    echo -e "${GREEN}  Uninstallation Complete!${NC}"
    echo "=========================================="
    echo ""
    echo "The Claude Stream Deck plugin has been removed."
    echo ""
    echo "Note: System dependencies (hidapi, jq, etc.) were not removed."
    echo "      udev rules on Linux were not removed."
    echo ""
}

main "$@"
