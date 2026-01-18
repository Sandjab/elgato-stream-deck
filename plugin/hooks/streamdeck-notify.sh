#!/bin/bash
#
# Claude Code Stream Deck Hook Script
#
# This script is called by Claude Code hooks to notify the Stream Deck
# daemon of state changes. It reads JSON from stdin and forwards it
# to the Unix socket.
#
# Usage: Called automatically by Claude Code hooks
#
# Exit codes: Always exits 0 to avoid blocking Claude Code
#

set -e

# Configuration
SOCKET_PATH="${HOME}/.claude/streamdeck.sock"
TIMEOUT=2

# Always exit successfully to not block Claude Code
trap 'exit 0' EXIT

# Check if socket exists
if [[ ! -S "$SOCKET_PATH" ]]; then
    exit 0
fi

# Read JSON from stdin
INPUT=$(cat)

# Validate JSON is not empty
if [[ -z "$INPUT" ]]; then
    exit 0
fi

# Extract event type using jq
if ! command -v jq &> /dev/null; then
    # Fallback: try to parse without jq using bash
    EVENT_TYPE=$(echo "$INPUT" | grep -o '"event_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
else
    EVENT_TYPE=$(echo "$INPUT" | jq -r '.event_name // empty' 2>/dev/null)
fi

# Skip if no event type
if [[ -z "$EVENT_TYPE" ]]; then
    exit 0
fi

# Extract tool name if present
if command -v jq &> /dev/null; then
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
    SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
else
    TOOL_NAME=$(echo "$INPUT" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
    SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
fi

# Build message JSON
if command -v jq &> /dev/null; then
    MESSAGE=$(jq -n \
        --arg event "$EVENT_TYPE" \
        --arg tool "${TOOL_NAME:-}" \
        --arg session "${SESSION_ID:-}" \
        --arg ts "$(date +%s)" \
        '{event: $event, tool: $tool, session_id: $session, timestamp: ($ts | tonumber)}')
else
    # Fallback without jq
    TIMESTAMP=$(date +%s)
    MESSAGE="{\"event\":\"$EVENT_TYPE\",\"tool\":\"$TOOL_NAME\",\"session_id\":\"$SESSION_ID\",\"timestamp\":$TIMESTAMP}"
fi

# Send to socket with timeout
# Use different netcat syntax based on platform
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Use nc with -G for connection timeout
    echo "$MESSAGE" | nc -G "$TIMEOUT" -U "$SOCKET_PATH" 2>/dev/null || true
else
    # Linux: Use nc with -w for timeout, -N to close after stdin EOF
    echo "$MESSAGE" | nc -w "$TIMEOUT" -N -U "$SOCKET_PATH" 2>/dev/null || true
fi

exit 0
