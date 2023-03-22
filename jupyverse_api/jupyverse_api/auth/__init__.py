from typing import Any, Callable, Dict, List, Optional, Tuple

from jupyverse_api import Config
from pydantic import BaseModel


class User(BaseModel):
    username: str = ""
    name: str = ""
    display_name: str = ""
    initials: Optional[str] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    workspace: str = "{}"
    settings: str = "{}"


class Auth:
    def current_user(self, permissions: Optional[Dict[str, List[str]]] = None) -> Callable:
        raise RuntimeError("Not implemented")

    async def update_user(self) -> Callable:
        raise RuntimeError("Not implemented")

    def websocket_auth(
        self,
        permissions: Optional[Dict[str, List[str]]] = None,
    ) -> Callable[[], Tuple[Any, Dict[str, List[str]]]]:
        raise RuntimeError("Not implemented")


class AuthConfig(Config):
    pass
