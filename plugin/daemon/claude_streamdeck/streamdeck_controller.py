"""Stream Deck XL USB HID controller.

Interfaces with Stream Deck XL hardware for displaying icons and
handling button presses.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Devices.StreamDeck import StreamDeck

from .config import (
    ACTION_BUTTONS,
    ButtonLayout,
    ClaudeState,
    Config,
    STATE_DISPLAYS,
    StreamDeckXLSpecs,
)

logger = logging.getLogger(__name__)

# Type alias for key press callback
KeyCallback = Callable[[int, bool], None]


class StreamDeckController:
    """Controls Stream Deck XL hardware via USB HID.

    Handles device connection, icon rendering, and button press events.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the controller.

        Args:
            config: Configuration instance
        """
        self.config = config
        self.specs = config.xl_specs
        self._deck: Optional[StreamDeck] = None
        self._key_callback: Optional[KeyCallback] = None
        self._current_state = ClaudeState.INACTIVE
        self._current_tool: Optional[str] = None
        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._icon_cache: Dict[str, Image.Image] = {}

    def connect(self) -> bool:
        """Connect to Stream Deck XL.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            devices = DeviceManager().enumerate()

            if not devices:
                logger.warning("No Stream Deck devices found")
                return False

            # Find Stream Deck XL by product ID
            for device in devices:
                device.open()
                device.reset()

                # Check if it's an XL model
                deck_type = device.deck_type()
                key_count = device.key_count()

                logger.info(f"Found device: {deck_type} with {key_count} keys")

                if key_count == self.specs.KEY_COUNT:
                    logger.info(f"Connected to Stream Deck XL")
                    self._deck = device
                    self._setup_device()
                    return True
                else:
                    device.close()

            logger.warning("Stream Deck XL not found (need 32-key device)")
            return False

        except Exception as e:
            logger.error(f"Failed to connect to Stream Deck: {e}")
            return False

    def _setup_device(self) -> None:
        """Configure the connected device."""
        if not self._deck:
            return

        # Set brightness
        self._deck.set_brightness(80)

        # Register key callback
        self._deck.set_key_callback(self._on_key_change)

        # Load font
        self._load_font()

        # Initialize display
        self._initialize_display()

    def _load_font(self) -> None:
        """Load font for text rendering."""
        try:
            # Try system fonts
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
            ]

            for font_path in font_paths:
                if Path(font_path).exists():
                    self._font = ImageFont.truetype(font_path, self.config.font_size)
                    logger.debug(f"Loaded font: {font_path}")
                    return

            # Fallback to default
            self._font = ImageFont.load_default()
            logger.debug("Using default font")

        except Exception as e:
            logger.warning(f"Failed to load font: {e}")
            self._font = ImageFont.load_default()

    def _initialize_display(self) -> None:
        """Initialize the display with default icons."""
        # Set status icon
        self.update_state(ClaudeState.INACTIVE)

        # Set action buttons
        for action_name, action_config in ACTION_BUTTONS.items():
            self._set_action_button(
                action_config["key"],
                action_config["icon"],
                action_config["title"],
                action_config["color"]
            )

        # Clear remaining keys
        for key in range(4, self.specs.KEY_COUNT):
            self._clear_key(key)

    def _clear_key(self, key: int) -> None:
        """Clear a key to black."""
        if not self._deck:
            return

        image = Image.new("RGB", self.specs.ICON_SIZE, (0, 0, 0))
        self._set_key_image(key, image)

    def disconnect(self) -> None:
        """Disconnect from Stream Deck."""
        if self._deck:
            try:
                # Clear all keys
                for key in range(self.specs.KEY_COUNT):
                    self._clear_key(key)

                self._deck.reset()
                self._deck.close()
                logger.info("Disconnected from Stream Deck")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self._deck = None

    def set_key_callback(self, callback: KeyCallback) -> None:
        """Set callback for key press events.

        Args:
            callback: Function(key_index, pressed) to call on key events
        """
        self._key_callback = callback

    def _on_key_change(self, deck: StreamDeck, key: int, pressed: bool) -> None:
        """Internal handler for key press events."""
        logger.debug(f"Key {key} {'pressed' if pressed else 'released'}")

        if self._key_callback:
            try:
                self._key_callback(key, pressed)
            except Exception as e:
                logger.error(f"Error in key callback: {e}")

    def update_state(
        self,
        state: ClaudeState,
        tool_name: Optional[str] = None
    ) -> None:
        """Update the status display.

        Args:
            state: New state to display
            tool_name: Optional tool name for TOOL_RUNNING state
        """
        if not self._deck:
            return

        self._current_state = state
        self._current_tool = tool_name

        display = STATE_DISPLAYS[state]

        # Determine title text
        if state == ClaudeState.TOOL_RUNNING and tool_name:
            title = self._truncate_text(tool_name, 10)
        else:
            title = display.title

        # Create and set the image
        self._set_status_button(display.icon, title, display.color)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to fit display."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 1] + "..."

    def _set_status_button(
        self,
        icon_name: str,
        title: str,
        bg_color: Tuple[int, int, int]
    ) -> None:
        """Set the status button (key 0) display."""
        image = self._render_button(icon_name, title, bg_color)
        self._set_key_image(ButtonLayout.STATUS, image)

    def _set_action_button(
        self,
        key: int,
        icon_name: str,
        title: str,
        bg_color: Tuple[int, int, int]
    ) -> None:
        """Set an action button display."""
        image = self._render_button(icon_name, title, bg_color)
        self._set_key_image(key, image)

    def _render_button(
        self,
        icon_name: str,
        title: str,
        bg_color: Tuple[int, int, int]
    ) -> Image.Image:
        """Render a button image with icon and title.

        Args:
            icon_name: Name of icon file
            title: Text to display below icon
            bg_color: Background color (RGB)

        Returns:
            PIL Image ready for Stream Deck
        """
        size = self.specs.ICON_SIZE

        # Create base image with background color
        image = Image.new("RGB", size, bg_color)
        draw = ImageDraw.Draw(image)

        # Load and composite icon
        icon = self._load_icon(icon_name)
        if icon:
            # Center icon in upper portion
            icon_size = (64, 64)
            icon_resized = icon.resize(icon_size, Image.Resampling.LANCZOS)

            # Calculate position (centered horizontally, upper third vertically)
            x = (size[0] - icon_size[0]) // 2
            y = 8

            # Handle transparency
            if icon_resized.mode == "RGBA":
                image.paste(icon_resized, (x, y), icon_resized)
            else:
                image.paste(icon_resized, (x, y))

        # Draw title text
        if title and self._font:
            # Get text bounding box
            bbox = draw.textbbox((0, 0), title, font=self._font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Center text at bottom
            x = (size[0] - text_width) // 2
            y = size[1] - text_height - 8

            draw.text((x, y), title, font=self._font, fill=(255, 255, 255))

        return image

    def _load_icon(self, icon_name: str) -> Optional[Image.Image]:
        """Load an icon from cache or file.

        Args:
            icon_name: Name of icon file

        Returns:
            PIL Image or None if not found
        """
        # Check cache
        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name].copy()

        # Load from file
        icon_path = self.config.get_icon_path(icon_name)

        if not icon_path.exists():
            logger.warning(f"Icon not found: {icon_path}")
            return None

        try:
            icon = Image.open(icon_path)
            icon = icon.convert("RGBA")
            self._icon_cache[icon_name] = icon
            return icon.copy()
        except Exception as e:
            logger.error(f"Failed to load icon {icon_name}: {e}")
            return None

    def _set_key_image(self, key: int, image: Image.Image) -> None:
        """Set the image for a specific key.

        Args:
            key: Key index (0-31)
            image: PIL Image to display
        """
        if not self._deck:
            return

        try:
            # Convert to native format
            native_image = PILHelper.to_native_format(self._deck, image)
            self._deck.set_key_image(key, native_image)
        except Exception as e:
            logger.error(f"Failed to set key {key} image: {e}")

    async def flash_key(self, key: int, duration: float = 0.1) -> None:
        """Flash a key briefly to provide feedback.

        Args:
            key: Key index to flash
            duration: Flash duration in seconds
        """
        if not self._deck:
            return

        try:
            # Create bright flash image
            flash_image = Image.new("RGB", self.specs.ICON_SIZE, (255, 255, 255))
            self._set_key_image(key, flash_image)

            # Wait
            await asyncio.sleep(duration)

            # Restore original
            if key == ButtonLayout.STATUS:
                self.update_state(self._current_state, self._current_tool)
            elif key in [b["key"] for b in ACTION_BUTTONS.values()]:
                # Find and restore action button
                for action_config in ACTION_BUTTONS.values():
                    if action_config["key"] == key:
                        self._set_action_button(
                            key,
                            action_config["icon"],
                            action_config["title"],
                            action_config["color"]
                        )
                        break
        except Exception as e:
            logger.error(f"Error flashing key {key}: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._deck is not None

    @property
    def current_state(self) -> ClaudeState:
        """Get current displayed state."""
        return self._current_state
