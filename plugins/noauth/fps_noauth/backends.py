from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket
from jupyverse_api.auth import Auth, User

USER = User()


class _NoAuth(Auth):
    def current_user(self, *args, **kwargs):
        async def _():
            return USER

        return _

    def websocket_auth(self, permissions: Optional[Dict[str, List[str]]] = None):
        async def _(
            websocket: WebSocket,
        ) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
            return websocket, permissions

        return _

    async def update_user(self):
        async def _(data: Dict[str, Any]) -> User:
            global USER
            user = dict(USER)
            user.update(data)
            USER = User(**user)
            return USER

        return _
