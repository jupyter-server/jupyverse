import logging
from functools import partial

try:
    from asgi_webdav.config import init_config_from_obj  # type: ignore
    from asgi_webdav.constants import DAV_METHODS, AppEntryParameters  # type: ignore
    from asgi_webdav.server import get_asgi_app  # type: ignore

    asgi_webdav_installed = True
except BaseException:
    asgi_webdav_installed = False
from jupyverse_api.app import App

from .config import WebDAVConfig


logger = logging.getLogger("webdav")


class WebDAVApp:
    def __init__(self, app, webdav_app):
        self._app = app
        self._webdav_app = webdav_app

    async def __call__(self, scope, receive, send):
        if scope.get("method") in DAV_METHODS and scope.get("path").startswith("/webdav"):
            return await self._webdav_app(scope, receive, send)
        return await self._app(scope, receive, send)


class WebDAV:
    def __init__(self, app: App, webdav_config: WebDAVConfig):
        if not asgi_webdav_installed:
            return

        for account in webdav_config.account_mapping:
            logger.info(f"WebDAV user {account.username} has password {account.password}")
        webdav_conf = webdav_config.dict()
        init_config_from_obj(webdav_conf)
        webdav_aep = AppEntryParameters()
        webdav_app = get_asgi_app(aep=webdav_aep, config_obj=webdav_conf)
        app.add_middleware(partial(WebDAVApp, webdav_app=webdav_app))
