from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _Lab


class LabComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore
        frontend_config = await ctx.request_resource(FrontendConfig)
        jupyterlab_config = ctx.get_resource(JupyterLabConfig)

        lab = _Lab(app, auth, frontend_config, jupyterlab_config)
        ctx.add_resource(lab, types=Lab)
