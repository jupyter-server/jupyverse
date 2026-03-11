from collections.abc import Awaitable, Callable
from typing import Any

from fps import Module


class PageConfig:
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._hooks: list[Callable[[dict[str, Any]], Awaitable[None]]] = []

    def register(self, hook: Callable[[dict[str, Any]], Awaitable[None]]):
        self._hooks.append(hook)

    def set(self, **kwargs: Any) -> None:
        self._config = kwargs

    async def get(self) -> dict[str, Any]:
        for hook in self._hooks:
            await hook(self._config)

        return self._config


class PageConfigModule(Module):
    async def prepare(self):
        self.put(PageConfig())
