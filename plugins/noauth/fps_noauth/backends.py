from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from jupyverse_api.auth import Auth, User

USER = User()


class _NoAuth(Auth):
    def current_user(self, *args, **kwargs):
        async def _():
            return USER

        return _

    def websocket_auth(self, permissions: dict[str, list[str]] | None = None):
        async def _(
            websocket: WebSocket,
        ) -> tuple[WebSocket, dict[str, list[str]] | None] | None:
            return websocket, permissions

        return _

    async def update_user(self):
        async def _(data: dict[str, Any]) -> User:
            global USER
            user = dict(USER)
            user.update(data)
            USER = User(**user)
            return USER

        return _
