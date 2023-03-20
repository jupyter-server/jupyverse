from asphalt.core import Component, Context, inject, resource
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents

from .routes import _Contents


class ContentsComponent(Component):
    @inject
    async def start(
        self,
        ctx: Context,
        app: App = resource(),
    ) -> None:
        auth = await ctx.request_resource(Auth)

        contents = _Contents(app, auth)
        ctx.add_resource(contents, types=Contents)
