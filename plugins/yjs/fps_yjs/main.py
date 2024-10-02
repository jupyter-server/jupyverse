from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from asphalt.core import Component, Context, context_teardown

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.yjs import Yjs, YjsConfig

from .routes import _Yjs


class YjsComponent(Component):
    def __init__(self, **kwargs):
        self.yjs_config = YjsConfig(**kwargs)

    @context_teardown
    async def start(
        self,
        ctx: Context,
    ) -> AsyncGenerator[None, Optional[BaseException]]:
        ctx.add_resource(self.yjs_config, types=YjsConfig)

        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore
        contents = await ctx.request_resource(Contents)  # type: ignore

        yjs = _Yjs(app, self.yjs_config, auth, contents)
        ctx.add_resource(yjs, types=Yjs)

        # start indexing in the background
        contents.file_id_manager

        yield

        yjs.room_manager.stop()
        contents.file_id_manager.stop_watching_files.set()
        await contents.file_id_manager.stopped_watching_files.wait()
