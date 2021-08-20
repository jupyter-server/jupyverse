from datetime import datetime
from http import HTTPStatus
from typing import Dict, Any

import fps  # type: ignore
from fastapi import APIRouter, WebSocket, Response

from .models import Terminal
from .server import TerminalServer

router = APIRouter()

TERMINALS: Dict[str, Dict[str, Any]] = {}


@router.get("/api/terminals")
async def get_terminals():
    return [terminal["info"] for terminal in TERMINALS.values()]


@router.post("/api/terminals")
async def create_terminal():
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
async def delete_terminal(name: str):
    TERMINALS[name]["server"].quit()
    del TERMINALS[name]
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.websocket("/terminals/websocket/{name}")
async def terminal_ws(websocket: WebSocket, name):
    await websocket.accept()
    await TERMINALS[name]["server"].serve(websocket)
    if name in TERMINALS:
        TERMINALS[name]["server"].quit()
        del TERMINALS[name]


r = fps.hooks.register_router(router)
