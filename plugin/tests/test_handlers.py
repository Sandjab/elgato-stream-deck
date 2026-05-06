"""Tests for the core handlers (system / device / asset / display / input)."""

import asyncio
import base64
import io

import pytest
from PIL import Image

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.core_api import CoreAPI
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.core.device_manager import DeviceManager
from claude_streamdeck.core.display_engine import DisplayEngine
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher
from claude_streamdeck.handlers import register_core_handlers


def _png() -> str:
    img = Image.new("RGB", (50, 50), (1, 2, 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _api_with_mock_device():
    bus = EventBus()
    bus.bind_loop(asyncio.get_event_loop())
    reg = AssetRegistry(static_dir=None)
    devices = DeviceManager()
    dev = MockDevice(id="xl-x", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    devices._devices[dev.id] = dev  # inject for tests
    disp = DisplayEngine(reg)
    disp.register_device(dev)
    inp = InputDispatcher(bus)
    inp.attach(dev)
    cmds = CommandRegistry()
    api = CoreAPI(devices=devices, assets=reg, display=disp, input=inp,
                  events=bus, commands=cmds)
    register_core_handlers(api)
    return api, dev


async def test_system_ping():
    api, _ = _api_with_mock_device()
    out = await api.commands.dispatch("system.ping", {})
    assert out == {"pong": True}


async def test_system_version():
    api, _ = _api_with_mock_device()
    out = await api.commands.dispatch("system.version", {})
    assert "version" in out
    assert "extensions" in out


async def test_device_list():
    api, dev = _api_with_mock_device()
    out = await api.commands.dispatch("device.list", {})
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["id"] == dev.id
    assert out[0]["model"] == "xl"
    assert out[0]["key_count"] == 32


async def test_device_capabilities_default_first():
    api, dev = _api_with_mock_device()
    out = await api.commands.dispatch("device.capabilities", {})
    assert out["id"] == dev.id


async def test_asset_upload_remove_list():
    api, _ = _api_with_mock_device()
    up = await api.commands.dispatch("asset.upload", {"name": "a", "data": _png()})
    assert up["name"] == "a"
    assert up["animated"] is False
    listed = await api.commands.dispatch("asset.list", {})
    assert any(item["name"] == "a" for item in listed)
    rm = await api.commands.dispatch("asset.remove", {"name": "a"})
    assert rm == {}


async def test_display_set_clear():
    api, dev = _api_with_mock_device()
    await api.commands.dispatch("asset.upload", {"name": "a", "data": _png()})
    await api.commands.dispatch("display.set", {"button": 5, "asset": "a"})
    assert dev.last_image_for(5) is not None
    await api.commands.dispatch("display.clear", {"button": 5})
    assert 5 in dev.cleared_keys


async def test_display_brightness():
    api, dev = _api_with_mock_device()
    await api.commands.dispatch("display.brightness", {"value": 42})
    assert dev.brightness == 42


async def test_input_set_active_then_press_emits():
    api, dev = _api_with_mock_device()
    received = []

    async def h(p): received.append(p)
    api.events.subscribe("button.pressed", h)
    await api.commands.dispatch("input.set_active", {"button": 7, "active": True})
    dev.simulate_press(7, True)
    await asyncio.sleep(0.05)
    assert received == [{"device_id": dev.id, "button": 7}]


async def test_invalid_params_missing_button():
    api, _ = _api_with_mock_device()
    with pytest.raises(Exception):
        await api.commands.dispatch("display.set", {"asset": "a"})


async def test_unknown_asset_in_display_set():
    api, _ = _api_with_mock_device()
    from claude_streamdeck.core.asset_registry import AssetNotFoundError
    with pytest.raises(AssetNotFoundError):
        await api.commands.dispatch("display.set", {"button": 0, "asset": "ghost"})
