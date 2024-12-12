from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _JupyterLab


class JupyterLabComponent(Component):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.jupyterlab_config = JupyterLabConfig(**kwargs)

    async def prepare(self) -> None:
        self.add_resource(self.jupyterlab_config, types=JupyterLabConfig)

        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)
        frontend_config = await self.get_resource(FrontendConfig)
        lab = await self.get_resource(Lab)

        jupyterlab = _JupyterLab(app, self.jupyterlab_config, auth, frontend_config, lab)
        self.add_resource(jupyterlab, types=JupyterLab)

        self.done()
