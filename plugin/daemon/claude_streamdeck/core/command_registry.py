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
