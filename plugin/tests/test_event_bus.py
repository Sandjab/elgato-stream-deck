"""Tests for EventBus."""

import asyncio
import threading

import pytest

from claude_streamdeck.core.event_bus import EventBus


async def test_subscribe_and_publish_async():
    bus = EventBus()
    received = []

    async def handler(payload):
        received.append(payload)

    bus.subscribe("topic", handler)
    await bus.publish("topic", {"x": 1})
    await asyncio.sleep(0)  # let task run
    assert received == [{"x": 1}]


async def test_multiple_subscribers_each_receive():
    bus = EventBus()
    a, b = [], []

    async def ha(p): a.append(p)
    async def hb(p): b.append(p)

    bus.subscribe("topic", ha)
    bus.subscribe("topic", hb)
    await bus.publish("topic", "hello")
    await asyncio.sleep(0)
    assert a == ["hello"]
    assert b == ["hello"]


async def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []

    async def handler(p): received.append(p)

    bus.subscribe("topic", handler)
    bus.unsubscribe("topic", handler)
    await bus.publish("topic", "x")
    await asyncio.sleep(0)
    assert received == []


async def test_publish_threadsafe_from_other_thread():
    bus = EventBus()
    received = []

    async def handler(p): received.append(p)

    bus.subscribe("topic", handler)
    bus.bind_loop(asyncio.get_running_loop())

    def from_thread():
        bus.publish_threadsafe("topic", "from-thread")

    t = threading.Thread(target=from_thread)
    t.start()
    t.join()
    await asyncio.sleep(0.05)
    assert received == ["from-thread"]


async def test_handler_exception_does_not_break_bus():
    bus = EventBus()
    received = []

    async def bad(p): raise RuntimeError("boom")
    async def good(p): received.append(p)

    bus.subscribe("topic", bad)
    bus.subscribe("topic", good)
    await bus.publish("topic", 42)
    await asyncio.sleep(0)
    assert received == [42]


async def test_unknown_topic_publish_is_noop():
    bus = EventBus()
    await bus.publish("nobody-listens", 1)  # no exception
