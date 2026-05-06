"""Routes HID button events to the EventBus, gated by per-button active state."""

import logging

from .device import Device
from .event_bus import EventBus

logger = logging.getLogger(__name__)


class InputDispatcher:
    """Per-device button state and HID-to-bus bridge."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._active: dict[str, set[int]] = {}  # device_id -> set of active buttons
        self._devices: dict[str, Device] = {}

    def attach(self, device: Device) -> None:
        self._devices[device.id] = device
        self._active.setdefault(device.id, set())
        device.set_key_callback(self._make_callback(device.id))

    def detach(self, device_id: str) -> None:
        self._devices.pop(device_id, None)
        self._active.pop(device_id, None)

    def set_active(self, device_id: str, button: int, active: bool) -> None:
        s = self._active.setdefault(device_id, set())
        if active:
            s.add(button)
        else:
            s.discard(button)

    def _make_callback(self, device_id: str):
        def cb(button: int, pressed: bool) -> None:
            if button not in self._active.get(device_id, set()):
                return
            topic = "button.pressed" if pressed else "button.released"
            self._bus.publish_threadsafe(
                topic, {"device_id": device_id, "button": button}
            )
        return cb
