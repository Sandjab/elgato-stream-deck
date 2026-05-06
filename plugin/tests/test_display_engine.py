"""Tests for DisplayEngine."""

import asyncio
import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.core.display_engine import (
    ButtonOutOfRangeError,
    DisplayEngine,
)


def _png(color=(10, 20, 30), size=(50, 50)) -> str:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _gif(frames=3, size=(40, 40)) -> str:
    images = [Image.new("RGB", size, (i * 80, 0, 0)) for i in range(frames)]
    buf = io.BytesIO()
    images[0].save(
        buf, format="GIF", save_all=True, append_images=images[1:],
        duration=20, loop=0,
    )
    return base64.b64encode(buf.getvalue()).decode()


def _make():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    dev = MockDevice(id="xl-1", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    eng = DisplayEngine(reg)
    eng.register_device(dev)
    return reg, dev, eng


async def test_set_image_pushes_to_device():
    reg, dev, eng = _make()
    reg.upload("a", _png())
    await eng.set_image(dev.id, 5, "a")
    assert dev.last_image_for(5) is not None
    assert dev.last_image_for(5).size == (96, 96)


async def test_set_image_unknown_asset_raises():
    reg, dev, eng = _make()
    from claude_streamdeck.core.asset_registry import AssetNotFoundError
    with pytest.raises(AssetNotFoundError):
        await eng.set_image(dev.id, 0, "nope")


async def test_clear_image_calls_device():
    reg, dev, eng = _make()
    await eng.clear(dev.id, 3)
    assert 3 in dev.cleared_keys


async def test_button_out_of_range():
    reg, dev, eng = _make()
    reg.upload("a", _png())
    with pytest.raises(ButtonOutOfRangeError):
        await eng.set_image(dev.id, 99, "a")


async def test_animate_cycles_frames():
    reg, dev, eng = _make()
    reg.upload("g", _gif(frames=3))
    await eng.animate(dev.id, 0, asset="g", loop=True)
    await asyncio.sleep(0.1)  # allow several frame swaps (each frame ~20ms)
    await eng.stop_animation(dev.id, 0, mode="freeze")
    # at least 2 different frames were pushed
    images = [img for k, img in dev.set_key_calls if k == 0]
    assert len(images) >= 2


async def test_set_image_cancels_running_animation():
    reg, dev, eng = _make()
    reg.upload("g", _gif(frames=3))
    reg.upload("s", _png())
    await eng.animate(dev.id, 0, asset="g", loop=True)
    await asyncio.sleep(0.05)
    await eng.set_image(dev.id, 0, "s")
    # after set_image, the static frame is the last one pushed
    last = dev.last_image_for(0)
    # static asset is uniform color; check by sampling a pixel
    assert last.getpixel((10, 10)) == (10, 20, 30)


async def test_stop_animation_clear_mode():
    reg, dev, eng = _make()
    reg.upload("g", _gif(frames=3))
    await eng.animate(dev.id, 0, asset="g", loop=True)
    await asyncio.sleep(0.05)
    await eng.stop_animation(dev.id, 0, mode="clear")
    assert 0 in dev.cleared_keys


async def test_set_brightness_passthrough():
    reg, dev, eng = _make()
    await eng.set_brightness(dev.id, 60)
    assert dev.brightness == 60


async def test_purge_device_stops_animations():
    reg, dev, eng = _make()
    reg.upload("g", _gif(frames=3))
    await eng.animate(dev.id, 0, asset="g", loop=True)
    await asyncio.sleep(0.02)
    await eng.purge_device(dev.id)
    # after purge, no further set_key_calls for button 0 should appear
    pre = len([1 for k, _ in dev.set_key_calls if k == 0])
    await asyncio.sleep(0.1)
    post = len([1 for k, _ in dev.set_key_calls if k == 0])
    assert pre == post
