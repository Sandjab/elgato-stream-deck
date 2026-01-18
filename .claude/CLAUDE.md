# Claude Code Stream Deck Plugin

## Project Overview

This project implements a Claude Code integration plugin for the Elgato Stream Deck XL. It provides real-time visual feedback of Claude Code's state and quick actions via physical buttons.

## Architecture

```
Claude Code (hooks) → Hook Script (bash) → Unix Socket → Python Daemon → Stream Deck XL (USB HID)
```

## Key Components

### Plugin (`plugin/`)
- `daemon/` - Python daemon that controls the Stream Deck
- `hooks/` - Bash scripts called by Claude Code hooks
- `assets/icons/96x96/` - PNG icons for Stream Deck XL
- `services/` - macOS LaunchAgent and Linux systemd service files
- `tests/` - Unit tests for state machine and socket server

### Documentation (`docs/`)
- `streamdeck-specifications.md` - Hardware specs for all Stream Deck models
- `claude-code-streamdeck-integration-spec.md` - Integration architecture
- `claude-streamdeck-tech-spec.md` - Detailed implementation spec
- `claude-streamdeck-prd.md` - Product requirements document

## Stream Deck XL Specs
- 32 buttons (8x4 grid)
- 96x96 pixel icons (JPEG format)
- Product ID: 0x006C

## Button Layout
- Key 0: Status indicator (state display)
- Key 1: New session (`claude`)
- Key 2: Resume session (`claude --resume`)
- Key 3: Stop/interrupt (sends Escape)

## States
- `inactive` (gray) - No active session
- `idle` (green) - Session ready
- `thinking` (blue) - Processing prompt
- `tool_running` (orange) - Executing tool

## Development

### Running the daemon
```bash
cd plugin/daemon
pip3 install -r requirements.txt
python3 -m claude_streamdeck --debug
```

### Running tests
```bash
cd plugin
python3 -m pytest tests/ -v
```

### Dependencies
- Python 3.9+
- streamdeck library
- pillow
- hidapi (system)
- jq (for hooks)

## Known Limitations
- Multiple concurrent Claude sessions share the same state display
- Stop button requires Accessibility permissions on macOS
- Resume uses `--resume` (shows list) instead of `--continue` (last session)
