import logging

from asphalt.core import Component, Context

from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.yjs import Yjs
from jupyverse_api.app import App

from .config import _KernelsConfig
from .routes import _Kernels


logger = logging.getLogger("kernels")


class KernelsComponent(Component):
    def __init__(self, **kwargs):
        self.kernels_config = _KernelsConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(self.kernels_config, types=KernelsConfig)

        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)
        frontend_config = await ctx.request_resource(FrontendConfig)
        yjs = await ctx.request_resource(Yjs)

        kernels = _Kernels(app, self.kernels_config, auth, frontend_config, yjs)
        ctx.add_resource(kernels, types=Kernels)
