#!/usr/bin/env bash
# Manual smoke test: requires a Stream Deck XL plugged in (and the
# Elgato app quitted so the HID handle is free).
# Run the daemon in another terminal first, from the repo root:
#   PYTHONPATH=plugin/daemon .venv/bin/python -m claude_streamdeck --debug

set -euo pipefail

SOCKET="${HOME}/.config/claude-streamdeck/daemon.sock"

if [[ ! -S "$SOCKET" ]]; then
  echo "Socket not found at $SOCKET. Is the daemon running?"
  exit 1
fi

# Send a command, read one response (one line of JSON).
send() {
  local payload="$1"
  echo "$payload" | nc -U "$SOCKET" -q 1 | head -n 1
}

echo "1. system.ping"
send '{"cmd":"system.ping","request_id":"a"}'

echo "2. device.list"
send '{"cmd":"device.list","request_id":"b"}'

echo "3. system.version"
send '{"cmd":"system.version","request_id":"c"}'

echo "Done. If all three returned ok:true, the daemon is alive."
