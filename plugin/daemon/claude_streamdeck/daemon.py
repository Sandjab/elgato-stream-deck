"""Daemon orchestrator: wires components, owns the asyncio loop."""

import asyncio
import logging
import signal
from typing import Optional

from .config import DaemonConfig
from .core.asset_registry import AssetRegistry
from .core.command_registry import CommandRegistry
from .core.core_api import CoreAPI
from .core.device import Device
from .core.device_manager import DeviceManager
from .core.display_engine import DisplayEngine
from .core.event_bus import EventBus
from .core.input_dispatcher import InputDispatcher
from .extensions import load_extensions, shutdown_extensions
from .handlers import register_core_handlers
from .transport.socket_server import SocketServer

logger = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: DaemonConfig) -> None:
        self.config = config
        self.bus = EventBus()
        self.assets = AssetRegistry(
            static_dir=config.assets_dir if config.assets_dir.exists() else None,
            max_size_bytes=config.max_asset_bytes,
        )
        self.devices = DeviceManager()
        self.display = DisplayEngine(self.assets)
        self.input = InputDispatcher(self.bus)
        self.commands = CommandRegistry()
        self.api = CoreAPI(
            devices=self.devices, assets=self.assets, display=self.display,
            input=self.input, events=self.bus, commands=self.commands, config={},
        )
        self.server = SocketServer(
            socket_path=config.socket_path,
            commands=self.commands, events=self.bus,
        )
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.bus.bind_loop(loop)
        register_core_handlers(self.api)
        # Devices first, so extensions see them on init.
        await self._connect_devices()
        load_extensions(self.api, self.config.extensions)
        await self.server.start()
        self._running = True
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self) -> None:
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self.server.stop()
        shutdown_extensions()
        for d in self.devices.all():
            try:
                await self.display.purge_device(d.id)
                self.input.detach(d.id)
                d.close()
            except Exception:
                logger.exception("device shutdown failed: %s", d.id)

    async def _connect_devices(self) -> None:
        for d in self.devices.enumerate():
            self._wire_device(d)

    def _wire_device(self, device: Device) -> None:
        # Ensure the device is registered with the manager so that
        # handlers that resolve devices via `DeviceManager.first/get/all`
        # can find it. The real `enumerate()` already populates `_devices`,
        # but mocked or test-injected paths may not — so we make the
        # registration idempotent here.
        self.devices._devices[device.id] = device
        self.display.register_device(device)
        self.input.attach(device)
        # Fire connected event (publish via bus on the loop).
        asyncio.create_task(
            self.bus.publish("device.connected",
                             {"device_id": device.id, "model": device.model.value})
        )

    async def _reconnect_loop(self) -> None:
        while self._running:
            await asyncio.sleep(2.0)
            known = {d.id for d in self.devices.all()}
            for d in self.devices.enumerate():
                if d.id not in known:
                    self._wire_device(d)
