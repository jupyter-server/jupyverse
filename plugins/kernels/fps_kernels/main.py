from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from asphalt.core import Component, add_resource, request_resource, start_background_task

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.yjs import Yjs

from .routes import _Kernels


class KernelsComponent(Component):
    def __init__(self, **kwargs):
        self.kernels_config = KernelsConfig(**kwargs)

    async def start(self) -> AsyncGenerator[None, Optional[BaseException]]:
        await add_resource(self.kernels_config, types=KernelsConfig)

        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore
        frontend_config = await request_resource(FrontendConfig)
        yjs = (
            await request_resource(Yjs)  # type: ignore
            if self.kernels_config.require_yjs
            else None
        )

        kernels = _Kernels(app, self.kernels_config, auth, frontend_config, yjs)
        await start_background_task(kernels.start, name="Kernels", teardown_action=kernels.stop)
        await add_resource(kernels, types=Kernels)
