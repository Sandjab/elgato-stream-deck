"""Aggregated registration of core handlers."""

from ..core.core_api import CoreAPI
from . import (
    asset_handlers,
    device_handlers,
    display_handlers,
    input_handlers,
    system_handlers,
)


def register_core_handlers(api: CoreAPI) -> None:
    system_handlers.register(api)
    device_handlers.register(api)
    asset_handlers.register(api)
    display_handlers.register(api)
    input_handlers.register(api)
