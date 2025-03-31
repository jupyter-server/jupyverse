from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import structlog
from anyio import Event
from fastapi import Response

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.terminals import Terminal, Terminals, TerminalServer

TERMINALS: dict[str, dict[str, Any]] = {}

log = structlog.get_logger()


class _Terminals(Terminals):
    def __init__(self, app: App, auth: Auth, _TerminalServer: type[TerminalServer]) -> None:
        super().__init__(app=app, auth=auth)
        self.TerminalServer = _TerminalServer
        self.stop_event = Event()

    async def start(self):
        await self.stop_event.wait()

    async def stop(self):
        for terminal in TERMINALS.values():
            terminal["server"].quit()
        self.stop_event.set()

    async def get_terminals(
        self,
        user: User,
    ):
        return [terminal["info"] for terminal in TERMINALS.values()]

    async def create_terminal(
        self,
        user: User,
    ):
        name_int = 1
        while True:
            if str(name_int) not in TERMINALS:
                break
            name_int += 1
        name = str(name_int)
        log.info("Creating terminal", name=name)
        terminal = Terminal(
            name=name,
            last_activity=datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        server = self.TerminalServer()
        TERMINALS[name] = {"info": terminal, "server": server}
        log.info("Terminal created", name=name)
        return terminal

    async def delete_terminal(
        self,
        name: str,
        user: User,
    ):
        log.info("Deleting terminal", name=name)
        if name in TERMINALS:
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
        if name not in TERMINALS:
            return

        await TERMINALS[name]["server"].serve(websocket, permissions)
        if name in TERMINALS:
            TERMINALS[name]["server"].quit(websocket)
            if not TERMINALS[name]["server"].websockets:
                del TERMINALS[name]
        log.info("Terminal exited", name=name)
