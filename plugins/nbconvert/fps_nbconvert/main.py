from asphalt.core import Component, Context
from jupyverse_api.auth import Auth
from jupyverse_api.app import App
from jupyverse_api.nbconvert import Nbconvert

from .routes import _Nbconvert


class NbconvertComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore

        nbconvert = _Nbconvert(app, auth)
        ctx.add_resource(nbconvert, types=Nbconvert)
