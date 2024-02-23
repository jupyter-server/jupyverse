from asphalt.core import Component, add_resource, get_resource, request_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab

from .routes import _Lab


class LabComponent(Component):
    async def start(self) -> None:
        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore
        frontend_config = await request_resource(FrontendConfig)
        jupyterlab_config = get_resource(JupyterLabConfig)

        lab = _Lab(app, auth, frontend_config, jupyterlab_config)
        await add_resource(lab, types=Lab)
