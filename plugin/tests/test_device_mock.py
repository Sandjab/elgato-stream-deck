"""Tests for the Device abstract interface and MockDevice."""

from PIL import Image

from claude_streamdeck.core.device import (
    Device,
    DeviceModel,
    ImageFormat,
    MockDevice,
)


def test_mock_device_capabilities():
    d = MockDevice(id="xl-mock", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    assert isinstance(d, Device)
    assert d.id == "xl-mock"
    assert d.model == DeviceModel.XL
    assert d.key_count == 32
    assert d.image_size == (96, 96)
    assert d.image_format == ImageFormat.JPEG  # default for XL
    assert d.has_screen is False
    assert d.has_dial is False


def test_mock_device_records_set_key_image():
    d = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    img = Image.new("RGB", (96, 96), (1, 2, 3))
    d.set_key_image(5, img)
    assert d.last_image_for(5) is img
    assert d.set_key_calls == [(5, img)]


def test_mock_device_clear_key_records():
    d = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    d.clear_key(7)
    assert d.cleared_keys == [7]


def test_mock_device_set_brightness():
    d = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    d.set_brightness(50)
    assert d.brightness == 50


def test_mock_device_invokes_callback_on_simulate_press():
    d = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    events = []
    d.set_key_callback(lambda k, p: events.append((k, p)))
    d.simulate_press(3, True)
    d.simulate_press(3, False)
    assert events == [(3, True), (3, False)]
