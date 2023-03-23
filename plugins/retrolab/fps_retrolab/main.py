from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.retrolab import RetroLab
from jupyverse_api.lab import Lab

from .routes import _RetroLab


class RetroLabComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore
        frontend_config = await ctx.request_resource(FrontendConfig)
        lab = await ctx.request_resource(Lab)  # type: ignore

        retrolab = _RetroLab(app, auth, frontend_config, lab)
        ctx.add_resource(retrolab, types=RetroLab)
