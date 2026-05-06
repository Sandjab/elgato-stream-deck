"""Tests for InputDispatcher."""

import asyncio

import pytest

from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher


def _device():
    return MockDevice(id="xl-1", model=DeviceModel.XL, key_count=32, image_size=(96, 96))


async def test_inactive_button_emits_nothing():
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    received = []

    async def h(payload): received.append(payload)
    bus.subscribe("button.pressed", h)

    dev = _device()
    dispatcher = InputDispatcher(bus)
    dispatcher.attach(dev)
    dev.simulate_press(5, True)
    await asyncio.sleep(0.05)
    assert received == []


async def test_active_button_pressed_emits():
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    received = []

    async def h(payload): received.append(payload)
    bus.subscribe("button.pressed", h)

    dev = _device()
    dispatcher = InputDispatcher(bus)
    dispatcher.attach(dev)
    dispatcher.set_active(dev.id, 5, True)
    dev.simulate_press(5, True)
    await asyncio.sleep(0.05)
    assert received == [{"device_id": "xl-1", "button": 5}]


async def test_active_button_released_emits():
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    received = []

    async def h(payload): received.append(payload)
    bus.subscribe("button.released", h)

    dev = _device()
    dispatcher = InputDispatcher(bus)
    dispatcher.attach(dev)
    dispatcher.set_active(dev.id, 7, True)
    dev.simulate_press(7, False)
    await asyncio.sleep(0.05)
    assert received == [{"device_id": "xl-1", "button": 7}]


async def test_set_inactive_stops_emission():
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    received = []

    async def h(payload): received.append(payload)
    bus.subscribe("button.pressed", h)

    dev = _device()
    dispatcher = InputDispatcher(bus)
    dispatcher.attach(dev)
    dispatcher.set_active(dev.id, 5, True)
    dispatcher.set_active(dev.id, 5, False)
    dev.simulate_press(5, True)
    await asyncio.sleep(0.05)
    assert received == []


async def test_detach_stops_emission():
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    received = []

    async def h(payload): received.append(payload)
    bus.subscribe("button.pressed", h)

    dev = _device()
    dispatcher = InputDispatcher(bus)
    dispatcher.attach(dev)
    dispatcher.set_active(dev.id, 5, True)
    dispatcher.detach(dev.id)
    dev.simulate_press(5, True)
    await asyncio.sleep(0.05)
    assert received == []
