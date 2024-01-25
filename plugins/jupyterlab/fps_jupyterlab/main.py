from asphalt.core import Component, Context, add_resource, request_resource

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
        await add_resource(self.jupyterlab_config, types=JupyterLabConfig)

        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore
        frontend_config = await request_resource(FrontendConfig)
        lab = await request_resource(Lab)  # type: ignore

        jupyterlab = _JupyterLab(app, self.jupyterlab_config, auth, frontend_config, lab)
        await add_resource(jupyterlab, types=JupyterLab)
