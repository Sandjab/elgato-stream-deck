"""Unix socket server for receiving Claude Code hook events.

Listens on a Unix domain socket and processes JSON messages
from the streamdeck-notify.sh hook script.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Type alias for message handlers
MessageHandler = Callable[[dict], None]


class SocketServer:
    """Async Unix domain socket server.

    Receives JSON messages from Claude Code hooks and dispatches
    them to registered handlers.
    """

    def __init__(
        self,
        socket_path: Path,
        message_handler: MessageHandler,
        timeout: float = 5.0
    ) -> None:
        """Initialize the socket server.

        Args:
            socket_path: Path to the Unix socket file
            message_handler: Callback function to handle received messages
            timeout: Connection timeout in seconds
        """
        self.socket_path = socket_path
        self.message_handler = message_handler
        self.timeout = timeout
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False

    async def start(self) -> None:
        """Start the socket server."""
        # Ensure socket directory exists
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing socket file if present
        if self.socket_path.exists():
            logger.info(f"Removing existing socket: {self.socket_path}")
            self.socket_path.unlink()

        # Create the server
        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self.socket_path)
        )

        # Set socket permissions (readable/writable by user only)
        os.chmod(self.socket_path, 0o600)

        self._running = True
        logger.info(f"Socket server listening on: {self.socket_path}")

    async def stop(self) -> None:
        """Stop the socket server."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Clean up socket file
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
                logger.info(f"Removed socket file: {self.socket_path}")
            except OSError as e:
                logger.warning(f"Could not remove socket file: {e}")

    async def serve_forever(self) -> None:
        """Run the server until stopped."""
        if not self._server:
            await self.start()

        if self._server:
            async with self._server:
                await self._server.serve_forever()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming connection.

        Reads JSON data from the connection and dispatches to the handler.
        """
        peer = "unix socket client"
        logger.debug(f"Connection from {peer}")

        try:
            # Read data with timeout
            data = await asyncio.wait_for(
                reader.read(4096),
                timeout=self.timeout
            )

            if data:
                await self._process_message(data)

        except asyncio.TimeoutError:
            logger.warning(f"Connection timeout from {peer}")
        except ConnectionResetError:
            logger.debug(f"Connection reset by {peer}")
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_message(self, data: bytes) -> None:
        """Process a received message.

        Parses JSON and dispatches to the message handler.
        """
        try:
            # Decode and parse JSON
            text = data.decode("utf-8").strip()
            if not text:
                return

            message = json.loads(text)
            logger.debug(f"Received message: {message}")

            # Dispatch to handler
            self.message_handler(message)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON received: {e}")
        except UnicodeDecodeError as e:
            logger.warning(f"Invalid UTF-8 data received: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running and self._server is not None
