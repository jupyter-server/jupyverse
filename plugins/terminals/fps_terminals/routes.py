import os
from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict

from fastapi import APIRouter, Depends, Response
from fps.hooks import register_router  # type: ignore
from fps_auth.backends import (  # type: ignore
    current_user,
    websocket_permissions_for_current_user,
)
from fps_auth.models import UserRead  # type: ignore

from .models import Terminal

if os.name == "nt":
    from .win_server import TerminalServer  # type: ignore
else:
    from .server import TerminalServer  # type: ignore

router = APIRouter()

TERMINALS: Dict[str, Dict[str, Any]] = {}


@router.get("/api/terminals")
async def get_terminals():
    return [terminal["info"] for terminal in TERMINALS.values()]


@router.post("/api/terminals")
async def create_terminal(
    user: UserRead = Depends(current_user("terminals")),
):
    name = str(len(TERMINALS) + 1)
    terminal = Terminal(
        **{
            "name": name,
            "last_activity": datetime.utcnow().isoformat() + "Z",
        }
    )
    server = TerminalServer()
    TERMINALS[name] = {"info": terminal, "server": server}
    return terminal


@router.delete("/api/terminals/{name}", status_code=204)
async def delete_terminal(
    name: str,
    user: UserRead = Depends(current_user("terminals")),
):
    for websocket in TERMINALS[name]["server"].websockets:
        TERMINALS[name]["server"].quit(websocket)
    del TERMINALS[name]
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.websocket("/terminals/websocket/{name}")
async def terminal_websocket(
    name,
    websocket_permissions=Depends(
        websocket_permissions_for_current_user({"terminals": ["read", "execute"]})
    ),
):
    websocket, permissions = websocket_permissions
    await websocket.accept()
    await TERMINALS[name]["server"].serve(websocket, permissions)
    if name in TERMINALS:
        TERMINALS[name]["server"].quit(websocket)
        if not TERMINALS[name]["server"].websockets:
            del TERMINALS[name]


r = register_router(router)
