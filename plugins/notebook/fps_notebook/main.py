from asphalt.core import Component, Context

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.lab import Lab
from jupyverse_api.notebook import Notebook

from .routes import _Notebook


class NotebookComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore
        frontend_config = await ctx.request_resource(FrontendConfig)
        lab = await ctx.request_resource(Lab)  # type: ignore

        notebook = _Notebook(app, auth, frontend_config, lab)
        ctx.add_resource(notebook, types=Notebook)
