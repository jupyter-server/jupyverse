from __future__ import annotations

from asphalt.core import Component, add_resource, get_resource, start_service_task

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs

from .routes import _Kernels


class KernelsComponent(Component):
    def __init__(self, **kwargs):
        self.kernels_config = KernelsConfig(**kwargs)

    async def start(self) -> None:
        add_resource(self.kernels_config, types=KernelsConfig)

        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]
        frontend_config = await get_resource(FrontendConfig, wait=True)
        lifespan = await get_resource(Lifespan, wait=True)
        if self.kernels_config.require_yjs:
            yjs = await get_resource(Yjs, wait=True)  # type: ignore[type-abstract]
        else:
            yjs = None

        kernels = _Kernels(app, self.kernels_config, auth, frontend_config, yjs, lifespan)  # type: ignore[type-abstract]
        await start_service_task(kernels.start, "Kernels", teardown_action=kernels.stop)
        add_resource(kernels, types=Kernels)
