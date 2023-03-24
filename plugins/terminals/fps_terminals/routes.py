from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict, Type

from fastapi import APIRouter, Depends, Response
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.terminals import Terminals, TerminalServer

from .models import Terminal

TERMINALS: Dict[str, Dict[str, Any]] = {}


class _Terminals(Terminals):
    def __init__(self, app: App, auth: Auth, _TerminalServer: Type[TerminalServer]) -> None:
        super().__init__(app)
        router = APIRouter()

        @router.get("/api/terminals")
        async def get_terminals(
            user: User = Depends(auth.current_user({"terminals": ["read"]})),
        ):
            return [terminal["info"] for terminal in TERMINALS.values()]

        @router.post("/api/terminals")
        async def create_terminal(
            user: User = Depends(auth.current_user({"terminals": ["write"]})),
        ):
            name = str(len(TERMINALS) + 1)
            terminal = Terminal(
                name=name,
                last_activity=datetime.utcnow().isoformat() + "Z",
            )
            server = _TerminalServer()
            TERMINALS[name] = {"info": terminal, "server": server}
            return terminal

        @router.delete("/api/terminals/{name}", status_code=204)
        async def delete_terminal(
            name: str,
            user: User = Depends(auth.current_user(permissions={"terminals": ["write"]})),
        ):
            for websocket in TERMINALS[name]["server"].websockets:
                TERMINALS[name]["server"].quit(websocket)
            del TERMINALS[name]
            return Response(status_code=HTTPStatus.NO_CONTENT.value)

        @router.websocket("/terminals/websocket/{name}")
        async def terminal_websocket(
            name,
            websocket_permissions=Depends(
                auth.websocket_auth(permissions={"terminals": ["read", "execute"]})
            ),
        ):
            if websocket_permissions is None:
                return
            websocket, permissions = websocket_permissions
            await websocket.accept()
            await TERMINALS[name]["server"].serve(websocket, permissions)
            if name in TERMINALS:
                TERMINALS[name]["server"].quit(websocket)
                if not TERMINALS[name]["server"].websockets:
                    del TERMINALS[name]

        self.include_router(router)
