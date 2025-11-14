from anyio import Event, create_task_group
from fps import Module
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _Lab


class LabModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        frontend_config = await self.get(FrontendConfig)
        jupyterlab_config = await self.get(JupyterLabConfig)

        async with create_task_group() as tg:
            lab = _Lab(app, auth, frontend_config, jupyterlab_config, self.exit_app, tg)
            self.put(lab, Lab)
            self.done()
            shutdown = Event()
            self.add_teardown_callback(shutdown.set)
            await shutdown.wait()
