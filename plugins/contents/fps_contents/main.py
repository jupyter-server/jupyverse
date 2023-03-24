from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents

from .routes import _Contents


class ContentsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore

        contents = _Contents(app, auth)
        ctx.add_resource(contents, types=Contents)
