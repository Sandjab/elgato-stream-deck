#!/bin/bash
#
# Claude Code Stream Deck XL Plugin Installer
#
# Installs the daemon, hook script, and configures the service
# for automatic startup.
#
# Usage: ./install.sh
#
# Supports: macOS, Linux (Debian/Ubuntu, Fedora, Arch)
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
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"
VENV_DIR="${INSTALL_DIR}/venv"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    exit 1
}

# Detect operating system
detect_os() {
    case "$(uname -s)" in
        Darwin*)
            OS="macos"
            ;;
        Linux*)
            OS="linux"
            # Detect distro
            if [ -f /etc/debian_version ]; then
                DISTRO="debian"
            elif [ -f /etc/fedora-release ]; then
                DISTRO="fedora"
            elif [ -f /etc/arch-release ]; then
                DISTRO="arch"
            else
                DISTRO="unknown"
            fi
            ;;
        *)
            error "Unsupported operating system: $(uname -s)"
            ;;
    esac
    success "Detected OS: $OS"
}

# Check Python version (3.10+)
check_python() {
    info "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed. Please install Python 3.10 or later."
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        error "Python 3.10+ is required. Found: Python $PYTHON_VERSION"
    fi

    success "Python $PYTHON_VERSION found"
}

# Install system dependencies
install_dependencies() {
    info "Installing system dependencies..."

    if [ "$OS" = "macos" ]; then
        # Check for Homebrew
        if ! command -v brew &> /dev/null; then
            warn "Homebrew not found. Please install from https://brew.sh"
            warn "Then run: brew install hidapi jq"
        else
            info "Installing hidapi and jq via Homebrew..."
            brew install hidapi jq 2>/dev/null || true
        fi
    elif [ "$OS" = "linux" ]; then
        case "$DISTRO" in
            debian)
                info "Installing dependencies via apt..."
                sudo apt-get update
                sudo apt-get install -y libusb-1.0-0-dev libhidapi-libusb0 jq netcat-openbsd
                ;;
            fedora)
                info "Installing dependencies via dnf..."
                sudo dnf install -y libusb1-devel hidapi jq nmap-ncat
                ;;
            arch)
                info "Installing dependencies via pacman..."
                sudo pacman -Sy --noconfirm libusb hidapi jq openbsd-netcat
                ;;
            *)
                warn "Unknown Linux distro. Please manually install: libusb, hidapi, jq, netcat"
                ;;
        esac

        # Setup udev rules for non-root access to Stream Deck
        setup_udev_rules
    fi

    success "System dependencies installed"
}

# Setup udev rules on Linux
setup_udev_rules() {
    info "Setting up udev rules for Stream Deck..."

    UDEV_RULES="/etc/udev/rules.d/50-streamdeck.rules"

    if [ ! -f "$UDEV_RULES" ]; then
        sudo tee "$UDEV_RULES" > /dev/null << 'EOF'
# Elgato Stream Deck devices
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
EOF
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        success "udev rules configured"
    else
        info "udev rules already exist"
    fi
}

# Create installation directory
create_install_dir() {
    info "Creating installation directory..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$HOOK_DIR"
    mkdir -p "${HOME}/.claude"

    success "Directories created"
}

# Install Python package in virtual environment
install_python_package() {
    info "Creating Python virtual environment..."

    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    info "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r "${SCRIPT_DIR}/daemon/requirements.txt"

    success "Python package installed"
}

# Copy daemon files
copy_daemon_files() {
    info "Copying daemon files..."

    cp -r "${SCRIPT_DIR}/daemon/claude_streamdeck" "${INSTALL_DIR}/"
    cp "${SCRIPT_DIR}/daemon/requirements.txt" "${INSTALL_DIR}/"

    success "Daemon files copied"
}

# Copy asset files
copy_assets() {
    info "Copying assets..."

    cp -r "${SCRIPT_DIR}/assets" "${INSTALL_DIR}/"

    success "Assets copied"
}

# Install hook script
install_hook() {
    info "Installing hook script..."

    cp "${SCRIPT_DIR}/hooks/streamdeck-notify.sh" "${HOOK_DIR}/"
    chmod +x "${HOOK_DIR}/streamdeck-notify.sh"

    success "Hook script installed"
}

