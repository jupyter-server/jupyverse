from asphalt.core import Component, Context

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents, HTTPContents

from .routes import _HTTPContents


class ContentsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore

        http_contents = _HTTPContents(app, auth)
        contents = http_contents.contents
        ctx.add_resource(http_contents, types=HTTPContents)
        ctx.add_resource(contents, types=Contents)
