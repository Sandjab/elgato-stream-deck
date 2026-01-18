"""Main daemon orchestrator for Claude Code Stream Deck plugin.

Coordinates the state machine, socket server, and Stream Deck controller
to provide a unified interface between Claude Code and the hardware.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from .actions import action_handler
from .config import ButtonLayout, ClaudeState, Config, config
from .socket_server import SocketServer
from .state_machine import StateContext, StateMachine
from .streamdeck_controller import StreamDeckController

logger = logging.getLogger(__name__)


class ClaudeStreamDeckDaemon:
    """Main daemon class that orchestrates all components."""

    def __init__(self, cfg: Optional[Config] = None) -> None:
        """Initialize the daemon.

        Args:
            cfg: Optional configuration override
        """
        self.config = cfg or config
        self.state_machine = StateMachine()
        self.controller = StreamDeckController(self.config)
        self.socket_server: Optional[SocketServer] = None
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        """Start the daemon."""
        logger.info("Starting Claude Stream Deck daemon...")

        # Store reference to event loop for thread-safe callbacks
        self._loop = asyncio.get_running_loop()

        # Ensure directories exist
        self.config.ensure_directories()

        # Register state change listener
        self.state_machine.add_listener(self._on_state_change)

        # Connect to Stream Deck
        await self._connect_streamdeck()

        # Start socket server
        self.socket_server = SocketServer(
            socket_path=self.config.socket_path,
            message_handler=self._on_socket_message,
            timeout=self.config.socket_timeout
        )
        await self.socket_server.start()

        self._running = True
        logger.info("Daemon started successfully")

    async def _connect_streamdeck(self) -> None:
        """Connect to Stream Deck with retry logic."""
        while self._running or not self.controller.is_connected:
            if self.controller.connect():
                # Set up key callback
                self.controller.set_key_callback(self._on_key_press)
                return

            logger.warning(
                f"Stream Deck not found, retrying in "
                f"{self.config.reconnect_delay}s..."
            )
            await asyncio.sleep(self.config.reconnect_delay)

    async def stop(self) -> None:
        """Stop the daemon gracefully."""
        logger.info("Stopping daemon...")
        self._running = False

        # Cancel reconnect task if running
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Stop socket server
        if self.socket_server:
            await self.socket_server.stop()

        # Disconnect Stream Deck
        self.controller.disconnect()

        # Remove listener
        self.state_machine.remove_listener(self._on_state_change)

        logger.info("Daemon stopped")

    async def run(self) -> None:
        """Run the daemon main loop."""
        await self.start()

        try:
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)

                # Check Stream Deck connection
                if not self.controller.is_connected:
                    logger.warning("Stream Deck disconnected, attempting reconnect...")
                    await self._connect_streamdeck()

        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    def _on_socket_message(self, message: dict) -> None:
        """Handle incoming socket message.

        Args:
            message: Parsed JSON message from hook script
        """
        event_type = message.get("event")
        tool_name = message.get("tool")
        session_id = message.get("session_id")

        if not event_type:
            logger.warning(f"Invalid message (no event): {message}")
            return

        logger.debug(f"Processing event: {event_type}, tool: {tool_name}")

        # Update state machine
        self.state_machine.process_event(
            event_type=event_type,
            session_id=session_id,
            tool_name=tool_name
        )

    def _on_state_change(
        self,
        old_state: ClaudeState,
        new_state: ClaudeState,
        context: StateContext
    ) -> None:
        """Handle state machine state changes.

        Args:
            old_state: Previous state
            new_state: New state
            context: Current state context
        """
        logger.info(
            f"State changed: {old_state.value} -> {new_state.value}"
            f" (tool: {context.tool_name})"
        )

        # Update Stream Deck display
        self.controller.update_state(new_state, context.tool_name)

    def _on_key_press(self, key: int, pressed: bool) -> None:
        """Handle Stream Deck key press.

        Called from Stream Deck library thread, not main event loop.

        Args:
            key: Key index
            pressed: True if key was pressed, False if released
        """
        # Only handle press events, not release
        if not pressed:
            return

        # Schedule async action on main event loop (thread-safe)
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._handle_key_action(key),
                self._loop
            )

    async def _handle_key_action(self, key: int) -> None:
        """Handle key press action asynchronously.

        Args:
            key: Key index that was pressed
        """
        # Flash key for feedback
        await self.controller.flash_key(key, self.config.flash_duration)

        if key == ButtonLayout.NEW:
            await action_handler.new_session()
        elif key == ButtonLayout.RESUME:
            await action_handler.resume_session()
        elif key == ButtonLayout.STOP:
            await action_handler.stop_session()
        else:
            logger.debug(f"Unbound key pressed: {key}")


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the daemon.

    Args:
        debug: Enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Reduce noise from libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("StreamDeck").setLevel(logging.WARNING)


def run_daemon(debug: bool = False) -> None:
    """Run the daemon with signal handling.

    Args:
        debug: Enable debug logging
    """
    setup_logging(debug)

    daemon = ClaudeStreamDeckDaemon()

    # Set up signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler():
        logger.info("Received shutdown signal")
        loop.create_task(daemon.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(daemon.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        loop.close()
