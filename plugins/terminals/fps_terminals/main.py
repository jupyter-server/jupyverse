import os
from typing import Type

from asphalt.core import Component, add_resource, request_resource, start_background_task

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.terminals import Terminals, TerminalServer

from .routes import _Terminals

_TerminalServer: Type[TerminalServer]
if os.name == "nt":
    from .win_server import _TerminalServer
else:
    from .server import _TerminalServer


class TerminalsComponent(Component):
    async def start(self) -> None:
        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore

        terminals = _Terminals(app, auth, _TerminalServer)
        await start_background_task(terminals.start, name="Terminals", teardown_action=terminals.stop)
        await add_resource(terminals, types=Terminals)
