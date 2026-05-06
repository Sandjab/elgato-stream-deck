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
