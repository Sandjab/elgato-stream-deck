"""device.* handlers: list, capabilities."""

from ..core.core_api import CoreAPI


def _device_dict(d) -> dict:
    return {
        "id": d.id,
        "model": d.model.value,
        "key_count": d.key_count,
        "image_size": list(d.image_size),
        "image_format": d.image_format.value,
        "has_screen": d.has_screen,
        "has_dial": d.has_dial,
    }


def _resolve_device(api: CoreAPI, params: dict):
    device_id = params.get("device_id")
    if device_id is None:
        d = api.devices.first()
    else:
        d = api.devices.get(device_id)
    if d is None:
        raise RuntimeError("no_device" if device_id is None else "device_not_found")
    return d


def register(api: CoreAPI) -> None:
    async def list_devices(_params):
        return [_device_dict(d) for d in api.devices.all()]

    async def capabilities(params):
        d = _resolve_device(api, params)
        return _device_dict(d)

    api.commands.register("device.list", list_devices)
    api.commands.register("device.capabilities", capabilities)
