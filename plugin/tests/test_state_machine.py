"""Unit tests for state machine module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add daemon directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "daemon"))

from claude_streamdeck.config import ClaudeState
from claude_streamdeck.state_machine import Event, StateMachine, StateContext


class TestStateMachine:
    """Tests for StateMachine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = StateMachine()
        self.listener_calls = []

        def listener(old, new, ctx):
            self.listener_calls.append((old, new, ctx.tool_name))

        self.sm.add_listener(listener)

    def test_initial_state(self):
        """Test that initial state is INACTIVE."""
        assert self.sm.state == ClaudeState.INACTIVE

    def test_session_start_transition(self):
        """Test SessionStart transitions from INACTIVE to IDLE."""
        self.sm.process_event("SessionStart", session_id="test-123")

        assert self.sm.state == ClaudeState.IDLE
        assert self.sm.context.session_id == "test-123"
        assert len(self.listener_calls) == 1
        assert self.listener_calls[0] == (ClaudeState.INACTIVE, ClaudeState.IDLE, None)

    def test_user_prompt_submit_transition(self):
        """Test UserPromptSubmit transitions from IDLE to THINKING."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")

        assert self.sm.state == ClaudeState.THINKING
        assert len(self.listener_calls) == 2
        assert self.listener_calls[1] == (ClaudeState.IDLE, ClaudeState.THINKING, None)

    def test_pre_tool_use_transition(self):
        """Test PreToolUse transitions from THINKING to TOOL_RUNNING."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")
        self.sm.process_event("PreToolUse", tool_name="Read")

        assert self.sm.state == ClaudeState.TOOL_RUNNING
        assert self.sm.context.tool_name == "Read"
        assert self.sm.context.tool_depth == 1

    def test_post_tool_use_transition(self):
        """Test PostToolUse transitions from TOOL_RUNNING to THINKING."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")
        self.sm.process_event("PreToolUse", tool_name="Read")
        self.sm.process_event("PostToolUse")

        assert self.sm.state == ClaudeState.THINKING
        assert self.sm.context.tool_name is None
        assert self.sm.context.tool_depth == 0

    def test_nested_tool_calls(self):
        """Test nested tool calls maintain TOOL_RUNNING state."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")
        self.sm.process_event("PreToolUse", tool_name="Task")
        self.sm.process_event("PreToolUse", tool_name="Read")

        assert self.sm.state == ClaudeState.TOOL_RUNNING
        assert self.sm.context.tool_name == "Read"
        assert self.sm.context.tool_depth == 2

        self.sm.process_event("PostToolUse")
        assert self.sm.state == ClaudeState.TOOL_RUNNING
        assert self.sm.context.tool_depth == 1

        self.sm.process_event("PostToolUse")
        assert self.sm.state == ClaudeState.THINKING
        assert self.sm.context.tool_depth == 0

    def test_stop_transition(self):
        """Test Stop transitions from THINKING/TOOL_RUNNING to IDLE."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")
        self.sm.process_event("PreToolUse", tool_name="Read")
        self.sm.process_event("Stop")

        assert self.sm.state == ClaudeState.IDLE
        assert self.sm.context.tool_depth == 0

    def test_session_end_transition(self):
        """Test SessionEnd transitions any state to INACTIVE."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")
        self.sm.process_event("SessionEnd")

        assert self.sm.state == ClaudeState.INACTIVE
        assert self.sm.context.session_id is None

    def test_unknown_event_ignored(self):
        """Test that unknown events are ignored."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UnknownEvent")

        assert self.sm.state == ClaudeState.IDLE
        assert len(self.listener_calls) == 1

    def test_reset(self):
        """Test reset returns to initial state."""
        self.sm.process_event("SessionStart")
        self.sm.process_event("UserPromptSubmit")
        self.sm.reset()

        assert self.sm.state == ClaudeState.INACTIVE
        assert self.sm.context.session_id is None

    def test_remove_listener(self):
        """Test listener removal."""
        listener = MagicMock()
        self.sm.add_listener(listener)
        self.sm.remove_listener(listener)

        self.sm.process_event("SessionStart")
        listener.assert_not_called()

    def test_listener_error_handling(self):
        """Test that listener errors don't break state machine."""
        def bad_listener(old, new, ctx):
            raise ValueError("Test error")

        self.sm.add_listener(bad_listener)
        self.sm.process_event("SessionStart")

        # State should still transition despite listener error
        assert self.sm.state == ClaudeState.IDLE


class TestEvent:
    """Tests for Event enum."""

    def test_event_values(self):
        """Test that all expected events exist."""
        assert Event.SESSION_START.value == "SessionStart"
        assert Event.SESSION_END.value == "SessionEnd"
        assert Event.USER_PROMPT_SUBMIT.value == "UserPromptSubmit"
        assert Event.PRE_TOOL_USE.value == "PreToolUse"
        assert Event.POST_TOOL_USE.value == "PostToolUse"
        assert Event.STOP.value == "Stop"


class TestStateContext:
    """Tests for StateContext dataclass."""

    def test_default_values(self):
        """Test default context values."""
        ctx = StateContext()

        assert ctx.state == ClaudeState.INACTIVE
        assert ctx.session_id is None
        assert ctx.tool_name is None
        assert ctx.tool_depth == 0
        assert ctx.last_event is None
