"""Drives static images and animations onto Devices via the AssetRegistry."""

import asyncio
import logging
from typing import Literal, Optional

from PIL import Image

from .asset_registry import AssetRegistry
from .device import Device

logger = logging.getLogger(__name__)


class ButtonOutOfRangeError(Exception):
    pass


class DeviceNotFoundError(Exception):
    pass


class DisplayEngine:
    """Per-(device, button) display state with cooperative animation tasks."""

    def __init__(self, assets: AssetRegistry) -> None:
        self._assets = assets
        self._devices: dict[str, Device] = {}
        # (device_id, button) -> asyncio.Task running an animation loop
        self._animations: dict[tuple[str, int], asyncio.Task] = {}

    def register_device(self, device: Device) -> None:
        self._devices[device.id] = device

    def unregister_device(self, device_id: str) -> None:
        self._devices.pop(device_id, None)

    def _device(self, device_id: str) -> Device:
        d = self._devices.get(device_id)
        if d is None:
            raise DeviceNotFoundError(device_id)
        return d

    def _check_button(self, device: Device, button: int) -> None:
        if button < 0 or button >= device.key_count:
            raise ButtonOutOfRangeError(f"{button} not in [0,{device.key_count})")

    async def set_image(self, device_id: str, button: int, asset_name: str) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)
        img = self._assets.get_resized(asset_name, d.image_size)
        d.set_key_image(button, img)

    async def clear(self, device_id: str, button: int) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)
        d.clear_key(button)

    async def animate(
        self,
        device_id: str,
        button: int,
        asset: Optional[str] = None,
        frames: Optional[list[dict]] = None,
        loop: bool = True,
    ) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)

        # Build (image, duration_ms) sequence
        sequence: list[tuple[Image.Image, int]] = []
        if asset is not None:
            a = self._assets.get(asset)
            imgs = self._assets.get_resized_frames(asset, d.image_size)
            for img, dur in zip(imgs, a.frame_durations_ms):
                sequence.append((img, dur))
        elif frames is not None:
            for f in frames:
                img = self._assets.get_resized(f["asset"], d.image_size)
                sequence.append((img, int(f.get("duration_ms", 100))))
        else:
            raise ValueError("animate requires `asset` or `frames`")

        if not sequence:
            return

        task = asyncio.create_task(
            self._animation_loop(d, button, sequence, loop)
        )
        self._animations[(device_id, button)] = task

    async def _animation_loop(
        self,
        device: Device,
        button: int,
        sequence: list[tuple[Image.Image, int]],
        loop: bool,
    ) -> None:
        try:
            while True:
                for img, dur in sequence:
                    device.set_key_image(button, img)
                    await asyncio.sleep(dur / 1000.0)
                if not loop:
                    return
        except asyncio.CancelledError:
            pass

    async def stop_animation(
        self, device_id: str, button: int, mode: Literal["freeze", "clear"]
    ) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)
        if mode == "clear":
            d.clear_key(button)

    async def _cancel_animation(self, device_id: str, button: int) -> None:
        task = self._animations.pop((device_id, button), None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("animation task crashed during cancel")

    async def set_brightness(self, device_id: str, value: int) -> None:
        d = self._device(device_id)
        d.set_brightness(value)

    async def purge_device(self, device_id: str) -> None:
        keys = [k for k in self._animations if k[0] == device_id]
        for k in keys:
            await self._cancel_animation(*k)
        self.unregister_device(device_id)
