"""Async pub/sub event bus, with thread-safe publish for HID callbacks."""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[None]]


class EventBus:
    """Topic-based pub/sub. Handlers are async; publish dispatches concurrently."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the event loop used by `publish_threadsafe`."""
        self._loop = loop

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        if handler in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(handler)

    async def publish(self, topic: str, payload: Any) -> None:
        """Publish from inside the event loop. Awaits all handlers."""
        handlers = list(self._subscribers.get(topic, []))
        for h in handlers:
            try:
                await h(payload)
            except Exception:
                logger.exception("EventBus handler for %r raised", topic)

    def publish_threadsafe(self, topic: str, payload: Any) -> None:
        """Publish from a non-asyncio thread. Requires `bind_loop` to have been called."""
        if self._loop is None:
            logger.warning("publish_threadsafe called before bind_loop; dropping %r", topic)
            return
        asyncio.run_coroutine_threadsafe(
            self.publish(topic, payload), self._loop
        )
