from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _Lab


class LabComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]
        frontend_config = await get_resource(FrontendConfig, wait=True)
        jupyterlab_config = await get_resource(JupyterLabConfig, optional=True)

        lab = _Lab(app, auth, frontend_config, jupyterlab_config)
        add_resource(lab, types=Lab)
