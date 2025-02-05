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
        # FIXME: find a better way than getting JupyterLabConfig with a timeout
        try:
            jupyterlab_config = await self.get(JupyterLabConfig, timeout=0.1)
        except TimeoutError:
            jupyterlab_config = None

        lab = _Lab(app, auth, frontend_config, jupyterlab_config)
        self.put(lab, types=Lab)
