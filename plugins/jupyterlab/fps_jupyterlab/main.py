from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _JupyterLab


class JupyterLabComponent(Component):
    def __init__(self, **kwargs):
        self.jupyterlab_config = JupyterLabConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(self.jupyterlab_config, types=JupyterLabConfig)

        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore
        frontend_config = await ctx.request_resource(FrontendConfig)
        lab = await ctx.request_resource(Lab)  # type: ignore

        jupyterlab = _JupyterLab(app, self.jupyterlab_config, auth, frontend_config, lab)
        ctx.add_resource(jupyterlab, types=JupyterLab)
