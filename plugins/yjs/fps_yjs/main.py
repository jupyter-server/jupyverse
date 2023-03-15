from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.yjs import Yjs

from .routes import _Yjs


class YjsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)
        contents = await ctx.request_resource(Contents)

        yjs = _Yjs(app, auth, contents)
        ctx.add_resource(yjs, types=Yjs)
