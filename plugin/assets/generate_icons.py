#!/usr/bin/env python3
"""Generate 96x96 PNG icons for Stream Deck XL.

Creates icons for all states and actions with a consistent style.
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw

# Icon size for Stream Deck XL
SIZE = 96
ICON_SIZE = 64  # Inner icon size

# Output directory
OUTPUT_DIR = Path(__file__).parent / "icons" / "96x96"


def create_circle_icon(color: tuple, inner_color: tuple = None) -> Image.Image:
    """Create a circular status icon."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer circle
    padding = 8
    draw.ellipse(
        [padding, padding, SIZE - padding, SIZE - padding],
        fill=color
    )

    # Inner circle highlight
    if inner_color:
        inner_padding = 24
        draw.ellipse(
            [inner_padding, inner_padding, SIZE - inner_padding, SIZE - inner_padding],
            fill=inner_color
        )

    return img


def create_plus_icon() -> Image.Image:
    """Create a plus icon for 'New' action."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Plus shape
    color = (100, 200, 100)  # Green
    thickness = 12
    center = SIZE // 2
    arm_length = 28

    # Horizontal bar
    draw.rectangle(
        [center - arm_length, center - thickness // 2,
         center + arm_length, center + thickness // 2],
        fill=color
    )

    # Vertical bar
    draw.rectangle(
        [center - thickness // 2, center - arm_length,
         center + thickness // 2, center + arm_length],
        fill=color
    )

    return img


def create_play_icon() -> Image.Image:
    """Create a play/triangle icon for 'Resume' action."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Triangle pointing right
    color = (100, 150, 255)  # Blue
    padding = 20

    points = [
        (padding + 10, padding),           # Top left
        (SIZE - padding, SIZE // 2),       # Right point
        (padding + 10, SIZE - padding),    # Bottom left
    ]

    draw.polygon(points, fill=color)

    return img


def create_stop_icon() -> Image.Image:
    """Create a stop/square icon for 'Stop' action."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Square
    color = (255, 100, 100)  # Red
    padding = 24

    draw.rectangle(
        [padding, padding, SIZE - padding, SIZE - padding],
        fill=color
    )

    return img


def create_thinking_icon() -> Image.Image:
    """Create a thinking/dots icon."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Three dots
    color = (100, 180, 255)  # Blue
    dot_radius = 8
    spacing = 24
    center_y = SIZE // 2

    for i in range(3):
        x = SIZE // 2 + (i - 1) * spacing
        draw.ellipse(
            [x - dot_radius, center_y - dot_radius,
             x + dot_radius, center_y + dot_radius],
            fill=color
        )

    return img


def create_tool_icon() -> Image.Image:
    """Create a tool/gear icon."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Simplified gear shape - outer circle with notches
    color = (255, 160, 50)  # Orange
    center = SIZE // 2
    outer_r = 36
    inner_r = 20

    # Draw outer circle
    draw.ellipse(
        [center - outer_r, center - outer_r,
         center + outer_r, center + outer_r],
        fill=color
    )

    # Draw inner circle (hole)
    draw.ellipse(
        [center - inner_r, center - inner_r,
         center + inner_r, center + inner_r],
        fill=(0, 0, 0, 0)
    )

    return img


def main():
    """Generate all icons."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    icons = {
        # Status icons
        "status-inactive.png": create_circle_icon((100, 100, 100), (60, 60, 60)),
        "status-idle.png": create_circle_icon((50, 200, 50), (80, 230, 80)),
        "status-thinking.png": create_thinking_icon(),
        "status-tool.png": create_tool_icon(),

        # Action icons
        "action-new.png": create_plus_icon(),
        "action-resume.png": create_play_icon(),
        "action-stop.png": create_stop_icon(),
    }

    for filename, icon in icons.items():
        path = OUTPUT_DIR / filename
        icon.save(path, "PNG")
        print(f"Created: {path}")

    print(f"\nGenerated {len(icons)} icons in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
