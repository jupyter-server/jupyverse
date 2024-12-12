import structlog
from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.lab import Lab
from jupyverse_api.notebook import Notebook

from .routes import _Notebook

logger = structlog.get_logger()


class NotebookComponent(Component):
    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)
        frontend_config = await self.get_resource(FrontendConfig)
        lab = await self.get_resource(Lab)

        notebook = _Notebook(app, auth, frontend_config, lab)
        self.add_resource(notebook, types=Notebook)

        self.done()
