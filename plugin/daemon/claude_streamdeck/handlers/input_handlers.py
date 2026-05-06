"""input.* handlers: set_active. (subscribe/unsubscribe live in SocketServer.)"""

from ..core.core_api import CoreAPI
from .device_handlers import _resolve_device


def register(api: CoreAPI) -> None:
    async def set_active(params):
        d = _resolve_device(api, params)
        api.input.set_active(d.id, int(params["button"]), bool(params["active"]))
        return {}

    api.commands.register("input.set_active", set_active)
