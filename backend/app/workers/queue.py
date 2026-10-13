from collections.abc import Awaitable, Callable
from typing import Protocol


class JobQueue(Protocol):
    """Provider-agnostic boundary for expensive asynchronous work."""

    async def enqueue(self, name: str, task: Callable[[], Awaitable[None]]) -> str: ...


class QueueNotConfiguredError(RuntimeError):
    pass
