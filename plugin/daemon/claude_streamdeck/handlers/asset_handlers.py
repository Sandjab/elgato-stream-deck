"""asset.* handlers: upload, remove, list."""

from ..core.core_api import CoreAPI


def register(api: CoreAPI) -> None:
    async def upload(params):
        name = params["name"]
        data = params["data"]
        a = api.assets.upload(name, data)
        return {"name": a.name, "animated": a.animated, "frame_count": a.frame_count}

    async def remove(params):
        api.assets.remove(params["name"])
        return {}

    async def list_assets(_params):
        return api.assets.list()

    api.commands.register("asset.upload", upload)
    api.commands.register("asset.remove", remove)
    api.commands.register("asset.list", list_assets)
