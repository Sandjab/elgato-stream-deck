"""Unit tests for socket server module."""

import asyncio
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add daemon directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "daemon"))

from claude_streamdeck.socket_server import SocketServer


class TestSocketServer:
    """Tests for SocketServer class."""

    @pytest.fixture
    def socket_path(self):
        """Create a temporary socket path with short name for macOS compatibility."""
        # Unix sockets have a 104-char limit on macOS, use /tmp with short name
        path = Path(f"/tmp/sd-{uuid.uuid4().hex[:8]}.sock")
        yield path
        # Cleanup
        if path.exists():
            path.unlink()

    @pytest.fixture
    def message_handler(self):
        """Create a mock message handler."""
        return MagicMock()

    @pytest.fixture
    def server(self, socket_path, message_handler):
        """Create a socket server instance."""
        return SocketServer(
            socket_path=socket_path,
            message_handler=message_handler,
            timeout=1.0
        )

    @pytest.mark.asyncio
    async def test_start_creates_socket(self, server, socket_path):
        """Test that start() creates the socket file."""
        await server.start()
        try:
            assert socket_path.exists()
            assert server.is_running
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_stop_removes_socket(self, server, socket_path):
        """Test that stop() removes the socket file."""
        await server.start()
        await server.stop()

        assert not socket_path.exists()
        assert not server.is_running

    @pytest.mark.asyncio
    async def test_removes_existing_socket(self, server, socket_path):
        """Test that start() removes existing socket file."""
        # Create a dummy file at the socket path
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.touch()

        await server.start()
        try:
            assert socket_path.exists()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_receive_json_message(self, server, socket_path, message_handler):
        """Test receiving a valid JSON message."""
        await server.start()
        try:
            # Connect and send message
            reader, writer = await asyncio.open_unix_connection(str(socket_path))

            message = {"event": "SessionStart", "session_id": "test-123"}
            writer.write(json.dumps(message).encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()

            # Give server time to process
            await asyncio.sleep(0.1)

            # Verify handler was called
            message_handler.assert_called_once_with(message)

        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_invalid_json_handled(self, server, socket_path, message_handler):
        """Test that invalid JSON doesn't crash server."""
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))

            writer.write(b"not valid json")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

            await asyncio.sleep(0.1)

            # Handler should not be called for invalid JSON
            message_handler.assert_not_called()

            # Server should still be running
            assert server.is_running

        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_empty_message_ignored(self, server, socket_path, message_handler):
        """Test that empty messages are ignored."""
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))

            writer.write(b"")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

            await asyncio.sleep(0.1)

            message_handler.assert_not_called()

        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_multiple_connections(self, server, socket_path, message_handler):
        """Test handling multiple sequential connections."""
        await server.start()
        try:
            messages = [
                {"event": "SessionStart"},
                {"event": "UserPromptSubmit"},
                {"event": "PreToolUse", "tool": "Read"},
            ]

            for msg in messages:
                reader, writer = await asyncio.open_unix_connection(str(socket_path))
                writer.write(json.dumps(msg).encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                await asyncio.sleep(0.05)

            await asyncio.sleep(0.1)

            assert message_handler.call_count == 3

        finally:
            await server.stop()


class TestSocketServerIntegration:
    """Integration tests for socket server with state machine."""

    @pytest.mark.asyncio
    async def test_full_message_flow(self):
        """Test complete message flow from socket to handler."""
        # Use short path for macOS compatibility
        socket_path = Path(f"/tmp/sd-int-{uuid.uuid4().hex[:8]}.sock")
        received_events = []

        def handler(msg):
            received_events.append(msg.get("event"))

        server = SocketServer(socket_path, handler, timeout=1.0)
        await server.start()

        try:
            events = [
                {"event": "SessionStart"},
                {"event": "UserPromptSubmit"},
                {"event": "PreToolUse", "tool": "Bash"},
                {"event": "PostToolUse"},
                {"event": "Stop"},
                {"event": "SessionEnd"},
            ]

            for event in events:
                reader, writer = await asyncio.open_unix_connection(str(socket_path))
                writer.write(json.dumps(event).encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                await asyncio.sleep(0.05)

            await asyncio.sleep(0.1)

            expected = [
                "SessionStart", "UserPromptSubmit", "PreToolUse",
                "PostToolUse", "Stop", "SessionEnd"
            ]
            assert received_events == expected

        finally:
            await server.stop()
