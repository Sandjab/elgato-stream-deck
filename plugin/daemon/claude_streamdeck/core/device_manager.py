"""Enumerates connected Stream Decks and yields concrete Devices."""

import logging
from typing import Optional

from StreamDeck.DeviceManager import DeviceManager as DeviceManagerHID

from .device import Device, DeviceModel
from .device_xl import XLDevice

logger = logging.getLogger(__name__)


_MODEL_BY_DECK_TYPE = {
    "Stream Deck XL": DeviceModel.XL,
}


class DeviceManager:
    """Enumerates HID Stream Decks and wraps them as Device instances."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        # Maps stable HID-level id (DevSrvsID:... on macOS) to our dev_id, so the
        # reconnect loop can skip devices we've already wrapped without retrying
        # `hid.open()` on them (which the lib rejects on a second call).
        self._known_hid_ids: dict[str, str] = {}

    def enumerate(self) -> list[Device]:
        out: list[Device] = []
        try:
            raw = DeviceManagerHID().enumerate()
        except Exception:
            logger.exception("HID enumerate failed")
            return out
        for hid in raw:
            try:
                hid_id = hid.id()  # stable, no open required
                if hid_id in self._known_hid_ids:
                    continue
                deck_type = hid.deck_type()
                model = _MODEL_BY_DECK_TYPE.get(deck_type)
                if model is None:
                    logger.info("Skipping unsupported model: %s", deck_type)
                    continue
                # Reading the serial requires the HID handle to be open.
                hid.open()
                serial = hid.get_serial_number().strip().strip("\x00")
                dev_id = f"{model.value}-{serial}"
                device: Device
                if model == DeviceModel.XL:
                    device = XLDevice(hid, id=dev_id)
                else:
                    continue  # other models not implemented yet
                self._devices[dev_id] = device
                self._known_hid_ids[hid_id] = dev_id
                out.append(device)
            except Exception:
                logger.exception("Failed to wrap HID device")
        return out

    def get(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)

    def first(self) -> Optional[Device]:
        for d in self._devices.values():
            return d
        return None

    def all(self) -> list[Device]:
        return list(self._devices.values())

    def remove(self, device_id: str) -> None:
        d = self._devices.pop(device_id, None)
        if d is not None:
            try:
                d.close()
            except Exception:
                logger.exception("Failed to close device %s", device_id)
        # Forget the HID id mapping so a future reconnect can re-wrap.
        for hid_id, mapped in list(self._known_hid_ids.items()):
            if mapped == device_id:
                del self._known_hid_ids[hid_id]