# Configure Claude Code hooks
configure_claude_hooks() {
    info "Configuring Claude Code hooks..."

    HOOK_PATH="${HOOK_DIR}/streamdeck-notify.sh"

    # Create or update settings.json
    if [ -f "$CLAUDE_SETTINGS" ]; then
        # Backup existing settings
        cp "$CLAUDE_SETTINGS" "${CLAUDE_SETTINGS}.bak"

        # Check if jq is available
        if command -v jq &> /dev/null; then
            # Use jq to merge hooks
            TEMP_FILE=$(mktemp)
            jq --arg hook "$HOOK_PATH" '
                .hooks //= {} |
                .hooks.SessionStart = [$hook] |
                .hooks.SessionEnd = [$hook] |
                .hooks.UserPromptSubmit = [$hook] |
                .hooks.PreToolUse = [$hook] |
                .hooks.PostToolUse = [$hook] |
                .hooks.Stop = [$hook]
            ' "$CLAUDE_SETTINGS" > "$TEMP_FILE"
            mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
        else
            warn "jq not found - please manually configure hooks in $CLAUDE_SETTINGS"
        fi
    else
        # Create new settings file
        cat > "$CLAUDE_SETTINGS" << EOF
{
  "hooks": {
    "SessionStart": ["${HOOK_PATH}"],
    "SessionEnd": ["${HOOK_PATH}"],
    "UserPromptSubmit": ["${HOOK_PATH}"],
    "PreToolUse": ["${HOOK_PATH}"],
    "PostToolUse": ["${HOOK_PATH}"],
    "Stop": ["${HOOK_PATH}"]
  }
}
EOF
    fi

    success "Claude Code hooks configured"
}

# Install service (launchd on macOS, systemd on Linux)
install_service() {
    info "Installing service..."

    if [ "$OS" = "macos" ]; then
        install_launchd_service
    elif [ "$OS" = "linux" ]; then
        install_systemd_service
    fi
}

# Install launchd service on macOS
install_launchd_service() {
    PLIST_DIR="${HOME}/Library/LaunchAgents"
    PLIST_FILE="${PLIST_DIR}/com.claude.streamdeck.plist"

    mkdir -p "$PLIST_DIR"

    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.streamdeck</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python</string>
        <string>-m</string>
        <string>claude_streamdeck</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/.claude/streamdeck.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.claude/streamdeck.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

    # Load the service
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE"

    success "LaunchAgent service installed and started"
}

# Install systemd service on Linux
install_systemd_service() {
    SERVICE_DIR="${HOME}/.config/systemd/user"
    SERVICE_FILE="${SERVICE_DIR}/claude-streamdeck.service"

    mkdir -p "$SERVICE_DIR"

    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Claude Code Stream Deck Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=${VENV_DIR}/bin/python -m claude_streamdeck
WorkingDirectory=${INSTALL_DIR}
Restart=always
RestartSec=5
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
EOF

    # Reload and enable service
    systemctl --user daemon-reload
    systemctl --user enable claude-streamdeck.service
    systemctl --user start claude-streamdeck.service

    success "systemd user service installed and started"
}

# Main installation flow
main() {
    echo ""
    echo "=========================================="
    echo "  Claude Code Stream Deck XL Installer"
    echo "=========================================="
    echo ""

    detect_os
    check_python
    install_dependencies
    create_install_dir
    install_python_package
    copy_daemon_files
    copy_assets
    install_hook
    configure_claude_hooks
    install_service

    echo ""
    echo "=========================================="
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo "=========================================="
    echo ""
    echo "The Stream Deck daemon is now running."
    echo ""
    echo "To check status:"
    if [ "$OS" = "macos" ]; then
        echo "  launchctl list | grep streamdeck"
    else
        echo "  systemctl --user status claude-streamdeck"
    fi
    echo ""
    echo "Logs are available at:"
    echo "  ~/.claude/streamdeck.log"
    echo ""
    echo "To test manually:"
    echo "  ${VENV_DIR}/bin/python -m claude_streamdeck --debug"
    echo ""
}

main "$@"
