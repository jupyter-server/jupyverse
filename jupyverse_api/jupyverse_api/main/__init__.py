from asphalt.core import Component, Context
from asphalt.web.fastapi import FastAPIComponent
from fastapi import FastAPI

from ..app import App


class AppComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(FastAPI)

        _app = App(app)
        ctx.add_resource(_app)


class JupyverseComponent(FastAPIComponent):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        await super().start(ctx)
