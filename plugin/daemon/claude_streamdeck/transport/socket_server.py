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
