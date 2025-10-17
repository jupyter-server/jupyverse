from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from jupyverse_api import Config

from .models import User  # noqa


class Auth(ABC):
    @abstractmethod
    def current_user(self, permissions: dict[str, list[str]] | None = None) -> Callable: ...

    @abstractmethod
    async def update_user(self) -> Callable: ...

    @abstractmethod
    def websocket_auth(
        self,
        permissions: dict[str, list[str]] | None = None,
    ) -> Callable[[Any], Awaitable[tuple[Any, dict[str, list[str]] | None] | None]]: ...


class AuthConfig(Config):
    pass
