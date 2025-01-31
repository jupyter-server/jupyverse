from fastaio import Component

from jupyverse_api.app import App

from .config import WebDAVConfig
from .routes import WebDAV


class WebDAVComponent(Component):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.webdav_config = WebDAVConfig(**kwargs)

    async def prepare(self) -> None:
        app = await self.get_resource(App)

        webdav = WebDAV(app, self.webdav_config)
        self.add_resource(webdav)
