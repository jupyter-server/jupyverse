from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from jupyverse_api import Config

from .models import User  # noqa


class Auth(ABC):
    @abstractmethod
    def current_user(self, permissions: Optional[Dict[str, List[str]]] = None) -> Callable:
        ...

    @abstractmethod
    async def update_user(self) -> Callable:
        ...

    @abstractmethod
    def websocket_auth(
        self,
        permissions: Optional[Dict[str, List[str]]] = None,
    ) -> Callable[[Any], Awaitable[Optional[Tuple[Any, Optional[Dict[str, List[str]]]]]]]:
        ...


class AuthConfig(Config):
    pass
