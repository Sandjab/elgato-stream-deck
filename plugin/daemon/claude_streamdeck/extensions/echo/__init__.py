"""Echo extension: marks all buttons active and logs presses."""

from __future__ import annotations

import logging
from typing import Optional

from ...core.core_api import CoreAPI

logger = logging.getLogger(__name__)


class Extension:
    def __init__(self) -> None:
        self._api: Optional[CoreAPI] = None

    def init(self, api: CoreAPI) -> None:
        self._api = api
        # Activate all buttons on every currently-attached device.
        for d in api.devices.all():
            for b in range(d.key_count):
                api.input.set_active(d.id, b, True)

        async def on_pressed(payload):
            logger.info("echo: button pressed %s", payload)

        api.events.subscribe("button.pressed", on_pressed)

    def shutdown(self) -> None:
        # Nothing persistent to clean up.
        pass
