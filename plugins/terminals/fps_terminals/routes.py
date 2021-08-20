from datetime import datetime
from typing import Dict

import fps  # type: ignore
from fastapi import APIRouter, WebSocket

from .models import Terminal
from .server import TerminalServer

router = APIRouter()

TERMINALS: Dict[str, Terminal] = {}


@router.get("/api/terminals")
async def get_terminals():
    return list(TERMINALS.values())


@router.post("/api/terminals")
async def create_terminal():
    name = str(len(TERMINALS) + 1)
    terminal = Terminal(
        **{
            "name": name,
            "last_activity": datetime.utcnow().isoformat() + "Z",
        }
    )
    TERMINALS[name] = terminal
    return terminal


@router.websocket("/terminals/websocket/{name}")
async def terminal_ws(websocket: WebSocket, name):
    await websocket.accept()
    terminal_server = TerminalServer()
    await terminal_server.serve(websocket)
    del TERMINALS[name]


r = fps.hooks.register_router(router)
