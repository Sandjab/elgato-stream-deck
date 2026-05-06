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
