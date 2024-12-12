from __future__ import annotations

import structlog
from anyio import create_task_group
from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs

from .routes import _Kernels

log = structlog.get_logger()


class KernelsComponent(Component):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.kernels_config = KernelsConfig(**kwargs)

    async def prepare(self) -> None:
        self.add_resource(self.kernels_config, types=KernelsConfig)

        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)
        frontend_config = await self.get_resource(FrontendConfig)
        lifespan = await self.get_resource(Lifespan)
        yjs = (
            await self.get_resource(Yjs)
            if self.kernels_config.require_yjs
            else None
        )

        self.kernels = _Kernels(app, self.kernels_config, auth, frontend_config, yjs, lifespan)
        self.add_resource(self.kernels, types=Kernels)

        async with create_task_group() as tg:
            tg.start_soon(self.kernels.start)
            self.done()

    async def stop(self) -> None:
        await self.kernels.stop()
