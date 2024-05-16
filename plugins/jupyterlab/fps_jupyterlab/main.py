from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _JupyterLab


class JupyterLabComponent(Component):
    def __init__(self, **kwargs):
        self.jupyterlab_config = JupyterLabConfig(**kwargs)

    async def start(self) -> None:
        add_resource(self.jupyterlab_config, types=JupyterLabConfig)

        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]
        frontend_config = await get_resource(FrontendConfig, wait=True)
        lab = await get_resource(Lab, wait=True)  # type: ignore[type-abstract]

        jupyterlab = _JupyterLab(app, self.jupyterlab_config, auth, frontend_config, lab)
        add_resource(jupyterlab, types=JupyterLab)
