from fps import Module
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_api.lab import Lab, PageConfig

from .routes import _JupyterLab


class JupyterLabModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = JupyterLabConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.config, JupyterLabConfig)

        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        frontend_config = await self.get(FrontendConfig)
        lab = await self.get(Lab)  # type: ignore[type-abstract]
        page_config = await self.get(PageConfig)

        jupyterlab = _JupyterLab(app, self.config, auth, frontend_config, lab, page_config)
        self.put(jupyterlab, JupyterLab)
