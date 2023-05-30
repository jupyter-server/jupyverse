from asphalt.core import Component, Context
from jupyverse_api.app import App

from .config import WebDAVConfig
from .routes import WebDAV


class WebDAVComponent(Component):
    def __init__(self, **kwargs):
        self.webdav_config = WebDAVConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)

        webdav = WebDAV(app, self.webdav_config)
        ctx.add_resource(webdav)
