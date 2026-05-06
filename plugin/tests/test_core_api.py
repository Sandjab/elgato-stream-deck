"""Tests for the CoreAPI façade."""

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.core_api import CoreAPI
from claude_streamdeck.core.device_manager import DeviceManager
from claude_streamdeck.core.display_engine import DisplayEngine
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher


def test_core_api_holds_components():
    reg = AssetRegistry(static_dir=None)
    bus = EventBus()
    devices = DeviceManager()
    disp = DisplayEngine(reg)
    inp = InputDispatcher(bus)
    cmds = CommandRegistry()
    api = CoreAPI(
        devices=devices, assets=reg, display=disp, input=inp,
        events=bus, commands=cmds, config={"k": "v"},
    )
    assert api.devices is devices
    assert api.assets is reg
    assert api.display is disp
    assert api.input is inp
    assert api.events is bus
    assert api.commands is cmds
    assert api.config == {"k": "v"}
