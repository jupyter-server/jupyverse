from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import structlog
from anyio import TASK_STATUS_IGNORED, Event, create_task_group
from anyio.abc import TaskStatus
from fastapi import Response
from jupyverse_api import App
from jupyverse_auth import Auth, User
from jupyverse_terminals import Terminal, Terminals, TerminalServer

TERMINALS: dict[str, dict[str, Any]] = {}

log = structlog.get_logger()


class _Terminals(Terminals):
    def __init__(self, app: App, auth: Auth, _TerminalServer: type[TerminalServer]) -> None:
        super().__init__(app=app, auth=auth)
        self.TerminalServer = _TerminalServer
        self.stop_event = Event()

    async def start(self):
        # Terminal shells live in this task group, not in a websocket's.
        async with create_task_group() as self.task_group:
            await self.stop_event.wait()

    async def stop(self):
        # Stop shells before waking start() to drain the task group.
        for terminal in list(TERMINALS.values()):
            terminal["server"].quit()
        TERMINALS.clear()
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
        await self.task_group.start(self._run_terminal, name, server)
        log.info("Terminal created", name=name)
        return terminal

    async def delete_terminal(
        self,
        name: str,
        user: User,
    ):
        log.info("Deleting terminal", name=name)
        terminal = TERMINALS.pop(name, None)
        if terminal is not None:
            terminal["server"].quit()
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

    async def _run_terminal(
        self,
        name: str,
        server: TerminalServer,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
    ) -> None:
        try:
            await server.run(task_status=task_status)
        except Exception:
            # A terminal failure must not cancel the shared task group.
            log.exception("Terminal task failed", name=name)
        finally:
            # The name may already belong to a newer terminal.
            if name in TERMINALS and TERMINALS[name]["server"] is server:
                del TERMINALS[name]
            log.info("Terminal exited", name=name)
