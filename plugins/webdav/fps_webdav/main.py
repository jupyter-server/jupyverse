from asphalt.core import Component, add_resource, request_resource

from jupyverse_api.app import App

from .config import WebDAVConfig
from .routes import WebDAV


class WebDAVComponent(Component):
    def __init__(self, **kwargs):
        self.webdav_config = WebDAVConfig(**kwargs)

    async def start(self) -> None:
        app = await request_resource(App)

        webdav = WebDAV(app, self.webdav_config)
        await add_resource(webdav)
