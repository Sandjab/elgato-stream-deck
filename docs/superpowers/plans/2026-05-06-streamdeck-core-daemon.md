# Stream Deck Core Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the POC's Claude-Code-specific Stream Deck daemon with a generic, multi-model, extensible core daemon that exposes atomic JSON primitives over a Unix socket and can be extended by in-process Python modules.

**Architecture:** Mono-process Python `asyncio` daemon. A pure core (DeviceManager, AssetRegistry, DisplayEngine, InputDispatcher, EventBus, CommandRegistry) sits behind a JSONL socket transport. Extensions are Python modules loaded by config that receive a `CoreAPI` façade and may register their own JSON commands. No business logic in the core.

**Tech Stack:** Python 3.11+ (for `tomllib`), `asyncio`, `streamdeck` (USB HID lib), `pillow` (image processing), `pytest` + `pytest-asyncio` (testing).

**Spec reference:** `docs/superpowers/specs/2026-05-06-streamdeck-core-daemon-design.md`

---

## Working Notes for the Implementing Engineer

- The repo already has a `.venv/` at the root with all deps installed (`streamdeck`, `pillow`, `pytest`, `pytest-asyncio`). Always run commands via `.venv/bin/python …` or activate it.
- The existing POC code under `plugin/daemon/claude_streamdeck/` (files: `actions.py`, `state_machine.py`, `streamdeck_controller.py`, `socket_server.py`, `daemon.py`, `config.py`) **is replaced wholesale** by this plan. Existing tests under `plugin/tests/` (`test_socket_server.py`, `test_state_machine.py`) target the old code and are also removed.
- Run tests from the repo root with: `.venv/bin/python -m pytest plugin/tests/ -v`. The `plugin/pytest.ini` is already configured for asyncio auto mode.
- Existing `plugin/tests/conftest.py` adds `plugin/daemon` to `sys.path` — keep this.
- Commit style in this repo is simple imperative ("Add X", "Implement Y") — no conventional prefix.
- All new files use 4-space indent, type hints, and Python ≥ 3.11 syntax. Module docstrings on every file.
- `EventBus` and `InputDispatcher` MUST be thread-safe: HID callbacks come from a non-asyncio thread inside the `streamdeck` lib. The pattern is `loop.call_soon_threadsafe(...)`.

---

## File Structure

```
plugin/daemon/claude_streamdeck/
├── __init__.py                    # version string only
├── __main__.py                    # CLI entry
├── config.py                      # TOML config loader
├── daemon.py                      # orchestrator: start/stop, wire components
│
├── core/
│   ├── __init__.py
│   ├── core_api.py                # façade exposed to extensions
│   ├── event_bus.py               # async pub/sub, thread-safe publish
│   ├── command_registry.py        # {name: handler}, dispatch, fail-fast on conflict
│   ├── asset_registry.py          # name → PIL.Image (static + animated), redim cache
│   ├── device.py                  # Device base class + DeviceModel enum + ImageFormat
│   ├── device_xl.py               # XL implementation using `streamdeck` lib
│   ├── device_manager.py          # enumerate, connect, reconnect loop, registry by id
│   ├── display_engine.py          # set_image, animate, stop_animation per (device, button)
│   └── input_dispatcher.py        # active flag per button, HID → EventBus bridge
│
├── transport/
│   ├── __init__.py
│   ├── connection.py              # one client connection: reader/writer, subscriptions
│   └── socket_server.py           # asyncio Unix server, JSONL, multi-client
│
├── handlers/
│   ├── __init__.py
│   ├── system_handlers.py         # ping, version
│   ├── device_handlers.py         # list, capabilities
│   ├── asset_handlers.py          # upload, remove, list
│   ├── display_handlers.py        # set, clear, animate, stop_animation, brightness
│   └── input_handlers.py          # set_active, subscribe, unsubscribe
│
└── extensions/
    ├── __init__.py                # extension loader
    └── echo/
        └── __init__.py            # echo demo extension

plugin/tests/
├── __init__.py
├── conftest.py                    # kept (sys.path setup)
├── test_event_bus.py
├── test_command_registry.py
├── test_asset_registry.py
├── test_device_mock.py
├── test_display_engine.py
├── test_input_dispatcher.py
├── test_connection.py
├── test_socket_server.py          # rewritten for JSONL persistent
├── test_handlers.py
├── test_extension_loading.py
└── test_protocol_e2e.py           # E2E over socket with mock device
```

---

## Task 0: Wipe POC code and prepare clean slate

**Files:**
- Delete: `plugin/daemon/claude_streamdeck/actions.py`
- Delete: `plugin/daemon/claude_streamdeck/state_machine.py`
- Delete: `plugin/daemon/claude_streamdeck/streamdeck_controller.py`
- Delete: `plugin/daemon/claude_streamdeck/socket_server.py`
- Delete: `plugin/daemon/claude_streamdeck/daemon.py`
- Delete: `plugin/daemon/claude_streamdeck/config.py`
- Delete: `plugin/daemon/claude_streamdeck/__main__.py`
- Delete: `plugin/tests/test_socket_server.py`
- Delete: `plugin/tests/test_state_machine.py`
- Modify: `plugin/daemon/claude_streamdeck/__init__.py` (reset to version only)

- [ ] **Step 1: Delete the obsolete POC files**

```bash
rm plugin/daemon/claude_streamdeck/actions.py \
   plugin/daemon/claude_streamdeck/state_machine.py \
   plugin/daemon/claude_streamdeck/streamdeck_controller.py \
   plugin/daemon/claude_streamdeck/socket_server.py \
   plugin/daemon/claude_streamdeck/daemon.py \
   plugin/daemon/claude_streamdeck/config.py \
   plugin/daemon/claude_streamdeck/__main__.py \
   plugin/tests/test_socket_server.py \
   plugin/tests/test_state_machine.py
```

- [ ] **Step 2: Reset `__init__.py`**

Replace contents of `plugin/daemon/claude_streamdeck/__init__.py`:

```python
"""Stream Deck core daemon — generic, extensible, multi-model."""

__version__ = "0.2.0"
```

- [ ] **Step 3: Create empty package directories**

```bash
mkdir -p plugin/daemon/claude_streamdeck/core \
         plugin/daemon/claude_streamdeck/transport \
         plugin/daemon/claude_streamdeck/handlers \
         plugin/daemon/claude_streamdeck/extensions/echo
touch plugin/daemon/claude_streamdeck/core/__init__.py \
      plugin/daemon/claude_streamdeck/transport/__init__.py \
      plugin/daemon/claude_streamdeck/handlers/__init__.py \
      plugin/daemon/claude_streamdeck/extensions/__init__.py \
      plugin/daemon/claude_streamdeck/extensions/echo/__init__.py
```

- [ ] **Step 4: Confirm test suite is empty and passes**

