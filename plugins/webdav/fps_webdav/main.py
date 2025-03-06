from fps import Module

from jupyverse_api.app import App

from .config import WebDAVConfig
from .routes import WebDAV


class WebDAVModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = WebDAVConfig(**kwargs)

    async def prepare(self) -> None:
        app = await self.get(App)

        webdav = WebDAV(app, self.config)
        self.put(webdav)
