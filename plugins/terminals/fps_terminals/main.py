import sys
from typing import Type

from asphalt.core import Component, add_resource, get_resource, start_service_task

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.terminals import Terminals, TerminalServer

from .routes import _Terminals

_TerminalServer: Type[TerminalServer]
if sys.platform == "win32":
    from .win_server import _TerminalServer
else:
    from .server import _TerminalServer


class TerminalsComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]

        terminals = _Terminals(app, auth, _TerminalServer)
        await start_service_task(terminals.start, name="Terminals", teardown_action=terminals.stop)
        add_resource(terminals, types=Terminals)
