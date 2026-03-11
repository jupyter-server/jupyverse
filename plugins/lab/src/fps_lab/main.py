from anyio import Event, create_task_group
from fps import Module
from jupyverse_api import App
from jupyverse_auth import Auth
from jupyverse_frontend import FrontendConfig
from jupyverse_jupyterlab import JupyterLabConfig
from jupyverse_lab import Lab, PageConfig

from .routes import _Lab


class LabModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        page_config = await self.get(PageConfig)
        frontend_config = await self.get(FrontendConfig)
        jupyterlab_config = await self.get(JupyterLabConfig)

        async with create_task_group() as tg:
            lab = _Lab(
                app, auth, frontend_config, jupyterlab_config, page_config, self.exit_app, tg
            )
            self.put(lab, Lab)
            self.done()
            shutdown = Event()
            self.add_teardown_callback(shutdown.set)
            await shutdown.wait()