Run: `.venv/bin/python -m pytest plugin/tests/ -v`
Expected: `no tests ran` (or equivalent), exit code 0 or 5 (pytest's "no tests collected" code). Either is acceptable here.

- [ ] **Step 5: Commit**

```bash
git add -A plugin/
git commit -m "Remove POC code to prepare for core daemon rewrite"
```

---

## Task 1: EventBus

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/event_bus.py`
- Test: `plugin/tests/test_event_bus.py`

The `EventBus` is a simple async pub/sub. Subscribers register a coroutine for a topic; publishers push payloads. Crucially, `publish_threadsafe` must work when called from a non-asyncio thread (HID callback).

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_event_bus.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_event_bus.py -v`
Expected: All 6 tests FAIL with `ModuleNotFoundError` for `claude_streamdeck.core.event_bus`.

- [ ] **Step 3: Implement EventBus**

Create `plugin/daemon/claude_streamdeck/core/event_bus.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_event_bus.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/event_bus.py plugin/tests/test_event_bus.py
git commit -m "Add EventBus with async and thread-safe publish"
```

---

## Task 2: CommandRegistry

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/command_registry.py`
- Test: `plugin/tests/test_command_registry.py`

Maps command names to async handlers. Conflict on register raises (fail-fast). Unknown command on dispatch returns a structured error.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_command_registry.py`:

```python
"""Tests for CommandRegistry."""

import pytest

from claude_streamdeck.core.command_registry import (
    CommandRegistry,
    DuplicateCommandError,
)


async def test_register_and_dispatch():
    reg = CommandRegistry()

    async def handler(params):
        return {"echoed": params}

    reg.register("system.ping", handler)
    result = await reg.dispatch("system.ping", {"x": 1})
    assert result == {"echoed": {"x": 1}}


async def test_duplicate_raises():
    reg = CommandRegistry()
    async def h(p): return None
    reg.register("foo", h)
    with pytest.raises(DuplicateCommandError):
        reg.register("foo", h)


async def test_unknown_command_raises():
    from claude_streamdeck.core.command_registry import UnknownCommandError
    reg = CommandRegistry()
    with pytest.raises(UnknownCommandError):
        await reg.dispatch("nope", {})


def test_list_commands():
    reg = CommandRegistry()
    async def h(p): return None
    reg.register("a", h)
    reg.register("b", h)
    assert sorted(reg.list_commands()) == ["a", "b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_command_registry.py -v`
Expected: 4 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement CommandRegistry**

Create `plugin/daemon/claude_streamdeck/core/command_registry.py`:

```python
"""Maps command names to async handlers; dispatches with structured errors."""

from typing import Any, Awaitable, Callable

Handler = Callable[[dict[str, Any]], Awaitable[Any]]


class DuplicateCommandError(Exception):
    """Raised when a command name is registered twice."""


class UnknownCommandError(Exception):
    """Raised when dispatching an unregistered command."""


class CommandRegistry:
    """In-memory registry mapping `cmd` strings to handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        if name in self._handlers:
            raise DuplicateCommandError(name)
        self._handlers[name] = handler

    async def dispatch(self, name: str, params: dict[str, Any]) -> Any:
        handler = self._handlers.get(name)
        if handler is None:
            raise UnknownCommandError(name)
        return await handler(params)

    def list_commands(self) -> list[str]:
        return list(self._handlers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_command_registry.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/command_registry.py plugin/tests/test_command_registry.py
git commit -m "Add CommandRegistry with duplicate detection and structured errors"
```

---

## Task 3: AssetRegistry

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/asset_registry.py`
- Test: `plugin/tests/test_asset_registry.py`

Stores images by name. Three sources: a static dir loaded at startup, dynamic uploads from base64, and a resize cache. Detects multi-frame GIFs as animated assets (frames + per-frame durations).

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_asset_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_asset_registry.py -v`
Expected: 11 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement AssetRegistry**

Create `plugin/daemon/claude_streamdeck/core/asset_registry.py`:

```python
"""Asset storage with static-dir loading, dynamic uploads, and resize cache."""

import base64
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


class AssetNotFoundError(Exception):
    pass


class AssetTooLargeError(Exception):
    pass


class InvalidAssetDataError(Exception):
    pass


@dataclass
class Asset:
    """A loaded asset, either single-frame or animated."""
    name: str
    frames: list[Image.Image]
    frame_durations_ms: list[int]
    size_bytes: int

    @property
    def animated(self) -> bool:
        return len(self.frames) > 1

    @property
    def frame_count(self) -> int:
        return len(self.frames)


class AssetRegistry:
    """Stores assets by name; provides resized variants from a cache."""

    def __init__(
        self,
        static_dir: Optional[Path],
        max_size_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self._assets: dict[str, Asset] = {}
        self._resize_cache: dict[tuple[str, tuple[int, int], int], Image.Image] = {}
        self._max_size = max_size_bytes
        if static_dir is not None and static_dir.is_dir():
            self._load_static(static_dir)

    def _load_static(self, dir_path: Path) -> None:
        for f in sorted(dir_path.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif"):
                continue
            try:
                data = f.read_bytes()
                asset = self._build_asset(f.stem, data)
                self._assets[asset.name] = asset
                logger.info("Loaded static asset: %s", asset.name)
            except Exception:
                logger.exception("Failed to load static asset %s", f)

    def upload(self, name: str, data_b64: str) -> Asset:
        try:
            raw = base64.b64decode(data_b64, validate=True)
        except Exception as e:
            raise InvalidAssetDataError(f"base64 decode failed: {e}") from e
        if len(raw) > self._max_size:
            raise AssetTooLargeError(f"{len(raw)} > {self._max_size}")
        asset = self._build_asset(name, raw)
        # Invalidate any previously cached resizes for this name.
        self._invalidate_resize_cache(name)
        self._assets[name] = asset
        return asset

    def _build_asset(self, name: str, raw: bytes) -> Asset:
        try:
            img = Image.open(io.BytesIO(raw))
            img.load()
        except (UnidentifiedImageError, OSError) as e:
            raise InvalidAssetDataError(f"image decode failed: {e}") from e

        frames: list[Image.Image] = []
        durations: list[int] = []
        try:
            n_frames = getattr(img, "n_frames", 1)
        except Exception:
            n_frames = 1

        for i in range(n_frames):
            img.seek(i)
            frame = img.convert("RGB")
            frames.append(frame.copy())
            duration = img.info.get("duration", 100)
            durations.append(int(duration) if duration else 100)

        return Asset(
            name=name,
            frames=frames,
            frame_durations_ms=durations,
            size_bytes=len(raw),
        )

    def get(self, name: str) -> Asset:
        asset = self._assets.get(name)
        if asset is None:
            raise AssetNotFoundError(name)
        return asset

    def remove(self, name: str) -> None:
        if name in self._assets:
            del self._assets[name]
            self._invalidate_resize_cache(name)

    def list(self) -> list[dict]:
        return [
            {"name": a.name, "animated": a.animated, "size_bytes": a.size_bytes}
            for a in self._assets.values()
        ]

    def get_resized(self, name: str, target_size: tuple[int, int]) -> Image.Image:
        return self.get_resized_frames(name, target_size)[0]

    def get_resized_frames(
        self, name: str, target_size: tuple[int, int]
    ) -> list[Image.Image]:
        asset = self.get(name)
        out: list[Image.Image] = []
        for idx, frame in enumerate(asset.frames):
            key = (name, target_size, idx)
            cached = self._resize_cache.get(key)
            if cached is None:
                cached = frame.resize(target_size, Image.Resampling.LANCZOS)
                self._resize_cache[key] = cached
            out.append(cached)
        return out

    def _invalidate_resize_cache(self, name: str) -> None:
        keys = [k for k in self._resize_cache if k[0] == name]
        for k in keys:
            del self._resize_cache[k]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_asset_registry.py -v`
Expected: 11 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/asset_registry.py plugin/tests/test_asset_registry.py
git commit -m "Add AssetRegistry with static loading, uploads, and resize cache"
```

---

## Task 4: Device base class and mock

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/device.py`
- Test: `plugin/tests/test_device_mock.py`

Defines the `Device` abstract interface, `DeviceModel` enum, `ImageFormat` enum, and a `MockDevice` (used for all tests of components above the Device layer).

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_device_mock.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_device_mock.py -v`
Expected: 5 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement Device + MockDevice**

Create `plugin/daemon/claude_streamdeck/core/device.py`:

```python
"""Abstract Device interface and MockDevice for tests."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional

from PIL import Image


class DeviceModel(str, Enum):
    XL = "xl"
    MK2 = "mk2"
    MINI = "mini"
    PLUS = "plus"
    NEO = "neo"
    PEDAL = "pedal"
    ORIGINAL = "original"


class ImageFormat(str, Enum):
    JPEG = "jpeg"
    BMP = "bmp"


KeyCallback = Callable[[int, bool], None]


class Device(ABC):
    """Abstract Stream Deck device. Subclassed by concrete model implementations."""

    id: str
    model: DeviceModel
    key_count: int
    image_size: tuple[int, int]
    image_format: ImageFormat
    has_screen: bool
    has_dial: bool

    @abstractmethod
    def set_key_image(self, button: int, image: Image.Image) -> None: ...

    @abstractmethod
    def clear_key(self, button: int) -> None: ...

    @abstractmethod
    def set_brightness(self, value: int) -> None: ...

    @abstractmethod
    def set_key_callback(self, callback: KeyCallback) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


class MockDevice(Device):
    """In-memory Device for tests. Records all calls; can simulate presses."""

    def __init__(
        self,
        id: str,
        model: DeviceModel,
        key_count: int,
        image_size: tuple[int, int],
        image_format: ImageFormat = ImageFormat.JPEG,
        has_screen: bool = False,
        has_dial: bool = False,
    ) -> None:
        self.id = id
        self.model = model
        self.key_count = key_count
        self.image_size = image_size
        self.image_format = image_format
        self.has_screen = has_screen
        self.has_dial = has_dial

        self.set_key_calls: list[tuple[int, Image.Image]] = []
        self.cleared_keys: list[int] = []
        self.brightness: Optional[int] = None
        self._callback: Optional[KeyCallback] = None
        self.closed = False

    def set_key_image(self, button: int, image: Image.Image) -> None:
        self.set_key_calls.append((button, image))

    def last_image_for(self, button: int) -> Optional[Image.Image]:
        for k, img in reversed(self.set_key_calls):
            if k == button:
                return img
        return None

    def clear_key(self, button: int) -> None:
        self.cleared_keys.append(button)

    def set_brightness(self, value: int) -> None:
        self.brightness = value

    def set_key_callback(self, callback: KeyCallback) -> None:
        self._callback = callback

    def simulate_press(self, button: int, pressed: bool) -> None:
        if self._callback:
            self._callback(button, pressed)

    def close(self) -> None:
        self.closed = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_device_mock.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/device.py plugin/tests/test_device_mock.py
git commit -m "Add Device interface, model enums, and MockDevice for tests"
```

---

## Task 5: InputDispatcher

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/input_dispatcher.py`
- Test: `plugin/tests/test_input_dispatcher.py`

Tracks per-button active state. Bridges HID callbacks (sync, possibly off-loop) to async events on the EventBus. Inactive buttons are silently dropped.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_input_dispatcher.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_input_dispatcher.py -v`
Expected: 5 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement InputDispatcher**

Create `plugin/daemon/claude_streamdeck/core/input_dispatcher.py`:

```python
"""Routes HID button events to the EventBus, gated by per-button active state."""

import logging

from .device import Device
from .event_bus import EventBus

logger = logging.getLogger(__name__)


class InputDispatcher:
    """Per-device button state and HID-to-bus bridge."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._active: dict[str, set[int]] = {}  # device_id -> set of active buttons
        self._devices: dict[str, Device] = {}

    def attach(self, device: Device) -> None:
        self._devices[device.id] = device
        self._active.setdefault(device.id, set())
        device.set_key_callback(self._make_callback(device.id))

    def detach(self, device_id: str) -> None:
        self._devices.pop(device_id, None)
        self._active.pop(device_id, None)

    def set_active(self, device_id: str, button: int, active: bool) -> None:
        s = self._active.setdefault(device_id, set())
        if active:
            s.add(button)
        else:
            s.discard(button)

    def _make_callback(self, device_id: str):
        def cb(button: int, pressed: bool) -> None:
            if button not in self._active.get(device_id, set()):
                return
            topic = "button.pressed" if pressed else "button.released"
            self._bus.publish_threadsafe(
                topic, {"device_id": device_id, "button": button}
            )
        return cb
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_input_dispatcher.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/input_dispatcher.py plugin/tests/test_input_dispatcher.py
git commit -m "Add InputDispatcher with per-button active gating"
```

---

## Task 6: DisplayEngine

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/display_engine.py`
- Test: `plugin/tests/test_display_engine.py`

Drives images and animations onto a `Device`, using the `AssetRegistry` for resized frames. One asyncio task per animated button. Switching from animated → static cancels the task.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_display_engine.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_display_engine.py -v`
Expected: 9 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement DisplayEngine**

Create `plugin/daemon/claude_streamdeck/core/display_engine.py`:

```python
"""Drives static images and animations onto Devices via the AssetRegistry."""

import asyncio
import logging
from typing import Literal, Optional

from PIL import Image

from .asset_registry import AssetRegistry
from .device import Device

logger = logging.getLogger(__name__)


class ButtonOutOfRangeError(Exception):
    pass


class DeviceNotFoundError(Exception):
    pass


class DisplayEngine:
    """Per-(device, button) display state with cooperative animation tasks."""

    def __init__(self, assets: AssetRegistry) -> None:
        self._assets = assets
        self._devices: dict[str, Device] = {}
        # (device_id, button) -> asyncio.Task running an animation loop
        self._animations: dict[tuple[str, int], asyncio.Task] = {}

    def register_device(self, device: Device) -> None:
        self._devices[device.id] = device

    def unregister_device(self, device_id: str) -> None:
        self._devices.pop(device_id, None)

    def _device(self, device_id: str) -> Device:
        d = self._devices.get(device_id)
        if d is None:
            raise DeviceNotFoundError(device_id)
        return d

    def _check_button(self, device: Device, button: int) -> None:
        if button < 0 or button >= device.key_count:
            raise ButtonOutOfRangeError(f"{button} not in [0,{device.key_count})")

    async def set_image(self, device_id: str, button: int, asset_name: str) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)
        img = self._assets.get_resized(asset_name, d.image_size)
        d.set_key_image(button, img)

    async def clear(self, device_id: str, button: int) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)
        d.clear_key(button)

    async def animate(
        self,
        device_id: str,
        button: int,
        asset: Optional[str] = None,
        frames: Optional[list[dict]] = None,
        loop: bool = True,
    ) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)

        # Build (image, duration_ms) sequence
        sequence: list[tuple[Image.Image, int]] = []
        if asset is not None:
            a = self._assets.get(asset)
            imgs = self._assets.get_resized_frames(asset, d.image_size)
            for img, dur in zip(imgs, a.frame_durations_ms):
                sequence.append((img, dur))
        elif frames is not None:
            for f in frames:
                img = self._assets.get_resized(f["asset"], d.image_size)
                sequence.append((img, int(f.get("duration_ms", 100))))
        else:
            raise ValueError("animate requires `asset` or `frames`")

        if not sequence:
            return

        task = asyncio.create_task(
            self._animation_loop(d, button, sequence, loop)
        )
        self._animations[(device_id, button)] = task

    async def _animation_loop(
        self,
        device: Device,
        button: int,
        sequence: list[tuple[Image.Image, int]],
        loop: bool,
    ) -> None:
        try:
            while True:
                for img, dur in sequence:
                    device.set_key_image(button, img)
                    await asyncio.sleep(dur / 1000.0)
                if not loop:
                    return
        except asyncio.CancelledError:
            pass

    async def stop_animation(
        self, device_id: str, button: int, mode: Literal["freeze", "clear"]
    ) -> None:
        d = self._device(device_id)
        self._check_button(d, button)
        await self._cancel_animation(device_id, button)
        if mode == "clear":
            d.clear_key(button)

    async def _cancel_animation(self, device_id: str, button: int) -> None:
        task = self._animations.pop((device_id, button), None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("animation task crashed during cancel")

    async def set_brightness(self, device_id: str, value: int) -> None:
        d = self._device(device_id)
        d.set_brightness(value)

    async def purge_device(self, device_id: str) -> None:
        keys = [k for k in self._animations if k[0] == device_id]
        for k in keys:
            await self._cancel_animation(*k)
        self.unregister_device(device_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_display_engine.py -v`
Expected: 9 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/display_engine.py plugin/tests/test_display_engine.py
git commit -m "Add DisplayEngine with per-button animations and cancellation"
```

---

## Task 7: DeviceManager + XL Device implementation

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/device_xl.py`
- Create: `plugin/daemon/claude_streamdeck/core/device_manager.py`
- Test: `plugin/tests/test_device_manager.py`

`device_xl.py` adapts the `streamdeck` lib's XL device to our `Device` interface. `device_manager.py` enumerates connected hardware, builds Devices, and exposes them by id. Tested with the `streamdeck` lib's enumeration mocked — no real HID required.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_device_manager.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_device_manager.py -v`
Expected: 5 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement XLDevice**

Create `plugin/daemon/claude_streamdeck/core/device_xl.py`:

```python
"""Concrete Device implementation for the Stream Deck XL."""

import logging
from typing import Optional

from PIL import Image
from StreamDeck.ImageHelpers import PILHelper

from .device import Device, DeviceModel, ImageFormat, KeyCallback

logger = logging.getLogger(__name__)


class XLDevice(Device):
    """Stream Deck XL adapter over the `streamdeck` library."""

    model = DeviceModel.XL
    has_screen = False
    has_dial = False

    def __init__(self, hid_device, id: str) -> None:
        self.id = id
        self._dev = hid_device
        self.key_count = hid_device.key_count()
        fmt = hid_device.key_image_format()
        self.image_size = fmt["size"]
        self.image_format = ImageFormat(str(fmt["format"]).lower())
        self._callback: Optional[KeyCallback] = None
        self._open()

    def _open(self) -> None:
        self._dev.open()
        self._dev.reset()
        self._dev.set_brightness(80)
        self._dev.set_key_callback(self._on_key_change)

    def _on_key_change(self, deck, key: int, pressed: bool) -> None:
        if self._callback:
            try:
                self._callback(key, pressed)
            except Exception:
                logger.exception("XL key callback failed")

    def set_key_image(self, button: int, image: Image.Image) -> None:
        native = PILHelper.to_native_format(self._dev, image)
        self._dev.set_key_image(button, native)

    def clear_key(self, button: int) -> None:
        black = Image.new("RGB", self.image_size, (0, 0, 0))
        self.set_key_image(button, black)

    def set_brightness(self, value: int) -> None:
        self._dev.set_brightness(max(0, min(100, value)))

    def set_key_callback(self, callback: KeyCallback) -> None:
        self._callback = callback

    def close(self) -> None:
        try:
            for k in range(self.key_count):
                self.clear_key(k)
            self._dev.reset()
        finally:
            try:
                self._dev.close()
            except Exception:
                logger.exception("XL close failed")
```

- [ ] **Step 4: Implement DeviceManager**

Create `plugin/daemon/claude_streamdeck/core/device_manager.py`:

```python
"""Enumerates connected Stream Decks and yields concrete Devices."""

import logging
from typing import Optional

from StreamDeck.DeviceManager import DeviceManager as DeviceManagerHID

from .device import Device, DeviceModel
from .device_xl import XLDevice

logger = logging.getLogger(__name__)


_MODEL_BY_DECK_TYPE = {
    "Stream Deck XL": DeviceModel.XL,
}


class DeviceManager:
    """Enumerates HID Stream Decks and wraps them as Device instances."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}

    def enumerate(self) -> list[Device]:
        out: list[Device] = []
        try:
            raw = DeviceManagerHID().enumerate()
        except Exception:
            logger.exception("HID enumerate failed")
            return out
        for hid in raw:
            try:
                deck_type = hid.deck_type()
                model = _MODEL_BY_DECK_TYPE.get(deck_type)
                if model is None:
                    logger.info("Skipping unsupported model: %s", deck_type)
                    continue
                serial = hid.get_serial_number().strip().strip("\x00")
                dev_id = f"{model.value}-{serial}"
                device: Device
                if model == DeviceModel.XL:
                    device = XLDevice(hid, id=dev_id)
                else:
                    continue  # other models not implemented yet
                self._devices[dev_id] = device
                out.append(device)
            except Exception:
                logger.exception("Failed to wrap HID device")
        return out

    def get(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)

    def first(self) -> Optional[Device]:
        for d in self._devices.values():
            return d
        return None

    def all(self) -> list[Device]:
        return list(self._devices.values())

    def remove(self, device_id: str) -> None:
        d = self._devices.pop(device_id, None)
        if d is not None:
            try:
                d.close()
            except Exception:
                logger.exception("Failed to close device %s", device_id)
```

- [ ] **Step 5: Adjust the test for XLDevice instantiation**

`XLDevice.__init__` calls `_open()` which calls `open()`/`reset()` on the HID handle. The fake in the test must support these. Update `_fake_xl` in the test to wire those:

In `plugin/tests/test_device_manager.py`, replace `_fake_xl` with:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_device_manager.py -v`
Expected: 5 PASSED.

- [ ] **Step 7: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/device_xl.py \
        plugin/daemon/claude_streamdeck/core/device_manager.py \
        plugin/tests/test_device_manager.py
git commit -m "Add XLDevice and DeviceManager with HID enumeration"
```

---

## Task 8: CoreAPI façade

**Files:**
- Create: `plugin/daemon/claude_streamdeck/core/core_api.py`
- Test: `plugin/tests/test_core_api.py`

A simple frozen dataclass that bundles references to the core components. Extensions receive this. No logic of its own — just plumbing.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_core_api.py`:

```python
"""Tests for the CoreAPI façade."""

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.core_api import CoreAPI
from claude_streamdeck.core.device_manager import DeviceManager
from claude_streamdeck.core.display_engine import DisplayEngine
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher


def test_core_api_holds_components():
    reg = AssetRegistry(static_dir=None)
    bus = EventBus()
    devices = DeviceManager()
    disp = DisplayEngine(reg)
    inp = InputDispatcher(bus)
    cmds = CommandRegistry()
    api = CoreAPI(
        devices=devices, assets=reg, display=disp, input=inp,
        events=bus, commands=cmds, config={"k": "v"},
    )
    assert api.devices is devices
    assert api.assets is reg
    assert api.display is disp
    assert api.input is inp
    assert api.events is bus
    assert api.commands is cmds
    assert api.config == {"k": "v"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest plugin/tests/test_core_api.py -v`
Expected: 1 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement CoreAPI**

Create `plugin/daemon/claude_streamdeck/core/core_api.py`:

```python
"""Façade injected into extensions: bundles handles to core components."""

from dataclasses import dataclass, field
from typing import Any

from .asset_registry import AssetRegistry
from .command_registry import CommandRegistry
from .device_manager import DeviceManager
from .display_engine import DisplayEngine
from .event_bus import EventBus
from .input_dispatcher import InputDispatcher


@dataclass
class CoreAPI:
    devices: DeviceManager
    assets: AssetRegistry
    display: DisplayEngine
    input: InputDispatcher
    events: EventBus
    commands: CommandRegistry
    config: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest plugin/tests/test_core_api.py -v`
Expected: 1 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/core/core_api.py plugin/tests/test_core_api.py
git commit -m "Add CoreAPI façade for extension injection"
```

---

## Task 9: Connection (one client over the socket)

**Files:**
- Create: `plugin/daemon/claude_streamdeck/transport/connection.py`
- Test: `plugin/tests/test_connection.py`

A `Connection` wraps an `(asyncio.StreamReader, asyncio.StreamWriter)` pair and provides:
- async iteration over JSONL messages
- `send_response(request_id, ok, ...)` and `send_event(name, payload)`
- subscription set (string flags like `"input"`)

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_connection.py`:

```python
"""Tests for the per-client Connection wrapper."""

import asyncio
import json

import pytest

from claude_streamdeck.transport.connection import Connection


async def _pipe():
    # Build a connected pair using asyncio sockets via a memory pipe.
    reader_a = asyncio.StreamReader()
    writer_a_buf = bytearray()

    class _W:
        def __init__(self): self._buf = writer_a_buf
        def write(self, data): self._buf.extend(data)
        async def drain(self): pass
        def close(self): pass
        async def wait_closed(self): pass
        def is_closing(self): return False

    writer = _W()
    return reader_a, writer, writer_a_buf


async def test_send_response_serializes_one_line():
    r, w, buf = await _pipe()
    c = Connection(r, w)
    await c.send_response(request_id="abc", ok=True, result={"x": 1})
    text = bytes(buf).decode()
    assert text.endswith("\n")
    obj = json.loads(text.strip())
    assert obj == {"ok": True, "request_id": "abc", "result": {"x": 1}}


async def test_send_response_error():
    r, w, buf = await _pipe()
    c = Connection(r, w)
    await c.send_response(request_id="x", ok=False, error="bad", message="nope")
    obj = json.loads(bytes(buf).decode().strip())
    assert obj == {"ok": False, "request_id": "x", "error": "bad", "message": "nope"}


async def test_send_event_includes_ts():
    r, w, buf = await _pipe()
    c = Connection(r, w)
    await c.send_event("button.pressed", {"device_id": "x", "button": 1})
    obj = json.loads(bytes(buf).decode().strip())
    assert obj["event"] == "button.pressed"
    assert obj["device_id"] == "x"
    assert obj["button"] == 1
    assert "ts" in obj
    assert isinstance(obj["ts"], int)


async def test_iter_messages_parses_jsonl():
    r, _, _ = await _pipe()
    r.feed_data(b'{"cmd":"a"}\n{"cmd":"b"}\n')
    r.feed_eof()

    class _W2:
        def write(self, d): pass
        async def drain(self): pass
        def close(self): pass
        async def wait_closed(self): pass
        def is_closing(self): return False

    c = Connection(r, _W2())
    msgs = []
    async for m in c.iter_messages():
        msgs.append(m)
    assert msgs == [{"cmd": "a"}, {"cmd": "b"}]


async def test_iter_messages_invalid_json_yields_sentinel():
    r, _, _ = await _pipe()
    r.feed_data(b'not-json\n{"cmd":"ok"}\n')
    r.feed_eof()

    class _W2:
        def write(self, d): pass
        async def drain(self): pass
        def close(self): pass
        async def wait_closed(self): pass
        def is_closing(self): return False

    c = Connection(r, _W2())
    msgs = []
    async for m in c.iter_messages():
        msgs.append(m)
    # The first line is delivered as InvalidJSONLine, the second parses OK.
    from claude_streamdeck.transport.connection import InvalidJSONLine
    assert isinstance(msgs[0], InvalidJSONLine)
    assert msgs[1] == {"cmd": "ok"}


def test_subscription_set_default_empty():
    class _R:
        async def readline(self): return b""
    class _W2:
        def write(self, d): pass
        async def drain(self): pass
        def close(self): pass
        async def wait_closed(self): pass
        def is_closing(self): return False
    c = Connection(_R(), _W2())
    assert "input" not in c.subscriptions
    c.subscriptions.add("input")
    assert "input" in c.subscriptions
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_connection.py -v`
Expected: 6 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement Connection**

Create `plugin/daemon/claude_streamdeck/transport/connection.py`:

```python
"""Per-client connection: JSONL framing, response/event helpers, subscriptions."""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional


@dataclass
class InvalidJSONLine:
    """Sentinel yielded when a received line isn't valid JSON."""
    line: bytes


class Connection:
    """Wraps a StreamReader/StreamWriter pair with JSONL framing helpers."""

    def __init__(self, reader, writer) -> None:
        self._reader = reader
        self._writer = writer
        self.subscriptions: set[str] = set()
        self._send_lock = asyncio.Lock()

    async def iter_messages(self) -> AsyncIterator[Any]:
        while True:
            line = await self._reader.readline()
            if not line:
                return
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError:
                yield InvalidJSONLine(line=line)

    async def send_response(
        self,
        request_id: Optional[str],
        ok: bool,
        result: Any = None,
        error: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        obj: dict[str, Any] = {"ok": ok}
        if request_id is not None:
            obj["request_id"] = request_id
        if ok:
            if result is not None:
                obj["result"] = result
        else:
            if error is not None:
                obj["error"] = error
            if message is not None:
                obj["message"] = message
        await self._write_json(obj)

    async def send_event(self, name: str, payload: dict[str, Any]) -> None:
        obj: dict[str, Any] = {"event": name, "ts": int(time.time() * 1000)}
        obj.update(payload)
        await self._write_json(obj)

    async def _write_json(self, obj: dict[str, Any]) -> None:
        line = (json.dumps(obj) + "\n").encode("utf-8")
        async with self._send_lock:
            self._writer.write(line)
            await self._writer.drain()

    async def close(self) -> None:
        if not self._writer.is_closing():
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_connection.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/transport/connection.py plugin/tests/test_connection.py
git commit -m "Add Connection wrapper with JSONL framing and helpers"
```

---

## Task 10: SocketServer (multi-client, JSONL persistent)

**Files:**
- Create: `plugin/daemon/claude_streamdeck/transport/socket_server.py`
- Test: `plugin/tests/test_socket_server.py`

Listens on a Unix socket. For each connection, spawns a task that reads JSONL messages, dispatches via `CommandRegistry`, and sends responses. Subscribes connections to the EventBus for `button.*` and `device.*` events.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_socket_server.py`:

```python
"""Tests for SocketServer (JSONL persistent, multi-client)."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.transport.socket_server import SocketServer


async def _start_server(reg, bus):
    sock_path = Path(tempfile.mkdtemp()) / "test.sock"
    server = SocketServer(socket_path=sock_path, commands=reg, events=bus)
    await server.start()
    return server, sock_path


async def _client(sock_path: Path):
    return await asyncio.open_unix_connection(str(sock_path))


async def _send(writer, obj):
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


async def _recv(reader):
    line = await reader.readline()
    return json.loads(line.decode().strip())


async def test_dispatch_command_returns_result():
    reg = CommandRegistry()
    async def ping(p): return {"pong": True}
    reg.register("system.ping", ping)

    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        r, w = await _client(sock)
        await _send(w, {"cmd": "system.ping", "request_id": "1"})
        resp = await _recv(r)
        assert resp == {"ok": True, "request_id": "1", "result": {"pong": True}}
        w.close()
        await w.wait_closed()
    finally:
        await server.stop()


async def test_unknown_command_returns_error():
    reg = CommandRegistry()
    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        r, w = await _client(sock)
        await _send(w, {"cmd": "nope", "request_id": "x"})
        resp = await _recv(r)
        assert resp["ok"] is False
        assert resp["error"] == "unknown_command"
        assert resp["request_id"] == "x"
        w.close(); await w.wait_closed()
    finally:
        await server.stop()


async def test_invalid_json_returns_error_keeps_connection():
    reg = CommandRegistry()
    async def ping(p): return {}
    reg.register("system.ping", ping)
    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        r, w = await _client(sock)
        # First line bad JSON
        w.write(b"not-json\n")
        await w.drain()
        resp1 = await _recv(r)
        assert resp1["ok"] is False
        assert resp1["error"] == "invalid_json"
        # Then a valid command on same connection
        await _send(w, {"cmd": "system.ping"})
        resp2 = await _recv(r)
        assert resp2["ok"] is True
        w.close(); await w.wait_closed()
    finally:
        await server.stop()


async def test_event_broadcast_to_subscribed_only():
    reg = CommandRegistry()
    # Provide subscribe/unsubscribe handlers via the server's "input.subscribe"
    bus = EventBus()
    server, sock = await _start_server(reg, bus)
    try:
        bus.bind_loop(asyncio.get_running_loop())
        # Two clients
        r1, w1 = await _client(sock)
        r2, w2 = await _client(sock)
        await asyncio.sleep(0.05)
        await _send(w1, {"cmd": "input.subscribe", "request_id": "s1"})
        resp = await _recv(r1)
        assert resp["ok"] is True
        # Publish a button event
        await bus.publish("button.pressed", {"device_id": "x", "button": 5})
        # Client 1 should receive
        line = await asyncio.wait_for(r1.readline(), timeout=1.0)
        ev = json.loads(line.decode().strip())
        assert ev["event"] == "button.pressed"
        assert ev["device_id"] == "x"
        assert ev["button"] == 5
        # Client 2 should NOT receive (verify by short timeout)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(r2.readline(), timeout=0.2)
        for w in (w1, w2):
            w.close(); await w.wait_closed()
    finally:
        await server.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_socket_server.py -v`
Expected: 4 FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement SocketServer**

Create `plugin/daemon/claude_streamdeck/transport/socket_server.py`:

```python
"""Async Unix socket server: JSONL persistent connections, multi-client."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from ..core.command_registry import (
    CommandRegistry,
    UnknownCommandError,
)
from ..core.event_bus import EventBus
from .connection import Connection, InvalidJSONLine

logger = logging.getLogger(__name__)


class SocketServer:
    """Listens on a Unix socket and dispatches JSONL commands to a CommandRegistry."""

    def __init__(
        self,
        socket_path: Path,
        commands: CommandRegistry,
        events: EventBus,
    ) -> None:
        self.socket_path = socket_path
        self._commands = commands
        self._events = events
        self._server: Optional[asyncio.AbstractServer] = None
        self._connections: set[Connection] = set()
        # Built-in handlers for input.subscribe / input.unsubscribe live here
        # because they need access to the per-connection state.
        self._register_subscription_handlers()
        self._wire_event_broadcast()

    def _register_subscription_handlers(self) -> None:
        # We don't register on the global CommandRegistry because these handlers
        # need the current connection context. They are dispatched specially in
        # `_handle_connection`.
        pass

    def _wire_event_broadcast(self) -> None:
        async def _on_button(payload):
            await self._broadcast("button.pressed", payload, gate="input")

        async def _on_release(payload):
            await self._broadcast("button.released", payload, gate="input")

        async def _on_dev_conn(payload):
            await self._broadcast("device.connected", payload, gate=None)

        async def _on_dev_disc(payload):
            await self._broadcast("device.disconnected", payload, gate=None)

        self._events.subscribe("button.pressed", _on_button)
        self._events.subscribe("button.released", _on_release)
        self._events.subscribe("device.connected", _on_dev_conn)
        self._events.subscribe("device.disconnected", _on_dev_disc)

    async def _broadcast(self, name: str, payload: dict, gate: Optional[str]) -> None:
        for conn in list(self._connections):
            if gate is not None and gate not in conn.subscriptions:
                continue
            try:
                await conn.send_event(name, payload)
            except Exception:
                logger.exception("send_event failed on connection")

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=str(self.socket_path)
        )
        os.chmod(self.socket_path, 0o600)
        logger.info("Socket server listening on %s", self.socket_path)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for conn in list(self._connections):
            await conn.close()
        self._connections.clear()
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

    async def _handle_connection(self, reader, writer) -> None:
        conn = Connection(reader, writer)
        self._connections.add(conn)
        try:
            async for msg in conn.iter_messages():
                if isinstance(msg, InvalidJSONLine):
                    await conn.send_response(
                        request_id=None, ok=False,
                        error="invalid_json", message="malformed JSON line",
                    )
                    continue
                await self._dispatch(conn, msg)
        except Exception:
            logger.exception("connection crashed")
        finally:
            self._connections.discard(conn)
            await conn.close()

    async def _dispatch(self, conn: Connection, msg: dict) -> None:
        cmd = msg.get("cmd")
        request_id = msg.get("request_id")
        if not isinstance(cmd, str):
            await conn.send_response(
                request_id, ok=False, error="invalid_params",
                message="missing or non-string `cmd`",
            )
            return

        # Built-in subscription handlers (need conn context).
        if cmd == "input.subscribe":
            conn.subscriptions.add("input")
            await conn.send_response(request_id, ok=True, result={})
            return
        if cmd == "input.unsubscribe":
            conn.subscriptions.discard("input")
            await conn.send_response(request_id, ok=True, result={})
            return

        params = {k: v for k, v in msg.items() if k not in ("cmd", "request_id")}
        try:
            result = await self._commands.dispatch(cmd, params)
            await conn.send_response(request_id, ok=True, result=result)
        except UnknownCommandError:
            await conn.send_response(
                request_id, ok=False, error="unknown_command",
                message=f"no such command: {cmd}",
            )
        except Exception as e:
            logger.exception("handler failed: %s", cmd)
            await conn.send_response(
                request_id, ok=False, error="extension_error", message=str(e),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_socket_server.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/transport/socket_server.py plugin/tests/test_socket_server.py
git commit -m "Add SocketServer with JSONL persistent connections and event broadcast"
```

---

## Task 11: Core handlers

**Files:**
- Create: `plugin/daemon/claude_streamdeck/handlers/system_handlers.py`
- Create: `plugin/daemon/claude_streamdeck/handlers/device_handlers.py`
- Create: `plugin/daemon/claude_streamdeck/handlers/asset_handlers.py`
- Create: `plugin/daemon/claude_streamdeck/handlers/display_handlers.py`
- Create: `plugin/daemon/claude_streamdeck/handlers/input_handlers.py`
- Create: `plugin/daemon/claude_streamdeck/handlers/__init__.py` (already exists; will be modified)
- Test: `plugin/tests/test_handlers.py`

Each handler module exposes a single `register(api: CoreAPI)` function. The `__init__.py` exposes a master `register_core_handlers(api)`.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_handlers.py`:

```python
"""Tests for the core handlers (system / device / asset / display / input)."""

import asyncio
import base64
import io

import pytest
from PIL import Image

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.core_api import CoreAPI
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.core.device_manager import DeviceManager
from claude_streamdeck.core.display_engine import DisplayEngine
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher
from claude_streamdeck.handlers import register_core_handlers


def _png() -> str:
    img = Image.new("RGB", (50, 50), (1, 2, 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _api_with_mock_device():
    bus = EventBus()
    bus.bind_loop(asyncio.get_event_loop())
    reg = AssetRegistry(static_dir=None)
    devices = DeviceManager()
    dev = MockDevice(id="xl-x", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    devices._devices[dev.id] = dev  # inject for tests
    disp = DisplayEngine(reg)
    disp.register_device(dev)
    inp = InputDispatcher(bus)
    inp.attach(dev)
    cmds = CommandRegistry()
    api = CoreAPI(devices=devices, assets=reg, display=disp, input=inp,
                  events=bus, commands=cmds)
    register_core_handlers(api)
    return api, dev


async def test_system_ping():
    api, _ = _api_with_mock_device()
    out = await api.commands.dispatch("system.ping", {})
    assert out == {"pong": True}


async def test_system_version():
    api, _ = _api_with_mock_device()
    out = await api.commands.dispatch("system.version", {})
    assert "version" in out
    assert "extensions" in out


async def test_device_list():
    api, dev = _api_with_mock_device()
    out = await api.commands.dispatch("device.list", {})
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["id"] == dev.id
    assert out[0]["model"] == "xl"
    assert out[0]["key_count"] == 32


async def test_device_capabilities_default_first():
    api, dev = _api_with_mock_device()
    out = await api.commands.dispatch("device.capabilities", {})
    assert out["id"] == dev.id


async def test_asset_upload_remove_list():
    api, _ = _api_with_mock_device()
    up = await api.commands.dispatch("asset.upload", {"name": "a", "data": _png()})
    assert up["name"] == "a"
    assert up["animated"] is False
    listed = await api.commands.dispatch("asset.list", {})
    assert any(item["name"] == "a" for item in listed)
    rm = await api.commands.dispatch("asset.remove", {"name": "a"})
    assert rm == {}


async def test_display_set_clear():
    api, dev = _api_with_mock_device()
    await api.commands.dispatch("asset.upload", {"name": "a", "data": _png()})
    await api.commands.dispatch("display.set", {"button": 5, "asset": "a"})
    assert dev.last_image_for(5) is not None
    await api.commands.dispatch("display.clear", {"button": 5})
    assert 5 in dev.cleared_keys


async def test_display_brightness():
    api, dev = _api_with_mock_device()
    await api.commands.dispatch("display.brightness", {"value": 42})
    assert dev.brightness == 42


async def test_input_set_active_then_press_emits():
    api, dev = _api_with_mock_device()
    received = []

    async def h(p): received.append(p)
    api.events.subscribe("button.pressed", h)
    await api.commands.dispatch("input.set_active", {"button": 7, "active": True})
    dev.simulate_press(7, True)
    await asyncio.sleep(0.05)
    assert received == [{"device_id": dev.id, "button": 7}]


async def test_invalid_params_missing_button():
    api, _ = _api_with_mock_device()
    with pytest.raises(Exception):
        await api.commands.dispatch("display.set", {"asset": "a"})


async def test_unknown_asset_in_display_set():
    api, _ = _api_with_mock_device()
    from claude_streamdeck.core.asset_registry import AssetNotFoundError
    with pytest.raises(AssetNotFoundError):
        await api.commands.dispatch("display.set", {"button": 0, "asset": "ghost"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_handlers.py -v`
Expected: 10 FAIL with `ImportError`.

- [ ] **Step 3: Implement system handlers**

Create `plugin/daemon/claude_streamdeck/handlers/system_handlers.py`:

```python
"""system.* handlers: ping, version."""

from .. import __version__
from ..core.core_api import CoreAPI


def register(api: CoreAPI) -> None:
    async def ping(_params): return {"pong": True}

    async def version(_params):
        return {
            "version": __version__,
            "extensions": list(api.config.get("loaded_extensions", [])),
        }

    api.commands.register("system.ping", ping)
    api.commands.register("system.version", version)
```

- [ ] **Step 4: Implement device handlers**

Create `plugin/daemon/claude_streamdeck/handlers/device_handlers.py`:

```python
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
```

- [ ] **Step 5: Implement asset handlers**

Create `plugin/daemon/claude_streamdeck/handlers/asset_handlers.py`:

```python
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
```

- [ ] **Step 6: Implement display handlers**

Create `plugin/daemon/claude_streamdeck/handlers/display_handlers.py`:

```python
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
```

- [ ] **Step 7: Implement input handlers**

Create `plugin/daemon/claude_streamdeck/handlers/input_handlers.py`:

```python
"""input.* handlers: set_active. (subscribe/unsubscribe live in SocketServer.)"""

from ..core.core_api import CoreAPI
from .device_handlers import _resolve_device


def register(api: CoreAPI) -> None:
    async def set_active(params):
        d = _resolve_device(api, params)
        api.input.set_active(d.id, int(params["button"]), bool(params["active"]))
        return {}

    api.commands.register("input.set_active", set_active)
```

- [ ] **Step 8: Wire up `handlers/__init__.py`**

Replace contents of `plugin/daemon/claude_streamdeck/handlers/__init__.py`:

```python
"""Aggregated registration of core handlers."""

from ..core.core_api import CoreAPI
from . import (
    asset_handlers,
    device_handlers,
    display_handlers,
    input_handlers,
    system_handlers,
)


def register_core_handlers(api: CoreAPI) -> None:
    system_handlers.register(api)
    device_handlers.register(api)
    asset_handlers.register(api)
    display_handlers.register(api)
    input_handlers.register(api)
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_handlers.py -v`
Expected: 10 PASSED.

- [ ] **Step 10: Commit**

```bash
git add plugin/daemon/claude_streamdeck/handlers/ plugin/tests/test_handlers.py
git commit -m "Add core JSON handlers (system, device, asset, display, input)"
```

---

## Task 12: Extension loader and `echo` extension

**Files:**
- Create: `plugin/daemon/claude_streamdeck/extensions/__init__.py` (modify existing empty file)
- Create: `plugin/daemon/claude_streamdeck/extensions/echo/__init__.py` (modify existing empty file)
- Test: `plugin/tests/test_extension_loading.py`

Loader imports modules by name from config and instantiates an `Extension` exported by each module.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_extension_loading.py`:

```python
"""Tests for extension loading."""

import asyncio

import pytest

from claude_streamdeck.core.asset_registry import AssetRegistry
from claude_streamdeck.core.command_registry import CommandRegistry
from claude_streamdeck.core.core_api import CoreAPI
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.core.device_manager import DeviceManager
from claude_streamdeck.core.display_engine import DisplayEngine
from claude_streamdeck.core.event_bus import EventBus
from claude_streamdeck.core.input_dispatcher import InputDispatcher
from claude_streamdeck.extensions import load_extensions


def _api():
    bus = EventBus()
    reg = AssetRegistry(static_dir=None)
    devices = DeviceManager()
    disp = DisplayEngine(reg)
    inp = InputDispatcher(bus)
    cmds = CommandRegistry()
    return CoreAPI(devices=devices, assets=reg, display=disp, input=inp,
                   events=bus, commands=cmds)


async def test_load_echo_extension_registers_handlers():
    api = _api()
    api.events.bind_loop(asyncio.get_event_loop())
    loaded = load_extensions(
        api, [{"module": "claude_streamdeck.extensions.echo", "config": {}}]
    )
    assert "claude_streamdeck.extensions.echo" in loaded


async def test_failing_extension_is_skipped(monkeypatch):
    api = _api()
    api.events.bind_loop(asyncio.get_event_loop())
    # Build a fake module with a broken init.
    import sys
    import types
    mod = types.ModuleType("fake_broken_ext")
    class Ext:
        def init(self, api): raise RuntimeError("boom")
        def shutdown(self): pass
    mod.Extension = Ext
    sys.modules["fake_broken_ext"] = mod

    loaded = load_extensions(api, [{"module": "fake_broken_ext", "config": {}}])
    assert loaded == []  # broken extension is skipped, daemon continues


async def test_echo_marks_buttons_active_when_device_attached():
    api = _api()
    api.events.bind_loop(asyncio.get_event_loop())
    dev = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    api.devices._devices[dev.id] = dev
    api.input.attach(dev)

    load_extensions(
        api, [{"module": "claude_streamdeck.extensions.echo", "config": {}}]
    )
    # The echo extension activates all buttons of all currently-known devices.
    received = []
    async def h(p): received.append(p)
    api.events.subscribe("button.pressed", h)
    dev.simulate_press(0, True)
    await asyncio.sleep(0.05)
    assert received == [{"device_id": "m", "button": 0}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_extension_loading.py -v`
Expected: 3 FAIL with `ImportError`.

- [ ] **Step 3: Implement the extension loader**

Replace contents of `plugin/daemon/claude_streamdeck/extensions/__init__.py`:

```python
"""Extension loader: imports modules by name and initializes them."""

import importlib
import logging
from typing import Any, Protocol

from ..core.core_api import CoreAPI

logger = logging.getLogger(__name__)


class Extension(Protocol):
    def init(self, api: CoreAPI) -> None: ...
    def shutdown(self) -> None: ...


# Track loaded extensions for shutdown.
_loaded: list[tuple[str, Any]] = []


def load_extensions(api: CoreAPI, specs: list[dict]) -> list[str]:
    """Load each extension by module name. Returns the names that loaded successfully."""
    loaded: list[str] = []
    for spec in specs:
        module_name = spec["module"]
        cfg = spec.get("config", {})
        try:
            mod = importlib.import_module(module_name)
            ext_cls = getattr(mod, "Extension")
            ext = ext_cls()
            # Provide the per-extension config slice without polluting api.config.
            scoped_api = CoreAPI(
                devices=api.devices,
                assets=api.assets,
                display=api.display,
                input=api.input,
                events=api.events,
                commands=api.commands,
                config=cfg,
            )
            ext.init(scoped_api)
            _loaded.append((module_name, ext))
            loaded.append(module_name)
            logger.info("Loaded extension: %s", module_name)
        except Exception:
            logger.exception("Failed to load extension %s", module_name)
    # Make the list of loaded extensions visible to system.version.
    api.config["loaded_extensions"] = loaded
    return loaded


def shutdown_extensions() -> None:
    while _loaded:
        name, ext = _loaded.pop()
        try:
            ext.shutdown()
        except Exception:
            logger.exception("Failed to shutdown extension %s", name)
```

- [ ] **Step 4: Implement the `echo` extension**

Replace contents of `plugin/daemon/claude_streamdeck/extensions/echo/__init__.py`:

```python
"""Echo extension: marks all buttons active and logs presses."""

import logging

from ...core.core_api import CoreAPI

logger = logging.getLogger(__name__)


class Extension:
    def __init__(self) -> None:
        self._api: CoreAPI | None = None

    def init(self, api: CoreAPI) -> None:
        self._api = api
        # Activate all buttons on every currently-attached device.
        for d in api.devices.all():
            for b in range(d.key_count):
                api.input.set_active(d.id, b, True)

        async def on_pressed(payload):
            logger.info("echo: button pressed %s", payload)

        api.events.subscribe("button.pressed", on_pressed)

    def shutdown(self) -> None:
        # Nothing persistent to clean up.
        pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_extension_loading.py -v`
Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add plugin/daemon/claude_streamdeck/extensions/ plugin/tests/test_extension_loading.py
git commit -m "Add extension loader and echo demo extension"
```

---

## Task 13: TOML config loader

**Files:**
- Create: `plugin/daemon/claude_streamdeck/config.py`
- Test: `plugin/tests/test_config.py`

Loads daemon config from TOML. Uses `tomllib` from the standard library (3.11+). Provides defaults when no file is present.

- [ ] **Step 1: Write the failing tests**

Create `plugin/tests/test_config.py`:

```python
"""Tests for the TOML config loader."""

from pathlib import Path

import pytest

from claude_streamdeck.config import DaemonConfig, load_config


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(None)
    assert isinstance(cfg, DaemonConfig)
    assert cfg.socket_path.name == "daemon.sock"
    assert cfg.extensions == []


def test_loads_from_toml(tmp_path: Path):
    f = tmp_path / "cfg.toml"
    f.write_text("""
[daemon]
socket_path = "/tmp/x.sock"
assets_dir = "/tmp/assets"

[[extensions]]
module = "claude_streamdeck.extensions.echo"
config = { log_level = "debug" }
""")
    cfg = load_config(f)
    assert str(cfg.socket_path) == "/tmp/x.sock"
    assert str(cfg.assets_dir) == "/tmp/assets"
    assert cfg.extensions == [
        {"module": "claude_streamdeck.extensions.echo", "config": {"log_level": "debug"}}
    ]


def test_user_path_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    f = tmp_path / "cfg.toml"
    f.write_text("""
[daemon]
socket_path = "~/sock"
""")
    cfg = load_config(f)
    assert str(cfg.socket_path) == str(tmp_path / "sock")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest plugin/tests/test_config.py -v`
Expected: 3 FAIL with `ImportError`.

- [ ] **Step 3: Implement DaemonConfig and load_config**

Create `plugin/daemon/claude_streamdeck/config.py`:

```python
"""TOML config loader for the daemon."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _expand(p: str) -> Path:
    return Path(p).expanduser()


@dataclass
class DaemonConfig:
    socket_path: Path = field(
        default_factory=lambda: _expand("~/.config/claude-streamdeck/daemon.sock")
    )
    assets_dir: Path = field(
        default_factory=lambda: _expand("~/.config/claude-streamdeck/assets")
    )
    max_asset_bytes: int = 5 * 1024 * 1024
    extensions: list[dict[str, Any]] = field(default_factory=list)


def load_config(path: Optional[Path]) -> DaemonConfig:
    if path is None or not path.exists():
        return DaemonConfig()
    with path.open("rb") as f:
        raw = tomllib.load(f)
    daemon = raw.get("daemon", {}) or {}
    cfg = DaemonConfig(
        socket_path=_expand(daemon.get("socket_path",
                                       "~/.config/claude-streamdeck/daemon.sock")),
        assets_dir=_expand(daemon.get("assets_dir",
                                      "~/.config/claude-streamdeck/assets")),
        max_asset_bytes=int(daemon.get("max_asset_bytes", 5 * 1024 * 1024)),
        extensions=list(raw.get("extensions", []) or []),
    )
    return cfg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest plugin/tests/test_config.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/config.py plugin/tests/test_config.py
git commit -m "Add TOML config loader with defaults"
```

---

## Task 14: Daemon orchestrator and CLI

**Files:**
- Create: `plugin/daemon/claude_streamdeck/daemon.py`
- Create: `plugin/daemon/claude_streamdeck/__main__.py`

The orchestrator wires every component, owns the asyncio loop, handles signals, and runs a reconnect loop for the device. The CLI parses args and calls into the orchestrator.

There are no automated tests for `daemon.py` itself (it's pure wiring). The integration test in Task 15 exercises the full stack.

- [ ] **Step 1: Implement the orchestrator**

Create `plugin/daemon/claude_streamdeck/daemon.py`:

```python
"""Daemon orchestrator: wires components, owns the asyncio loop."""

import asyncio
import logging
import signal
from typing import Optional

from .config import DaemonConfig
from .core.asset_registry import AssetRegistry
from .core.command_registry import CommandRegistry
from .core.core_api import CoreAPI
from .core.device import Device
from .core.device_manager import DeviceManager
from .core.display_engine import DisplayEngine
from .core.event_bus import EventBus
from .core.input_dispatcher import InputDispatcher
from .extensions import load_extensions, shutdown_extensions
from .handlers import register_core_handlers
from .transport.socket_server import SocketServer

logger = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: DaemonConfig) -> None:
        self.config = config
        self.bus = EventBus()
        self.assets = AssetRegistry(
            static_dir=config.assets_dir if config.assets_dir.exists() else None,
            max_size_bytes=config.max_asset_bytes,
        )
        self.devices = DeviceManager()
        self.display = DisplayEngine(self.assets)
        self.input = InputDispatcher(self.bus)
        self.commands = CommandRegistry()
        self.api = CoreAPI(
            devices=self.devices, assets=self.assets, display=self.display,
            input=self.input, events=self.bus, commands=self.commands, config={},
        )
        self.server = SocketServer(
            socket_path=config.socket_path,
            commands=self.commands, events=self.bus,
        )
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.bus.bind_loop(loop)
        register_core_handlers(self.api)
        # Devices first, so extensions see them on init.
        await self._connect_devices()
        load_extensions(self.api, self.config.extensions)
        await self.server.start()
        self._running = True
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self) -> None:
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self.server.stop()
        shutdown_extensions()
        for d in self.devices.all():
            try:
                await self.display.purge_device(d.id)
                self.input.detach(d.id)
                d.close()
            except Exception:
                logger.exception("device shutdown failed: %s", d.id)

    async def _connect_devices(self) -> None:
        for d in self.devices.enumerate():
            self._wire_device(d)

    def _wire_device(self, device: Device) -> None:
        self.display.register_device(device)
        self.input.attach(device)
        # Fire connected event (publish via bus on the loop).
        asyncio.create_task(
            self.bus.publish("device.connected",
                             {"device_id": device.id, "model": device.model.value})
        )

    async def _reconnect_loop(self) -> None:
        while self._running:
            await asyncio.sleep(2.0)
            known = {d.id for d in self.devices.all()}
            for d in self.devices.enumerate():
                if d.id not in known:
                    self._wire_device(d)
```

- [ ] **Step 2: Implement the CLI entry**

Create `plugin/daemon/claude_streamdeck/__main__.py`:

```python
"""CLI entry: `python -m claude_streamdeck`."""

import argparse
import asyncio
import logging
import signal
from pathlib import Path

from .config import load_config
from .daemon import Daemon


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("StreamDeck").setLevel(logging.WARNING)


async def _run(config_path: Path | None) -> None:
    cfg = load_config(config_path)
    daemon = Daemon(cfg)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await daemon.start()
    try:
        await stop.wait()
    finally:
        await daemon.stop()


def main() -> None:
    parser = argparse.ArgumentParser(prog="claude-streamdeck")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    _setup_logging(args.debug)
    asyncio.run(_run(args.config))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test the CLI by running it without a device**

Run: `.venv/bin/python -m claude_streamdeck --debug & sleep 1 ; kill %1`

Expected: log lines showing socket server listening on the default path, then graceful shutdown when killed. (No real device → log message saying enumeration found nothing supported, but daemon still runs.)

If the command fails because the default `~/.config/claude-streamdeck/` directory does not exist, that's a real bug — the socket server is supposed to mkdir its parent. If it does fail, fix `SocketServer.start` (it already does `mkdir(parents=True, exist_ok=True)` per Task 10, so this should work).

- [ ] **Step 4: Run the full unit + integration test suite**

Run: `.venv/bin/python -m pytest plugin/tests/ -v`
Expected: All tests still PASS (nothing should regress).

- [ ] **Step 5: Commit**

```bash
git add plugin/daemon/claude_streamdeck/daemon.py plugin/daemon/claude_streamdeck/__main__.py
git commit -m "Add daemon orchestrator and CLI entry point"
```

---

## Task 15: End-to-end protocol test (mock device)

**Files:**
- Test: `plugin/tests/test_protocol_e2e.py`

Verifies the full stack: spin up a `Daemon` with a mocked `DeviceManager.enumerate`, connect a real Unix socket client, push JSONL commands, receive responses, simulate a press, observe a broadcast event.

- [ ] **Step 1: Write the failing test**

Create `plugin/tests/test_protocol_e2e.py`:

```python
"""End-to-end test of the daemon over a real Unix socket with a mocked device."""

import asyncio
import base64
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from claude_streamdeck.config import DaemonConfig
from claude_streamdeck.core.device import DeviceModel, MockDevice
from claude_streamdeck.daemon import Daemon


def _png() -> str:
    img = Image.new("RGB", (50, 50), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def _send(w, obj):
    w.write((json.dumps(obj) + "\n").encode())
    await w.drain()


async def _recv(r):
    line = await asyncio.wait_for(r.readline(), timeout=2.0)
    return json.loads(line.decode().strip())


async def test_e2e_set_image_then_press():
    sock = Path(tempfile.mkdtemp()) / "e2e.sock"
    cfg = DaemonConfig(
        socket_path=sock,
        assets_dir=Path("/nonexistent"),
        extensions=[],
    )
    daemon = Daemon(cfg)

    # Inject a MockDevice instead of enumerating real hardware.
    mock = MockDevice(id="xl-test", model=DeviceModel.XL,
                      key_count=32, image_size=(96, 96))
    with patch.object(daemon.devices, "enumerate", return_value=[mock]):
        await daemon.start()
    try:
        r, w = await asyncio.open_unix_connection(str(sock))

        # Upload an asset
        await _send(w, {"cmd": "asset.upload", "request_id": "1",
                        "name": "a", "data": _png()})
        resp = await _recv(r)
        assert resp["ok"] is True
        assert resp["result"]["name"] == "a"

        # Display it on button 5
        await _send(w, {"cmd": "display.set", "request_id": "2",
                        "button": 5, "asset": "a"})
        resp = await _recv(r)
        assert resp["ok"] is True
        assert mock.last_image_for(5) is not None

        # Activate button 7 and subscribe
        await _send(w, {"cmd": "input.set_active", "request_id": "3",
                        "button": 7, "active": True})
        resp = await _recv(r)
        assert resp["ok"] is True
        await _send(w, {"cmd": "input.subscribe", "request_id": "4"})
        resp = await _recv(r)
        assert resp["ok"] is True

        # Simulate a press; expect an event
        mock.simulate_press(7, True)
        ev = await _recv(r)
        assert ev["event"] == "button.pressed"
        assert ev["device_id"] == "xl-test"
        assert ev["button"] == 7

        w.close()
        await w.wait_closed()
    finally:
        await daemon.stop()


async def test_e2e_unknown_command_keeps_connection():
    sock = Path(tempfile.mkdtemp()) / "e2e2.sock"
    cfg = DaemonConfig(socket_path=sock, assets_dir=Path("/nonexistent"), extensions=[])
    daemon = Daemon(cfg)
    mock = MockDevice(id="m", model=DeviceModel.XL, key_count=32, image_size=(96, 96))
    with patch.object(daemon.devices, "enumerate", return_value=[mock]):
        await daemon.start()
    try:
        r, w = await asyncio.open_unix_connection(str(sock))
        await _send(w, {"cmd": "nope.nope", "request_id": "x"})
        resp = await _recv(r)
        assert resp["ok"] is False
        assert resp["error"] == "unknown_command"

        await _send(w, {"cmd": "system.ping", "request_id": "y"})
        resp = await _recv(r)
        assert resp["ok"] is True
        assert resp["result"] == {"pong": True}

        w.close(); await w.wait_closed()
    finally:
        await daemon.stop()
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest plugin/tests/test_protocol_e2e.py -v`
Expected: 2 PASSED.

If the first run fails because the daemon's `_connect_devices` doesn't pick up the mocked enumerate, the issue is likely in `Daemon._connect_devices`: it iterates `self.devices.enumerate()`. The patch above patches `daemon.devices.enumerate`, which is the right target. If it still fails, double-check that `DeviceManager.enumerate` is called once at startup and again in the reconnect loop — both call sites will use the patched version.

- [ ] **Step 3: Commit**

```bash
git add plugin/tests/test_protocol_e2e.py
git commit -m "Add end-to-end protocol test with mock device"
```

---

## Task 16: Smoke test script for a real Stream Deck XL

**Files:**
- Create: `plugin/scripts/smoke_test.sh`

Manual end-to-end check against real hardware. This is **not** an automated test — it's run by a human with an XL plugged in. It exercises the protocol end-to-end through the socket.

- [ ] **Step 1: Create the smoke test script**

Create `plugin/scripts/smoke_test.sh`:

```bash
#!/usr/bin/env bash
# Manual smoke test: requires a Stream Deck XL plugged in.
# Run the daemon in another terminal first:
#   .venv/bin/python -m claude_streamdeck --debug

set -euo pipefail

SOCKET="${HOME}/.config/claude-streamdeck/daemon.sock"

if [[ ! -S "$SOCKET" ]]; then
  echo "Socket not found at $SOCKET. Is the daemon running?"
  exit 1
fi

# Send a command, read one response (one line of JSON).
send() {
  local payload="$1"
  echo "$payload" | nc -U "$SOCKET" -q 1 | head -n 1
}

echo "1. system.ping"
send '{"cmd":"system.ping","request_id":"a"}'

echo "2. device.list"
send '{"cmd":"device.list","request_id":"b"}'

echo "3. system.version"
send '{"cmd":"system.version","request_id":"c"}'

echo "Done. If all three returned ok:true, the daemon is alive."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x plugin/scripts/smoke_test.sh
```

- [ ] **Step 3: Commit**

```bash
git add plugin/scripts/smoke_test.sh
git commit -m "Add manual smoke test script for real Stream Deck XL"
```

---

## Task 17: Final test run and cleanup

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/python -m pytest plugin/tests/ -v`
Expected: All tests across all task files PASS. Approximate count: ~55 tests.

- [ ] **Step 2: Verify no stray files from the old POC remain**

Run: `ls plugin/daemon/claude_streamdeck/`
Expected: only `__init__.py`, `__main__.py`, `config.py`, `daemon.py`, `core/`, `transport/`, `handlers/`, `extensions/`. No `actions.py`, `state_machine.py`, `streamdeck_controller.py`, `socket_server.py` at the top level.

Run: `ls plugin/tests/`
Expected: `__init__.py`, `conftest.py`, and the new `test_*.py` files. No `test_state_machine.py` (it was deleted in Task 0).

- [ ] **Step 3: Verify the README of `plugin/daemon` is up to date**

If `plugin/daemon/README.md` exists and references old commands or files, update it. If it doesn't exist, do nothing here — README updates are out of scope for this plan.

- [ ] **Step 4: Final commit if anything changed**

```bash
git status
```
If there are changes:
```bash
git add -A
git commit -m "Cleanup after core daemon rewrite"
```
If clean: nothing to commit, the rewrite is complete.

---

## Self-Review

**Spec coverage check** (against `docs/superpowers/specs/2026-05-06-streamdeck-core-daemon-design.md`):

- §3 Architecture: covered by Task 14 (orchestrator wires Tasks 1–13).
- §4.1 DeviceManager: Task 7. §4.2 Device: Task 4. §4.3 AssetRegistry: Task 3. §4.4 DisplayEngine: Task 6. §4.5 InputDispatcher: Task 5. §4.6 EventBus: Task 1. §4.7 CommandRegistry: Task 2. §4.8 SocketServer: Task 10 (with Connection in Task 9). §4.9 CoreAPI: Task 8.
- §5 Protocol (commands, events, errors): Task 11 (handlers) + Task 10 (transport built-ins for `input.subscribe/unsubscribe`) + Task 15 (E2E).
- §6 Extension mechanism: Task 12 (loader + echo demo) + Task 13 (config schema).
- §7 Code structure: matches Task 0 + Tasks 1–14 file layout.
- §8 Error handling: most cases covered explicitly in handler tests (Task 11) and SocketServer tests (Task 10). `device_not_found` is implemented in `device_handlers._resolve_device` and tested via E2E indirectly. `extension_error` is tested in Task 10's exception path. Note: connection-broken cleanup happens in `SocketServer._handle_connection`'s `finally` block (Task 10).
- §9 Tests: covered by per-task tests. The "smoke test (manual)" is Task 16.
- §10 MVP scope: Task 0 wipes POC; everything reimplemented; no Claude extension yet (correctly out of scope).

**Placeholder scan:** No "TBD", "TODO", "implement later", "fill in details" in any task. Every code step has full content. Test code is complete.

**Type / name consistency check:**
- `DeviceModel.XL` used in Tasks 4, 7, 11, 12, 15 — consistent.
- `Asset` dataclass: `name`, `frames`, `frame_durations_ms`, `size_bytes`; `animated` and `frame_count` are properties — used consistently in Tasks 3, 11, 12, 15.
- `set_image` (DisplayEngine method) vs `display.set` (JSON command name) — distinct on purpose: API method names use snake_case, JSON uses dotted names. Cross-references in handlers (Task 11) are correct.
- `purge_device` defined in Task 6, called in Task 14 — consistent.
- `bind_loop` defined in Task 1, called in Task 14 — consistent.
- `attach`/`detach` (InputDispatcher) defined in Task 5, called in Tasks 12, 14 — consistent.
- `register_core_handlers` defined in Task 11's `__init__.py`, called in Task 14 — consistent.
- `load_extensions`/`shutdown_extensions` defined in Task 12, called in Task 14 — consistent.
- `_resolve_device` is reused across handlers (Task 11) — single source in `device_handlers.py`.

No issues found.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-streamdeck-core-daemon.md`.**
