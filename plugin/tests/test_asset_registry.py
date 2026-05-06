"""Tests for AssetRegistry."""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from claude_streamdeck.core.asset_registry import (
    Asset,
    AssetNotFoundError,
    AssetRegistry,
    AssetTooLargeError,
    InvalidAssetDataError,
)


def _png_bytes(color=(255, 0, 0), size=(50, 50)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _gif_bytes_animated(frames=3, size=(40, 40)) -> bytes:
    images = [Image.new("RGB", size, (i * 80, 0, 0)) for i in range(frames)]
    buf = io.BytesIO()
    images[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=100,
        loop=0,
    )
    return buf.getvalue()


def test_upload_static_png():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    data = base64.b64encode(_png_bytes()).decode()
    asset = reg.upload("red", data)
    assert asset.name == "red"
    assert asset.animated is False
    assert asset.frame_count == 1


def test_upload_animated_gif():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    data = base64.b64encode(_gif_bytes_animated(frames=4)).decode()
    asset = reg.upload("spin", data)
    assert asset.animated is True
    assert asset.frame_count == 4
    assert len(asset.frame_durations_ms) == 4


def test_get_unknown_raises():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    with pytest.raises(AssetNotFoundError):
        reg.get("nope")


def test_remove_asset():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    reg.upload("red", base64.b64encode(_png_bytes()).decode())
    reg.remove("red")
    with pytest.raises(AssetNotFoundError):
        reg.get("red")


def test_too_large_rejected():
    reg = AssetRegistry(static_dir=None, max_size_bytes=10)
    with pytest.raises(AssetTooLargeError):
        reg.upload("big", base64.b64encode(_png_bytes()).decode())


def test_invalid_base64_rejected():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    with pytest.raises(InvalidAssetDataError):
        reg.upload("bad", "!!!not-base64!!!")


def test_invalid_image_rejected():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    bad = base64.b64encode(b"not an image at all").decode()
    with pytest.raises(InvalidAssetDataError):
        reg.upload("bad", bad)


def test_resize_cache_hit():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    reg.upload("red", base64.b64encode(_png_bytes(size=(50, 50))).decode())
    a = reg.get_resized("red", (96, 96))
    b = reg.get_resized("red", (96, 96))
    assert a is b  # same cached PIL image instance
    assert a.size == (96, 96)


def test_resize_animated_returns_all_frames():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    reg.upload("spin", base64.b64encode(_gif_bytes_animated(frames=3)).decode())
    frames = reg.get_resized_frames("spin", (96, 96))
    assert len(frames) == 3
    for f in frames:
        assert f.size == (96, 96)


def test_static_dir_loaded_at_init(tmp_path: Path):
    f = tmp_path / "blue.png"
    f.write_bytes(_png_bytes(color=(0, 0, 255)))
    reg = AssetRegistry(static_dir=tmp_path, max_size_bytes=1024 * 1024)
    asset = reg.get("blue")
    assert asset.animated is False


def test_list_assets():
    reg = AssetRegistry(static_dir=None, max_size_bytes=1024 * 1024)
    reg.upload("a", base64.b64encode(_png_bytes()).decode())
    reg.upload("b", base64.b64encode(_png_bytes()).decode())
    items = reg.list()
    names = sorted(i["name"] for i in items)
    assert names == ["a", "b"]
