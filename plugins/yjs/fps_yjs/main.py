from __future__ import annotations
from collections.abc import AsyncGenerator

from asphalt.core import Component, Context, context_teardown
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.yjs import Yjs

from .routes import _Yjs


class YjsComponent(Component):
    @context_teardown
    async def start(
        self,
        ctx: Context,
    ) -> AsyncGenerator[None, BaseException | None]:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)
        contents = await ctx.request_resource(Contents)

        yjs = _Yjs(app, auth, contents)
        ctx.add_resource(yjs, types=Yjs)

        # start indexing in the background
        contents.file_id_manager

        yield

        contents.file_id_manager.stop_watching_files.set()
        await contents.file_id_manager.stopped_watching_files.wait()
