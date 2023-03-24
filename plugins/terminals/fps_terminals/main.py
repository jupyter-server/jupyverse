import os
from typing import Type

from asphalt.core import Component, Context
from jupyverse_api.auth import Auth
from jupyverse_api.terminals import Terminals, TerminalServer
from jupyverse_api.app import App

from .routes import _Terminals

_TerminalServer: Type[TerminalServer]
if os.name == "nt":
    from .win_server import _TerminalServer
else:
    from .server import _TerminalServer


class TerminalsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore

        terminals = _Terminals(app, auth, _TerminalServer)
        ctx.add_resource(terminals, types=Terminals)
