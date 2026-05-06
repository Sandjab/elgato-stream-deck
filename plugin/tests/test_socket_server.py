"""Tests for SocketServer (JSONL persistent, multi-client)."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.transport.socket_server import SocketServer


async def _start_server(reg, bus):
    sock_path = Path(tempfile.mkdtemp()) / "test.sock"
    server = SocketServer(socket_path=sock_path, commands=reg, events=bus)
    await server.start()
    return server, sock_path


async def _client(sock_path: Path):
    return await asyncio.open_unix_connection(str(sock_path))


async def _send(writer, obj):
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


async def _recv(reader):
    line = await reader.readline()
    return json.loads(line.decode().strip())


async def test_dispatch_command_returns_result():
    reg = CommandRegistry()
    async def ping(p): return {"pong": True}
    reg.register("system.ping", ping)

    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        r, w = await _client(sock)
        await _send(w, {"cmd": "system.ping", "request_id": "1"})
        resp = await _recv(r)
        assert resp == {"ok": True, "request_id": "1", "result": {"pong": True}}
        w.close()
        await w.wait_closed()
    finally:
        await server.stop()


async def test_unknown_command_returns_error():
    reg = CommandRegistry()
    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        r, w = await _client(sock)
        await _send(w, {"cmd": "nope", "request_id": "x"})
        resp = await _recv(r)
        assert resp["ok"] is False
        assert resp["error"] == "unknown_command"
        assert resp["request_id"] == "x"
        w.close(); await w.wait_closed()
    finally:
        await server.stop()


async def test_invalid_json_returns_error_keeps_connection():
    reg = CommandRegistry()
    async def ping(p): return {}
    reg.register("system.ping", ping)
    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        r, w = await _client(sock)
        # First line bad JSON
        w.write(b"not-json\n")
        await w.drain()
        resp1 = await _recv(r)
        assert resp1["ok"] is False
        assert resp1["error"] == "invalid_json"
        # Then a valid command on same connection
        await _send(w, {"cmd": "system.ping"})
        resp2 = await _recv(r)
        assert resp2["ok"] is True
        w.close(); await w.wait_closed()
    finally:
        await server.stop()


async def test_event_broadcast_to_subscribed_only():
    reg = CommandRegistry()
    # Provide subscribe/unsubscribe handlers via the server's "input.subscribe"
    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        # Two clients
        r1, w1 = await _client(sock)
        r2, w2 = await _client(sock)
        await asyncio.sleep(0.05)
        await _send(w1, {"cmd": "input.subscribe", "request_id": "s1"})
        resp = await _recv(r1)
        assert resp["ok"] is True
        # Publish a button event
        await bus.publish("button.pressed", {"device_id": "x", "button": 5})
        # Client 1 should receive
        line = await asyncio.wait_for(r1.readline(), timeout=1.0)
        ev = json.loads(line.decode().strip())
        assert ev["event"] == "button.pressed"
        assert ev["device_id"] == "x"
        assert ev["button"] == 5
        # Client 2 should NOT receive (verify by short timeout)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(r2.readline(), timeout=0.2)
        for w in (w1, w2):
            w.close(); await w.wait_closed()
    finally:
        await server.stop()
