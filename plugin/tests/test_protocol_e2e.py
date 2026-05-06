"""End-to-end test of the daemon over a real Unix socket with a mocked device."""

import asyncio
import base64
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from claude_streamdeck.config import DaemonConfig
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.daemon import Daemon


def _png() -> str:
    img = Image.new("RGB", (50, 50), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def _send(w, obj):
    w.write((json.dumps(obj) + "\n").encode())
    await w.drain()


async def _recv(r):
    line = await asyncio.wait_for(r.readline(), timeout=2.0)
    return json.loads(line.decode().strip())


async def test_e2e_set_image_then_press():
    sock = Path(tempfile.mkdtemp()) / "e2e.sock"
    cfg = DaemonConfig(
        socket_path=sock,
        assets_dir=Path("/nonexistent"),
        extensions=[],
    )
    daemon = Daemon(cfg)

    # Inject a MockDevice instead of enumerating real hardware.
    mock = MockDevice(id="xl-test", model=DeviceModel.XL,
                      key_count=32, image_size=(96, 96))
    with patch.object(daemon.devices, "enumerate", return_value=[mock]):
        await daemon.start()
    try:
        r, w = await asyncio.open_unix_connection(str(sock))

        # Upload an asset
        await _send(w, {"cmd": "asset.upload", "request_id": "1",
                        "name": "a", "data": _png()})
        resp = await _recv(r)
        assert resp["ok"] is True
        assert resp["result"]["name"] == "a"

        # Display it on button 5
        await _send(w, {"cmd": "display.set", "request_id": "2",
                        "button": 5, "asset": "a"})
        resp = await _recv(r)
        assert resp["ok"] is True
        assert mock.last_image_for(5) is not None

        # Activate button 7 and subscribe
        await _send(w, {"cmd": "input.set_active", "request_id": "3",
                        "button": 7, "active": True})
        resp = await _recv(r)
        assert resp["ok"] is True
        await _send(w, {"cmd": "input.subscribe", "request_id": "4"})
        resp = await _recv(r)
        assert resp["ok"] is True

        # Simulate a press; expect an event
        mock.simulate_press(7, True)
        ev = await _recv(r)
        assert ev["event"] == "button.pressed"
        assert ev["device_id"] == "xl-test"
        assert ev["button"] == 7

        w.close()
        await w.wait_closed()
    finally:
        await daemon.stop()


async def test_e2e_unknown_command_keeps_connection():
    sock = Path(tempfile.mkdtemp()) / "e2e2.sock"
    cfg = DaemonConfig(socket_path=sock, assets_dir=Path("/nonexistent"), extensions=[])
    daemon = Daemon(cfg)
    mock = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    with patch.object(daemon.devices, "enumerate", return_value=[mock]):
        await daemon.start()
    try:
        r, w = await asyncio.open_unix_connection(str(sock))
        await _send(w, {"cmd": "nope.nope", "request_id": "x"})
        resp = await _recv(r)
        assert resp["ok"] is False
        assert resp["error"] == "unknown_command"

        await _send(w, {"cmd": "system.ping", "request_id": "y"})
        resp = await _recv(r)
        assert resp["ok"] is True
        assert resp["result"] == {"pong": True}

        w.close(); await w.wait_closed()
    finally:
        await daemon.stop()
