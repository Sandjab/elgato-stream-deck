"""system.* handlers: ping, version."""

from .. import __version__
from ..core.core_api import CoreAPI


def register(api: CoreAPI) -> None:
    async def ping(_params): return {"pong": True}

    async def version(_params):
        return {
            "version": __version__,
            "extensions": list(api.config.get("loaded_extensions", [])),
        }

    api.commands.register("system.ping", ping)
    api.commands.register("system.version", version)
