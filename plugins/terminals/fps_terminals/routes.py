from datetime import datetime
from http import HTTPStatus
from typing import Dict, Any

from fps.config import Config  # type: ignore
from fps.hooks import register_router  # type: ignore
from fastapi import APIRouter, WebSocket, Response, Depends, status

from fps_auth.routes import cookie_authentication, users  # type: ignore
from fps_auth.models import User, user_db  # type: ignore
from fps_auth.config import AuthConfig  # type: ignore

from .models import Terminal
from .server import TerminalServer

router = APIRouter()
auth_config = Config(AuthConfig)

TERMINALS: Dict[str, Dict[str, Any]] = {}


@router.get("/api/terminals")
async def get_terminals():
    return [terminal["info"] for terminal in TERMINALS.values()]


@router.post("/api/terminals")
async def create_terminal(
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
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
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    TERMINALS[name]["server"].quit()
    del TERMINALS[name]
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.websocket("/terminals/websocket/{name}")
async def terminal_websocket(websocket: WebSocket, name):
    accept_websocket = False
    if auth_config.disable_auth:
        accept_websocket = True
    else:
        cookie = websocket._cookies["fastapiusersauth"]
        user = await cookie_authentication(cookie, user_db)
        if user:
            accept_websocket = True
    if accept_websocket:
        await websocket.accept()
        await TERMINALS[name]["server"].serve(websocket)
        if name in TERMINALS:
            TERMINALS[name]["server"].quit(websocket)
            del TERMINALS[name]
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


r = register_router(router)
