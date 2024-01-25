from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict, Type

from anyio import Event
from fastapi import Response

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.terminals import Terminal, Terminals, TerminalServer

TERMINALS: Dict[str, Dict[str, Any]] = {}


class _Terminals(Terminals):
    def __init__(self, app: App, auth: Auth, _TerminalServer: Type[TerminalServer]) -> None:
        super().__init__(app=app, auth=auth)
        self.TerminalServer = _TerminalServer
        self.stopped = Event()

    async def start(self):
        await self.stopped.wait()

    async def stop(self):
        print(f"stopping {TERMINALS}")
        for terminal in TERMINALS.values():
            await terminal["server"].stop()
        self.stopped.set()

    async def get_terminals(
        self,
        user: User,
    ):
        return [terminal["info"] for terminal in TERMINALS.values()]

    async def create_terminal(
        self,
        user: User,
    ):
        name = str(len(TERMINALS) + 1)
        terminal = Terminal(
            name=name,
            last_activity=datetime.utcnow().isoformat() + "Z",
        )
        server = self.TerminalServer()
        TERMINALS[name] = {"info": terminal, "server": server}
        return terminal

    async def delete_terminal(
        self,
        name: str,
        user: User,
    ):
        for websocket in TERMINALS[name]["server"].websockets:
            TERMINALS[name]["server"].quit(websocket)
        del TERMINALS[name]
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def terminal_websocket(
        self,
        name,
        websocket_permissions,
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
