import os
from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict

from fastapi import APIRouter, Depends, Response, WebSocket, status
from fps.hooks import register_router  # type: ignore
from fps_auth.backends import current_user, get_jwt_strategy  # type: ignore
from fps_auth.config import get_auth_config  # type: ignore
from fps_auth.db import get_user_db  # type: ignore
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
    user: UserRead = Depends(current_user),
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
    user: UserRead = Depends(current_user),
):
    for websocket in TERMINALS[name]["server"].websockets:
        TERMINALS[name]["server"].quit(websocket)
    del TERMINALS[name]
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.websocket("/terminals/websocket/{name}")
async def terminal_websocket(
    websocket: WebSocket,
    name,
    auth_config=Depends(get_auth_config),
    user_db=Depends(get_user_db),
):
    accept_websocket = False
    if auth_config.mode == "noauth":
        accept_websocket = True
    else:
        cookie = websocket._cookies["fastapiusersauth"]
        user = await get_jwt_strategy().read_token(cookie, user_db)
        if user:
            accept_websocket = True
    if accept_websocket:
        await websocket.accept()
        await TERMINALS[name]["server"].serve(websocket)
        if name in TERMINALS:
            TERMINALS[name]["server"].quit(websocket)
            if not TERMINALS[name]["server"].websockets:
                del TERMINALS[name]
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


r = register_router(router)
