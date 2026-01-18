"""Button action handlers for Stream Deck.

Implements the New, Resume, and Stop actions with platform-specific
implementations for macOS and Linux.
"""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def get_platform() -> str:
    """Get the current platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        return "unknown"


class ActionHandler:
    """Handles button press actions."""

    def __init__(self) -> None:
        self._platform = get_platform()
        logger.info(f"ActionHandler initialized for platform: {self._platform}")

    async def new_session(self) -> bool:
        """Start a new Claude Code session.

        Opens a new terminal window and runs 'claude' command.

        Returns:
            True if action was successful, False otherwise.
        """
        logger.info("Action: New session")

        if self._platform == "macos":
            return await self._new_session_macos()
        elif self._platform == "linux":
            return await self._new_session_linux()
        else:
            logger.error(f"Unsupported platform: {self._platform}")
            return False

    async def _new_session_macos(self) -> bool:
        """Start new session on macOS using AppleScript."""
        script = '''
        tell application "Terminal"
            activate
            do script "claude"
        end tell
        '''

        return await self._run_osascript(script)

    async def _new_session_linux(self) -> bool:
        """Start new session on Linux."""
        # Try common terminal emulators in order of preference
        terminals = [
            ("gnome-terminal", ["gnome-terminal", "--", "claude"]),
            ("konsole", ["konsole", "-e", "claude"]),
            ("xfce4-terminal", ["xfce4-terminal", "-e", "claude"]),
            ("xterm", ["xterm", "-e", "claude"]),
            ("kitty", ["kitty", "claude"]),
            ("alacritty", ["alacritty", "-e", "claude"]),
        ]

        for name, cmd in terminals:
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(
                        cmd,
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logger.info(f"Launched new session with {name}")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to launch {name}: {e}")
                    continue

        logger.error("No supported terminal emulator found")
        return False

    async def resume_session(self) -> bool:
        """Resume the most recent Claude Code session.

        Opens a new terminal window and runs 'claude --resume' command.

        Returns:
            True if action was successful, False otherwise.
        """
        logger.info("Action: Resume session")

        if self._platform == "macos":
            return await self._resume_session_macos()
        elif self._platform == "linux":
            return await self._resume_session_linux()
        else:
            logger.error(f"Unsupported platform: {self._platform}")
            return False

    async def _resume_session_macos(self) -> bool:
        """Resume session on macOS using AppleScript."""
        script = '''
        tell application "Terminal"
            activate
            do script "claude --resume"
        end tell
        '''

        return await self._run_osascript(script)

    async def _resume_session_linux(self) -> bool:
        """Resume session on Linux."""
        terminals = [
            ("gnome-terminal", ["gnome-terminal", "--", "claude", "--resume"]),
            ("konsole", ["konsole", "-e", "claude", "--resume"]),
            ("xfce4-terminal", ["xfce4-terminal", "-e", "claude --resume"]),
            ("xterm", ["xterm", "-e", "claude", "--resume"]),
            ("kitty", ["kitty", "claude", "--resume"]),
            ("alacritty", ["alacritty", "-e", "claude", "--resume"]),
        ]

        for name, cmd in terminals:
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(
                        cmd,
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logger.info(f"Launched resume session with {name}")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to launch {name}: {e}")
                    continue

        logger.error("No supported terminal emulator found")
        return False

    async def stop_session(self) -> bool:
        """Stop/interrupt the current Claude Code operation.

        Sends Escape key to the active terminal to interrupt Claude.

        Returns:
            True if action was successful, False otherwise.
        """
        logger.info("Action: Stop session")

        if self._platform == "macos":
            return await self._stop_session_macos()
        elif self._platform == "linux":
            return await self._stop_session_linux()
        else:
            logger.error(f"Unsupported platform: {self._platform}")
            return False

    async def _stop_session_macos(self) -> bool:
        """Stop session on macOS by sending Escape key."""
        # Send Escape key to Terminal
        script = '''
        tell application "System Events"
            tell process "Terminal"
                key code 53
            end tell
        end tell
        '''

        return await self._run_osascript(script)

    async def _stop_session_linux(self) -> bool:
        """Stop session on Linux using xdotool."""
        if not shutil.which("xdotool"):
            logger.error("xdotool not found - required for stop action on Linux")
            return False

        try:
            # Get active window
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error("Failed to get active window")
                return False

            window_id = result.stdout.strip()

            # Send Escape key
            subprocess.run(
                ["xdotool", "key", "--window", window_id, "Escape"],
                check=True
            )

            logger.info("Sent Escape key to active window")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"xdotool command failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to stop session: {e}")
            return False

    async def _run_osascript(self, script: str) -> bool:
        """Run an AppleScript on macOS.

        Args:
            script: AppleScript code to execute

        Returns:
            True if successful, False otherwise.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )

            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"osascript failed: {stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to run osascript: {e}")
            return False


# Global action handler instance
action_handler = ActionHandler()
