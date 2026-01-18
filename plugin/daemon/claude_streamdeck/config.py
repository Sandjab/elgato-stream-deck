"""Configuration for Claude Code Stream Deck XL Plugin.

Contains paths, constants, and XL-specific specifications.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Tuple


class ClaudeState(Enum):
    """Claude Code session states."""
    INACTIVE = "inactive"
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_RUNNING = "tool_running"


@dataclass
class StreamDeckXLSpecs:
    """Stream Deck XL hardware specifications."""
    PRODUCT_ID: int = 0x006C
    VENDOR_ID: int = 0x0FD9  # Elgato
    KEY_COUNT: int = 32
    KEY_COLS: int = 8
    KEY_ROWS: int = 4
    ICON_SIZE: Tuple[int, int] = (96, 96)
    IMAGE_FORMAT: str = "JPEG"


@dataclass
class ButtonLayout:
    """Button positions for XL layout (8x4 grid)."""
    STATUS: int = 0
    NEW: int = 1
    RESUME: int = 2
    STOP: int = 3
    # Keys 4-31 are available for future use


@dataclass
class StateDisplay:
    """Display configuration for each state."""
    icon: str
    title: str
    color: Tuple[int, int, int]  # RGB background color


# State to display mapping
STATE_DISPLAYS: Dict[ClaudeState, StateDisplay] = {
    ClaudeState.INACTIVE: StateDisplay(
        icon="status-inactive.png",
        title="Offline",
        color=(128, 128, 128)  # Gray
    ),
    ClaudeState.IDLE: StateDisplay(
        icon="status-idle.png",
        title="Ready",
        color=(0, 200, 0)  # Green
    ),
    ClaudeState.THINKING: StateDisplay(
        icon="status-thinking.png",
        title="Thinking...",
        color=(0, 120, 255)  # Blue
    ),
    ClaudeState.TOOL_RUNNING: StateDisplay(
        icon="status-tool.png",
        title="Tool",
        color=(255, 140, 0)  # Orange
    ),
}

# Action button configurations
ACTION_BUTTONS: Dict[str, Dict] = {
    "new": {
        "key": ButtonLayout.NEW,
        "icon": "action-new.png",
        "title": "New",
        "color": (60, 60, 60)
    },
    "resume": {
        "key": ButtonLayout.RESUME,
        "icon": "action-resume.png",
        "title": "Resume",
        "color": (60, 60, 60)
    },
    "stop": {
        "key": ButtonLayout.STOP,
        "icon": "action-stop.png",
        "title": "Stop",
        "color": (60, 60, 60)
    },
}


@dataclass
class Config:
    """Main configuration class."""

    # Paths
    socket_path: Path = field(
        default_factory=lambda: Path.home() / ".claude" / "streamdeck.sock"
    )
    assets_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "assets" / "icons" / "96x96"
    )
    log_path: Path = field(
        default_factory=lambda: Path.home() / ".claude" / "streamdeck.log"
    )

    # Hardware specs
    xl_specs: StreamDeckXLSpecs = field(default_factory=StreamDeckXLSpecs)

    # Button layout
    buttons: ButtonLayout = field(default_factory=ButtonLayout)

    # Display settings
    font_size: int = 14
    font_name: str = "Helvetica"

    # Timeouts
    socket_timeout: float = 5.0
    reconnect_delay: float = 2.0
    flash_duration: float = 0.1

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def get_icon_path(self, icon_name: str) -> Path:
        """Get full path to an icon file."""
        return self.assets_path / icon_name

    def get_state_display(self, state: ClaudeState) -> StateDisplay:
        """Get display configuration for a state."""
        return STATE_DISPLAYS.get(state, STATE_DISPLAYS[ClaudeState.INACTIVE])


# Global configuration instance
config = Config()
