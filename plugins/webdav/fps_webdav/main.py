from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App

from .config import WebDAVConfig
from .routes import WebDAV


class WebDAVComponent(Component):
    def __init__(self, **kwargs):
        self.webdav_config = WebDAVConfig(**kwargs)

    async def start(self) -> None:
        app = await get_resource(App, wait=True)

        webdav = WebDAV(app, self.webdav_config)
        add_resource(webdav)
