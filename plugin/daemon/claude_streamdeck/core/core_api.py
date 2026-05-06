"""Façade injected into extensions: bundles handles to core components."""

from dataclasses import dataclass, field
from typing import Any

from .asset_registry import AssetRegistry
from .command_registry import CommandRegistry
from .device_manager import DeviceManager
from .display_engine import DisplayEngine
from .event_bus import EventBus
from .input_dispatcher import InputDispatcher


@dataclass
class CoreAPI:
    devices: DeviceManager
    assets: AssetRegistry
    display: DisplayEngine
    input: InputDispatcher
    events: EventBus
    commands: CommandRegistry
    config: dict[str, Any] = field(default_factory=dict)
