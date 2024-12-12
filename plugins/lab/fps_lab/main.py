from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _Lab


class LabComponent(Component):
    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)
        frontend_config = await self.get_resource(FrontendConfig)
        jupyterlab_config = await self.get_resource(JupyterLabConfig, timeout=0.1)

        lab = _Lab(app, auth, frontend_config, jupyterlab_config)
        self.add_resource(lab, types=Lab)

        self.done()
