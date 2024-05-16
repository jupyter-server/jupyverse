from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.lab import Lab
from jupyverse_api.notebook import Notebook

from .routes import _Notebook


class NotebookComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]
        frontend_config = await get_resource(FrontendConfig, wait=True)
        lab = await get_resource(Lab, wait=True)  # type: ignore[type-abstract]

        notebook = _Notebook(app, auth, frontend_config, lab)
        add_resource(notebook, types=Notebook)
