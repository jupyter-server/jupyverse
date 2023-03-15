from asphalt.core import Component, Context
from jupyverse_api.auth import Auth
from jupyverse_api.terminals import Terminals
from jupyverse_api.app import App

from .routes import _Terminals


class TerminalsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)

        terminals = _Terminals(app, auth)
        ctx.add_resource(terminals, types=Terminals)
