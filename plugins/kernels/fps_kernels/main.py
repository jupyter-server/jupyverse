from __future__ import annotations

import structlog
from anyio import create_task_group
from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernel import DefaultKernelFactory
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs

from .routes import _Kernels

log = structlog.get_logger()


class KernelsModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = KernelsConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.config, KernelsConfig)

        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        frontend_config = await self.get(FrontendConfig)
        lifespan = await self.get(Lifespan)
        yjs = (
            await self.get(Yjs)  # type: ignore[type-abstract]
            if self.config.require_yjs
            else None
        )
        default_kernel_factory = await self.get(DefaultKernelFactory)

        self.kernels = _Kernels(
            app,
            self.config,
            auth,
            frontend_config,
            yjs,
            lifespan,
            default_kernel_factory,
        )
        self.put(self.kernels, Kernels, teardown_callback=self.kernels.stop)

        async with create_task_group() as tg:
            tg.start_soon(self.kernels.start)
            self.done()
