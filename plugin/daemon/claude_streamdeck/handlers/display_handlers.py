"""display.* handlers: set, clear, animate, stop_animation, brightness."""

from ..core.core_api import CoreAPI
from .device_handlers import _resolve_device


def register(api: CoreAPI) -> None:
    async def set_image(params):
        d = _resolve_device(api, params)
        await api.display.set_image(d.id, params["button"], params["asset"])
        return {}

    async def clear(params):
        d = _resolve_device(api, params)
        await api.display.clear(d.id, params["button"])
        return {}

    async def animate(params):
        d = _resolve_device(api, params)
        await api.display.animate(
            d.id,
            params["button"],
            asset=params.get("asset"),
            frames=params.get("frames"),
            loop=bool(params.get("loop", True)),
        )
        return {}

    async def stop_animation(params):
        d = _resolve_device(api, params)
        await api.display.stop_animation(
            d.id, params["button"], mode=params.get("mode", "freeze")
        )
        return {}

    async def brightness(params):
        d = _resolve_device(api, params)
        await api.display.set_brightness(d.id, int(params["value"]))
        return {}

    api.commands.register("display.set", set_image)
    api.commands.register("display.clear", clear)
    api.commands.register("display.animate", animate)
    api.commands.register("display.stop_animation", stop_animation)
    api.commands.register("display.brightness", brightness)
