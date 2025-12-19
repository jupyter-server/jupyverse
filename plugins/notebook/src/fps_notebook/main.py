import structlog
from fps import Module
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab, PageConfig
from jupyverse_api.notebook import Notebook

from .routes import _Notebook

logger = structlog.get_logger()


class NotebookModule(Module):
    async def prepare(self) -> None:
        self.put(None, JupyterLabConfig)
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        frontend_config = await self.get(FrontendConfig)
        lab = await self.get(Lab)  # type: ignore[type-abstract]
        page_config = await self.get(PageConfig)

        notebook = _Notebook(app, auth, frontend_config, lab, page_config)
        self.put(notebook, Notebook)
