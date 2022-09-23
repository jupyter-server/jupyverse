from typing import Dict, List, Optional, Tuple

from fastapi import WebSocket


class User:
    pass


def current_user(*args, **kwargs):
    async def _():
        pass

    return _


def websocket_auth(permissions: Optional[Dict[str, List[str]]] = None):
    async def _(
        websocket: WebSocket,
    ) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
        return websocket, permissions

    return _


async def update_user():
    async def _(*args, **kwargs):
        pass

    return _
