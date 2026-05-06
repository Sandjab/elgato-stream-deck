"""Concrete Device implementation for the Stream Deck XL."""

import logging
from typing import Optional

from PIL import Image
from StreamDeck.ImageHelpers import PILHelper

from .device import Device, DeviceModel, ImageFormat, KeyCallback

logger = logging.getLogger(__name__)


class XLDevice(Device):
    """Stream Deck XL adapter over the `streamdeck` library."""

    model = DeviceModel.XL
    has_screen = False
    has_dial = False

    def __init__(self, hid_device, id: str) -> None:
        self.id = id
        self._dev = hid_device
        self.key_count = hid_device.key_count()
        fmt = hid_device.key_image_format()
        self.image_size = fmt["size"]
        self.image_format = ImageFormat(str(fmt["format"]).lower())
        self._callback: Optional[KeyCallback] = None
        self._open()

    def _open(self) -> None:
        self._dev.open()
        self._dev.reset()
        self._dev.set_brightness(80)
        self._dev.set_key_callback(self._on_key_change)

    def _on_key_change(self, deck, key: int, pressed: bool) -> None:
        if self._callback:
            try:
                self._callback(key, pressed)
            except Exception:
                logger.exception("XL key callback failed")

    def set_key_image(self, button: int, image: Image.Image) -> None:
        native = PILHelper.to_native_format(self._dev, image)
        self._dev.set_key_image(button, native)

    def clear_key(self, button: int) -> None:
        black = Image.new("RGB", self.image_size, (0, 0, 0))
        self.set_key_image(button, black)

    def set_brightness(self, value: int) -> None:
        self._dev.set_brightness(max(0, min(100, value)))

    def set_key_callback(self, callback: KeyCallback) -> None:
        self._callback = callback

    def close(self) -> None:
        try:
            for k in range(self.key_count):
                self.clear_key(k)
            self._dev.reset()
        finally:
            try:
                self._dev.close()
            except Exception:
                logger.exception("XL close failed")
