"""Tests for DeviceManager (using a fake StreamDeck library)."""

from unittest.mock import MagicMock, patch

import pytest

from claude_streamdeck.core.device import DeviceModel
from claude_streamdeck.core.device_manager import DeviceManager


def _fake_xl(serial="ABCDEF", key_count=32):
    fake = MagicMock()
    fake.deck_type.return_value = "Stream Deck XL"
    fake.key_count.return_value = key_count
    fake.key_image_format.return_value = {"size": (96, 96), "format": "JPEG"}
    fake.get_serial_number.return_value = serial
    fake.open = MagicMock()
    fake.reset = MagicMock()
    fake.set_brightness = MagicMock()
    fake.set_key_callback = MagicMock()
    return fake


def test_enumerate_xl():
    fake = _fake_xl()
    with patch("claude_streamdeck.core.device_manager.DeviceManagerHID") as MgrCls:
        MgrCls.return_value.enumerate.return_value = [fake]
        mgr = DeviceManager()
        devices = mgr.enumerate()
    assert len(devices) == 1
    d = devices[0]
    assert d.model == DeviceModel.XL
    assert d.id == "xl-ABCDEF"
    assert d.key_count == 32
    assert d.image_size == (96, 96)


def test_enumerate_skips_unknown_models():
    fake = MagicMock()
    fake.deck_type.return_value = "Mystery Deck"
    fake.key_count.return_value = 99
    with patch("claude_streamdeck.core.device_manager.DeviceManagerHID") as MgrCls:
        MgrCls.return_value.enumerate.return_value = [fake]
        mgr = DeviceManager()
        devices = mgr.enumerate()
    assert devices == []


def test_get_by_id_returns_device():
    fake = _fake_xl()
    with patch("claude_streamdeck.core.device_manager.DeviceManagerHID") as MgrCls:
        MgrCls.return_value.enumerate.return_value = [fake]
        mgr = DeviceManager()
        mgr.enumerate()
    d = mgr.get("xl-ABCDEF")
    assert d is not None


def test_get_unknown_returns_none():
    with patch("claude_streamdeck.core.device_manager.DeviceManagerHID") as MgrCls:
        MgrCls.return_value.enumerate.return_value = []
        mgr = DeviceManager()
        mgr.enumerate()
    assert mgr.get("missing") is None


def test_first_returns_first_device_or_none():
    fake = _fake_xl(serial="X1")
    with patch("claude_streamdeck.core.device_manager.DeviceManagerHID") as MgrCls:
        MgrCls.return_value.enumerate.return_value = [fake]
        mgr = DeviceManager()
        mgr.enumerate()
    assert mgr.first() is not None
    assert mgr.first().id == "xl-X1"
