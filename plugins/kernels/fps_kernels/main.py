from __future__ import annotations
import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Optional

from asphalt.core import Component, Context, context_teardown

from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.yjs import Yjs
from jupyverse_api.app import App

from .routes import _Kernels


logger = logging.getLogger("kernels")


class KernelsComponent(Component):
    def __init__(self, **kwargs):
        self.kernels_config = KernelsConfig(**kwargs)

    @context_teardown
    async def start(
        self,
        ctx: Context,
    ) -> AsyncGenerator[None, Optional[BaseException]]:
        ctx.add_resource(self.kernels_config, types=KernelsConfig)

        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore
        frontend_config = await ctx.request_resource(FrontendConfig)
        yjs = await ctx.request_resource(Yjs)

        kernels = _Kernels(app, self.kernels_config, auth, frontend_config, yjs)
        ctx.add_resource(kernels, types=Kernels)

        if self.kernels_config.connection_path is not None:
            path = Path(self.kernels_config.connection_path)
            task = asyncio.create_task(kernels.watch_connection_files(path))

        yield

        if self.kernels_config.connection_path is not None:
            task.cancel()
        for kernel in kernels.kernels.values():
            await kernel["server"].stop()
