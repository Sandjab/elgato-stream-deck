"""State machine for tracking Claude Code session state.

Handles state transitions based on events received from Claude Code hooks.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from .config import ClaudeState

logger = logging.getLogger(__name__)


class Event(Enum):
    """Events that trigger state transitions."""
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    NOTIFICATION = "Notification"
    PRE_COMPACT = "PreCompact"


@dataclass
class StateContext:
    """Context information for current state."""
    state: ClaudeState = ClaudeState.INACTIVE
    session_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_depth: int = 0  # Track nested tool calls
    last_event: Optional[Event] = None


# Type alias for state change listeners
StateChangeListener = Callable[[ClaudeState, ClaudeState, StateContext], None]


class StateMachine:
    """Manages Claude Code session state transitions.

    State Diagram:
        INACTIVE --SessionStart--> IDLE
        IDLE --UserPromptSubmit--> THINKING
        THINKING --PreToolUse--> TOOL_RUNNING
        TOOL_RUNNING --PostToolUse--> THINKING
        THINKING --Stop--> IDLE
        * --SessionEnd--> INACTIVE

    The tool_depth counter handles nested tool calls (e.g., when a tool
    spawns subagents that use their own tools).
    """

    def __init__(self) -> None:
        self._context = StateContext()
        self._listeners: List[StateChangeListener] = []

    @property
    def state(self) -> ClaudeState:
        """Get current state."""
        return self._context.state

    @property
    def context(self) -> StateContext:
        """Get current context."""
        return self._context

    def add_listener(self, listener: StateChangeListener) -> None:
        """Add a listener to be notified of state changes."""
        self._listeners.append(listener)

    def remove_listener(self, listener: StateChangeListener) -> None:
        """Remove a state change listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, old_state: ClaudeState, new_state: ClaudeState) -> None:
        """Notify all listeners of a state change."""
        for listener in self._listeners:
            try:
                listener(old_state, new_state, self._context)
            except Exception as e:
                logger.error(f"Error in state change listener: {e}")

    def _transition(self, new_state: ClaudeState) -> None:
        """Perform a state transition and notify listeners."""
        old_state = self._context.state
        if old_state != new_state:
            logger.info(f"State transition: {old_state.value} -> {new_state.value}")
            self._context.state = new_state
            self._notify_listeners(old_state, new_state)

    def process_event(
        self,
        event_type: str,
        session_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """Process an event and update state accordingly.

        Args:
            event_type: The event type string from Claude Code hook
            session_id: Optional session identifier
            tool_name: Optional tool name (for tool events)
            **kwargs: Additional event data (ignored)
        """
        try:
            event = Event(event_type)
        except ValueError:
            logger.warning(f"Unknown event type: {event_type}")
            return

        self._context.last_event = event

        if event == Event.SESSION_START:
            self._handle_session_start(session_id)
        elif event == Event.SESSION_END:
            self._handle_session_end()
        elif event == Event.USER_PROMPT_SUBMIT:
            self._handle_user_prompt_submit()
        elif event == Event.PRE_TOOL_USE:
            self._handle_pre_tool_use(tool_name)
        elif event == Event.POST_TOOL_USE:
            self._handle_post_tool_use()
        elif event == Event.STOP:
            self._handle_stop()
        elif event == Event.SUBAGENT_STOP:
            self._handle_subagent_stop()
        elif event == Event.NOTIFICATION:
            self._handle_notification()
        elif event == Event.PRE_COMPACT:
            self._handle_pre_compact()

    def _handle_session_start(self, session_id: Optional[str]) -> None:
        """Handle SessionStart event."""
        self._context.session_id = session_id
        self._context.tool_depth = 0
        self._context.tool_name = None
        self._transition(ClaudeState.IDLE)

    def _handle_session_end(self) -> None:
        """Handle SessionEnd event."""
        self._context.session_id = None
        self._context.tool_depth = 0
        self._context.tool_name = None
        self._transition(ClaudeState.INACTIVE)

    def _handle_user_prompt_submit(self) -> None:
        """Handle UserPromptSubmit event."""
        if self._context.state in (ClaudeState.IDLE, ClaudeState.INACTIVE):
            self._transition(ClaudeState.THINKING)

    def _handle_pre_tool_use(self, tool_name: Optional[str]) -> None:
        """Handle PreToolUse event."""
        self._context.tool_depth += 1
        self._context.tool_name = tool_name
        if self._context.state == ClaudeState.THINKING:
            self._transition(ClaudeState.TOOL_RUNNING)
        # Notify listeners even if state didn't change (tool name updated)
        elif self._context.state == ClaudeState.TOOL_RUNNING:
            self._notify_listeners(ClaudeState.TOOL_RUNNING, ClaudeState.TOOL_RUNNING)

    def _handle_post_tool_use(self) -> None:
        """Handle PostToolUse event."""
        if self._context.tool_depth > 0:
            self._context.tool_depth -= 1

        if self._context.tool_depth == 0:
            self._context.tool_name = None
            if self._context.state == ClaudeState.TOOL_RUNNING:
                self._transition(ClaudeState.THINKING)

    def _handle_stop(self) -> None:
        """Handle Stop event."""
        self._context.tool_depth = 0
        self._context.tool_name = None
        if self._context.state in (ClaudeState.THINKING, ClaudeState.TOOL_RUNNING):
            self._transition(ClaudeState.IDLE)

    def _handle_subagent_stop(self) -> None:
        """Handle SubagentStop event - same as Stop."""
        self._handle_stop()

    def _handle_notification(self) -> None:
        """Handle Notification event - no state change."""
        logger.debug("Notification received")

    def _handle_pre_compact(self) -> None:
        """Handle PreCompact event - no state change."""
        logger.debug("PreCompact received")

    def reset(self) -> None:
        """Reset state machine to initial state."""
        old_state = self._context.state
        self._context = StateContext()
        if old_state != ClaudeState.INACTIVE:
            self._notify_listeners(old_state, ClaudeState.INACTIVE)
