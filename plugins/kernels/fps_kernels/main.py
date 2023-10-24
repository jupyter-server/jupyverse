from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Optional

from asphalt.core import Component, Context, context_teardown

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.yjs import Yjs

from .kernel_driver.paths import jupyter_runtime_dir
from .routes import _Kernels


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
        yjs = (
            await ctx.request_resource(Yjs)  # type: ignore
            if self.kernels_config.require_yjs
            else None
        )

        kernels = _Kernels(app, self.kernels_config, auth, frontend_config, yjs)
        ctx.add_resource(kernels, types=Kernels)

        if self.kernels_config.allow_external_kernels:
            external_connection_dir = self.kernels_config.external_connection_dir
            if external_connection_dir is None:
                path = Path(jupyter_runtime_dir()) / "external_kernels"
            else:
                path = Path(external_connection_dir)
            task = asyncio.create_task(kernels.watch_connection_files(path))

        yield

        if self.kernels_config.allow_external_kernels:
            task.cancel()
        for kernel in kernels.kernels.values():
            await kernel["server"].stop()
