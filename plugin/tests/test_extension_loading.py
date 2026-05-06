"""Tests for extension loading."""

import asyncio

import pytest

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.core_api import CoreAPI
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.core.device_manager import DeviceManager
from claude_streamdeck.core.display_engine import DisplayEngine
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher
from claude_streamdeck.extensions import load_extensions


def _api():
    bus = EventBus()
    reg = AssetRegistry(static_dir=None)
    devices = DeviceManager()
    disp = DisplayEngine(reg)
    inp = InputDispatcher(bus)
    cmds = CommandRegistry()
    return CoreAPI(devices=devices, assets=reg, display=disp, input=inp,
                   events=bus, commands=cmds)


async def test_load_echo_extension_registers_handlers():
    api = _api()
    api.events.bind_loop(asyncio.get_event_loop())
    loaded = load_extensions(
        api, [{"module": "claude_streamdeck.extensions.echo", "config": {}}]
    )
    assert "claude_streamdeck.extensions.echo" in loaded


async def test_failing_extension_is_skipped(monkeypatch):
    api = _api()
    api.events.bind_loop(asyncio.get_event_loop())
    # Build a fake module with a broken init.
    import sys
    import types
    mod = types.ModuleType("fake_broken_ext")
    class Ext:
        def init(self, api): raise RuntimeError("boom")
        def shutdown(self): pass
    mod.Extension = Ext
    sys.modules["fake_broken_ext"] = mod

    loaded = load_extensions(api, [{"module": "fake_broken_ext", "config": {}}])
    assert loaded == []  # broken extension is skipped, daemon continues


async def test_echo_marks_buttons_active_when_device_attached():
    api = _api()
    api.events.bind_loop(asyncio.get_event_loop())
    dev = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    api.devices._devices[dev.id] = dev
    api.input.attach(dev)

    load_extensions(
        api, [{"module": "claude_streamdeck.extensions.echo", "config": {}}]
    )
    # The echo extension activates all buttons of all currently-known devices.
    received = []
    async def h(p): received.append(p)
    api.events.subscribe("button.pressed", h)
    dev.simulate_press(0, True)
    await asyncio.sleep(0.05)
    assert received == [{"device_id": "m", "button": 0}]
