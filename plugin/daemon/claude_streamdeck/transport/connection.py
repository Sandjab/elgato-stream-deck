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
