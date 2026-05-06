"""Abstract Device interface and MockDevice for tests."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional

from PIL import Image


class DeviceModel(str, Enum):
    XL = "xl"
    MK2 = "mk2"
    MINI = "mini"
    PLUS = "plus"
    NEO = "neo"
    PEDAL = "pedal"
    ORIGINAL = "original"


class ImageFormat(str, Enum):
    JPEG = "jpeg"
    BMP = "bmp"


KeyCallback = Callable[[int, bool], None]


class Device(ABC):
    """Abstract Stream Deck device. Subclassed by concrete model implementations."""

    id: str
    model: DeviceModel
    key_count: int
    image_size: tuple[int, int]
    image_format: ImageFormat
    has_screen: bool
    has_dial: bool

    @abstractmethod
    def set_key_image(self, button: int, image: Image.Image) -> None: ...

    @abstractmethod
    def clear_key(self, button: int) -> None: ...

    @abstractmethod
    def set_brightness(self, value: int) -> None: ...

    @abstractmethod
    def set_key_callback(self, callback: KeyCallback) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


class MockDevice(Device):
    """In-memory Device for tests. Records all calls; can simulate presses."""

    def __init__(
        self,
        id: str,
        model: DeviceModel,
        key_count: int,
        image_size: tuple[int, int],
        image_format: ImageFormat = ImageFormat.JPEG,
        has_screen: bool = False,
        has_dial: bool = False,
    ) -> None:
        self.id = id
        self.model = model
        self.key_count = key_count
        self.image_size = image_size
        self.image_format = image_format
        self.has_screen = has_screen
        self.has_dial = has_dial

        self.set_key_calls: list[tuple[int, Image.Image]] = []
        self.cleared_keys: list[int] = []
        self.brightness: Optional[int] = None
        self._callback: Optional[KeyCallback] = None
        self.closed = False

    def set_key_image(self, button: int, image: Image.Image) -> None:
        self.set_key_calls.append((button, image))

    def last_image_for(self, button: int) -> Optional[Image.Image]:
        for k, img in reversed(self.set_key_calls):
            if k == button:
                return img
        return None

    def clear_key(self, button: int) -> None:
        self.cleared_keys.append(button)

    def set_brightness(self, value: int) -> None:
        self.brightness = value

    def set_key_callback(self, callback: KeyCallback) -> None:
        self._callback = callback

    def simulate_press(self, button: int, pressed: bool) -> None:
        if self._callback:
            self._callback(button, pressed)

    def close(self) -> None:
        self.closed = True
