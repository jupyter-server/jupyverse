from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth

from .routes import JupyterCAD


class JupyterCADComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore

        jupytercad = JupyterCAD(app, auth)
        ctx.add_resource(jupytercad)
